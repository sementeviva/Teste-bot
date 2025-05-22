import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template
from twilio.rest import Client
from openai import OpenAI

from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho

app = Flask(__name__)
app.secret_key = "chave_secreta_upload"

# Blueprints
from routes.upload_csv import upload_csv_bp
app.register_blueprint(upload_csv_bp)
from routes.edit_produtos import edit_produtos_bp
app.register_blueprint(edit_produtos_bp)
from routes.ver_produtos import ver_produtos_bp
app.register_blueprint(ver_produtos_bp)

# Chaves de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

client_openai = OpenAI(api_key=openai_api_key)
client_twilio = Client(twilio_sid, twilio_token)

# Carrega produtos do banco de dados
def carregar_produtos_db():
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432)
        )
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

# Busca produto no DataFrame
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

# Gera contexto para o GPT
def gerar_contexto_csv():
    contextos = []
    for _, row in produtos_df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preco']} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

contexto_produtos = gerar_contexto_csv()

def get_gpt_response(mensagem, contexto_produtos):
    prompt = f"""
Você é um assistente de vendas de uma loja chamada Semente Viva.
Use o seguinte catálogo para responder perguntas dos clientes de forma natural e clara.

Catálogo de produtos:
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

# Webhook do WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From")  # Mantém 'whatsapp:+5511999999999'
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

    client_twilio.messages.create(
        from_=twilio_number,   # Deve estar no formato: whatsapp:+55...
        to=sender_number,      # Também no formato: whatsapp:+55...
        body=resposta_final
    )

    return "OK", 200

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
