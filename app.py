import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, Response
from datetime import datetime

# Importa utilitário Twilio
from utils.twilio_utils import send_whatsapp_message

# Importa módulos do seu fluxo (mantendo organização)
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho

# Blueprints
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_upload")

# Registre os blueprints
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")

RENDER_BASE_URL = "https://teste-bot-9ppl.onrender.com"

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

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

def buscar_produto_csv(mensagem):
    df = carregar_produtos_db()
    mensagem_lower = mensagem.lower()
    resultados = df[df["nome"].str.contains(mensagem_lower)]
    if not resultados.empty:
        respostas = []
        for _, row in resultados.iterrows():
            resposta = f"{row['nome'].capitalize()} - R$ {row['preco']}\n{row['descricao']}"
            respostas.append(resposta)
        return "\n\n".join(respostas)
    return None

def gerar_contexto_csv():
    df = carregar_produtos_db()
    contextos = []
    for _, row in df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preco']} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

def buscar_produto_detalhado(mensagem):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, preco, descricao, categoria, imagem FROM produtos WHERE LOWER(nome) LIKE %s LIMIT 1",
            (f"%{mensagem.lower()}%",)
        )
        produto = cur.fetchone()
        cur.close()
        conn.close()
        if produto:
            return {
                "id": produto[0],
                "nome": produto[1],
                "preco": produto[2],
                "descricao": produto[3],
                "categoria": produto[4],
                "tem_imagem": produto[5] is not None
            }
    except Exception as e:
        print(f"Erro buscar produto detalhado: {e}")
    return None

def get_gpt_response(mensagem):
    # (Sua lógica IA. Mantenha o mock se não tiver OpenAI.)
    return "Desculpe, não encontrei o produto que você procurou. Posso te ajudar com outra coisa?"

def salvar_conversa(sender_number, user_message, resposta_final):
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

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From", "").replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()

    print(f"[+] Recebido do WhatsApp: {sender_number} - Mensagem: {user_message}")

    if not sender_number or not user_message:
        print("[-] Dados insuficientes recebidos na mensagem WhatsApp.")
        return Response("Dados insuficientes", status=400)

    resposta_final = None

    user_message_lower = user_message.lower()

    # Atalhos de comando
    if user_message_lower in ["menu", "ver produtos", "produtos"]:
        resposta_final = listar_categorias()
    elif user_message_lower in ["carrinho", "ver carrinho"]:
        resposta_final = ver_carrinho(sender_number)
    elif user_message.isdigit():
        resposta_final = adicionar_ao_carrinho(sender_number, int(user_message))
    elif user_message_lower in ["chá", "chás", "suplementos", "óleos", "veganos"]:
        resposta_final = listar_produtos_categoria(user_message_lower)

    # Caso busca detalhada por produto (resposta com imagem)
    if resposta_final is None:
        produto_detalhado = buscar_produto_detalhado(user_message)
        if produto_detalhado:
            resposta_final = f"{produto_detalhado['nome'].capitalize()} - R$ {produto_detalhado['preco']}\n{produto_detalhado['descricao']}"
            if produto_detalhado["tem_imagem"]:
                img_url = f"{RENDER_BASE_URL}/ver_produtos/imagem/{produto_detalhado['id']}"
            else:
                img_url = None
            # Envia resposta (com ou sem imagem)
            try:
                send_whatsapp_message(
                    to_number=sender_number,
                    body=resposta_final,
                    media_url=img_url
                )
                print(f"[Twilio] Mensagem enviada para {sender_number} (com imagem? {'Sim' if img_url else 'Não'})")
            except Exception as e:
                print(f"[Twilio ERRO] Falha ao enviar WhatsApp produto detalhado: {e}")
            salvar_conversa(sender_number, user_message, resposta_final)
            return Response(status=200)

    # Brute force: busca qualquer produto por nome (csv)
    if resposta_final is None:
        resposta_csv = buscar_produto_csv(user_message)
        if resposta_csv:
            resposta_final = resposta_csv

    # IA (fallback)
    if resposta_final is None:
        resposta_final = get_gpt_response(user_message)

    # Envie a resposta padrão (fora do bloco de produto detalhado)
    try:
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        print(f"[Twilio] Mensagem enviada para {sender_number} (texto simples)")
    except Exception as e:
        print(f"[Twilio ERRO] Falha ao enviar WhatsApp: {e}")

    salvar_conversa(sender_number, user_message, resposta_final)
    return Response(status=200)

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
