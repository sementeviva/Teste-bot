import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template
from twilio.rest import Client
from openai import OpenAI
from datetime import datetime
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho

app = Flask(__name__)
app.secret_key = "chave_secreta_upload"

# Blueprints
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
app.register_blueprint(upload_csv_bp)
app.register_blueprint(edit_produtos_bp)
app.register_blueprint(ver_produtos_bp)

# Variáveis de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

client_openai = OpenAI(api_key=openai_api_key)
client_twilio = Client(twilio_sid, twilio_token)

# Conexão com o banco
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

# Carregar produtos do banco
def carregar_produtos_db():
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM produtos", conn)
        df.columns = [col.strip().lower() for col in df.columns]
        df.fillna("", inplace=True)
        df["nome"] = df["nome"].astype(str).str.lower()
        conn.close()
        return df
    except Exception as e:
        print(f"Erro ao carregar produtos do banco: {e}")
        return pd.DataFrame(columns=["nome", "descricao", "preco", "categoria"])

produtos_df = carregar_produtos_db()

# Busca no catálogo
def buscar_produto_csv(mensagem):
    mensagem_lower = mensagem.lower()
    resultados = produtos_df[produtos_df["nome"].str.contains(mensagem_lower)]
    if not resultados.empty:
        respostas = []
        for _, row in resultados.iterrows():
            resposta = f"{row['nome'].capitalize()} - R$ {row['preco']}\n{row['descricao']}"
            respostas.append(resposta)
        return "\n\n".join(respostas)
    return None

def gerar_contexto_csv():
    contextos = []
    for _, row in produtos_df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preco']} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

contexto_produtos = gerar_contexto_csv()

def get_gpt_response(mensagem, contexto_produtos):
    prompt = f"""
Você é um assistente de vendas da loja Semente Viva.
Use o seguinte catálogo para responder de forma clara e natural.

Catálogo:
{contexto_produtos}

Mensagem do cliente: {mensagem}
    """
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Responda sempre em português com educação e clareza."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# Webhook WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From").replace("whatsapp:", "")
    user_message = request.form.get("Body").strip().lower()

    if user_message in ["menu", "ver produtos", "produtos"]:
        resposta_final = listar_categorias()
    elif user_message in ["carrinho", "ver carrinho"]:
        resposta_final = ver_carrinho(sender_number)
    elif user_message.isdigit():
        resposta_final = adicionar_ao_carrinho(sender_number, int(user_message))
    elif user_message in ["chá", "chás", "suplementos", "óleos", "veganos"]:
        resposta_final = listar_produtos_categoria(user_message)
    else:
        resposta_csv = buscar_produto_csv(user_message)
        if resposta_csv:
            resposta_final = resposta_csv
        else:
            resposta_final = get_gpt_response(user_message, contexto_produtos)

    # Envia a resposta
    client_twilio.messages.create(
        from_=twilio_number,
        to=f"whatsapp:{sender_number}",
        body=resposta_final
    )

    # Armazena no banco (usando data_hora, não datahora)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversas (contato, mensagem_usuario, resposta_bot, data_hora) VALUES (%s, %s, %s, %s)",
            (sender_number, user_message, resposta_final, datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar conversa: {e}")

    return "OK", 200

@app.route("/conversas", methods=["GET", "POST"])
def ver_conversas():
    conn = get_db_connection()
    cursor = conn.cursor()

    contato = request.form.get("contato", "")
    data = request.form.get("data", "")

    query = "SELECT * FROM conversas WHERE 1=1"
    params = []

    if contato:
        query += " AND contato LIKE %s"
        params.append(f"%{contato}%")
    if data:
        query += " AND DATE(data_hora) = %s"
        params.append(data)

    query += " ORDER BY data_hora DESC"

    cursor.execute(query, params)
    conversas = cursor.fetchall()
    conn.close()

    return render_template("conversas.html", conversas=conversas, contato=contato, data=data)

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
