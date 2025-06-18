import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from datetime import datetime
import requests

# --- NOVOS IMPORTS PARA AUTENTICAÇÃO ---
from flask_login import LoginManager
from models.user import User # O modelo que criámos no passo anterior
from routes.auth import auth_bp # O blueprint de autenticação que vamos criar a seguir

# Importa utilitários e os outros Blueprints
from utils.twilio_utils import send_whatsapp_message
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho, finalizar_compra
from utils.db_utils import get_db_connection, salvar_conversa
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp
from routes.treinamento_bot import treinamento_bot_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_secreta_muito_forte_e_dificil")

# --- INÍCIO DA CONFIGURAÇÃO DO FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
# Se um utilizador não logado tentar aceder a uma página protegida,
# ele será redirecionado para a rota 'auth.login'.
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, faça login para aceder a esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    """
    Esta função é usada pelo Flask-Login para recarregar o objeto do utilizador
    a partir do ID do utilizador guardado na sessão.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, email, conta_id FROM utilizadores WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
        if user_data:
            # Retorna um objeto User que criámos em models/user.py
            return User(id=user_data['id'], nome=user_data['nome'], email=user_data['email'], conta_id=user_data['conta_id'])
        return None
    except Exception as e:
        print(f"Erro ao carregar utilizador: {e}")
        return None
    finally:
        if conn:
            conn.close()
# --- FIM DA CONFIGURAÇÃO DO FLASK-LOGIN ---


# Registra os blueprints
app.register_blueprint(auth_bp, url_prefix="/auth") # NOVO: Blueprint de autenticação
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')
app.register_blueprint(treinamento_bot_bp, url_prefix="/treinamento")

# Variáveis de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)

# As funções auxiliares (carregar_produtos_db, etc.) continuam como estavam na sua versão.
def carregar_produtos_db():
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM produtos WHERE ativo = TRUE", conn)
        df.columns = [col.strip().lower() for col in df.columns]
        df.fillna("", inplace=True)
        df["nome"] = df["nome"].astype(str).str.lower()
        conn.close()
        return df
    except Exception as e:
        print(f"Erro ao carregar produtos do banco: {e}")
        return pd.DataFrame()

def buscar_produto_detalhado(mensagem):
    if len(mensagem.strip()) < 3: return None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, nome, preco, descricao FROM produtos WHERE LOWER(nome) ILIKE %s AND ativo = TRUE LIMIT 1", (f"%{mensagem.lower()}%",))
        produto = cur.fetchone()
        cur.close()
        conn.close()
        return produto
    except Exception as e:
        print(f"Erro buscar produto detalhado: {e}")
        return None

def get_gpt_response(mensagem):
    df = carregar_produtos_db()
    contextos = [f"ID {row['id']}: {row['nome'].capitalize()} - R$ {row['preco']:.2f} - {row['descricao']}" for _, row in df.iterrows()]
    contexto_produtos = "\n".join(contextos)
    prompt = f"""
    Você é um assistente virtual de vendas da loja Semente Viva. Seu objetivo é ser simpático, eficiente e guiar o cliente.
    Sempre guie o cliente sobre os próximos passos. Comandos: 'produtos', 'add <ID> <quantidade>', 'carrinho', 'finalizar'.
    Se o cliente perguntar sobre um produto, forneça a descrição, preço e sugira usar o comando 'add' com o ID.
    Catálogo: {contexto_produtos}
    Mensagem do cliente: {mensagem}
    """
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Responda sempre em português com educação e clareza."}, {"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # A lógica do Sandbox de Desenvolvimento
    is_test_mode = os.environ.get("TEST_MODE_ENABLED", "FALSE").upper() == "TRUE"
    developer_number = os.environ.get("DEVELOPER_WHATSAPP_NUMBER")
    
    sender_number_with_prefix = request.form.get("From", "")

    if is_test_mode:
        print("--- AVISO: A APLICAÇÃO ESTÁ EM MODO DE TESTE ---")
        if sender_number_with_prefix != developer_number:
            print(f"Mensagem de '{sender_number_with_prefix}' ignorada. Apenas o desenvolvedor '{developer_number}' pode interagir.")
            return "OK", 200
        else:
            print(f"--- INFO: Mensagem do desenvolvedor '{sender_number_with_prefix}' recebida em modo de teste. Processando... ---")

    # Variáveis principais
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    user_message_lower = user_message.lower()

    if not sender_number or not user_message:
        return "Dados insuficientes", 400

    # Lógica "Liga/Desliga"
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1", (sender_number,))
            venda_ativa = cur.fetchone()
            if venda_ativa and venda_ativa.get('modo_atendimento') == 'manual':
                salvar_conversa(sender_number, user_message, "--- MENSAGEM RECEBIDA EM MODO MANUAL ---")
                return "OK", 200
    finally:
        if conn: conn.close()
    
    resposta_final = ""
    
    # Lógica de Alerta e Resposta do Bot
    PALAVRAS_CHAVE_ALERTA = ['ajuda', 'atendente', 'humano', 'falar com alguem', 'falar com um atendente', 'problema', 'reclamação', 'cancelar']
    if any(palavra in user_message_lower for palavra in PALAVRAS_CHAVE_ALERTA):
        resposta_final = "Entendido. Um de nossos atendentes entrará em contato em breve para te ajudar. Por favor, aguarde um momento."
        # ... (lógica de alerta)
    elif user_message_lower in ["oi", "olá", "ola", "menu", "começar", "iniciar"]:
        resposta_final = ("Olá! Bem-vindo(a) à Semente Viva! 🌱\n\n"
                          "Comandos úteis:\n"
                          "👉 Digite `produtos` para ver nosso catálogo.\n"
                          "👉 Digite `carrinho` para ver seus itens.\n"
                          "👉 Digite `finalizar` para concluir seu pedido.")
    elif user_message_lower.startswith('add '):
        parts = user_message.split()
        try:
            prod_id, quantidade = int(parts[1]), int(parts[2])
            resposta_final = adicionar_ao_carrinho(sender_number, prod_id, quantidade)
        except (ValueError, IndexError):
            resposta_final = "Formato inválido. Use: `add <ID> <quantidade>` (ex: `add 1 2`)"
    elif user_message_lower in ["carrinho", "ver carrinho"]:
        resposta_final = ver_carrinho(sender_number)
    elif user_message_lower == 'finalizar':
        resposta_final = finalizar_compra(sender_number)
    elif user_message_lower in ["produtos", "ver produtos", "catalogo"]:
        resposta_final = listar_categorias()
    elif user_message_lower in [cat.lower() for cat in ['Chá', 'Chás', 'Suplementos', 'Óleos', 'Veganos', 'Goiabada']]:
        resposta_final = listar_produtos_categoria(user_message_lower)
    else:
        produto_detalhado = buscar_produto_detalhado(user_message)
        if produto_detalhado:
            resposta_final = (f"Encontrei: *{produto_detalhado['nome'].capitalize()}* - R$ {float(produto_detalhado['preco']):.2f}\n"
                              f"_{produto_detalhado['descricao']}_\n\n"
                              f"Para adicionar, use: `add {produto_detalhado['id']} <quantidade>`")
        else:
            resposta_final = get_gpt_response(user_message)

    # Lógica de envio e salvamento
    if resposta_final:
        salvar_conversa(sender_number, user_message, resposta_final)
        try:
            send_whatsapp_message(to_number=sender_number, body=resposta_final)
        except Exception as e:
            print(f"--- AVISO: Falha ao enviar mensagem via Twilio: {e} ---")
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        salvar_conversa(sender_number, user_message, "Erro: Sem resposta gerada.")
        try:
            send_whatsapp_message(to_number=sender_number, body=fallback_message)
        except Exception as e:
            print(f"--- AVISO: Falha ao enviar mensagem de fallback via Twilio: {e} ---")
    
    return "OK", 200


@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

