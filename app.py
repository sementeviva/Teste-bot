# --- IMPORTS ---
import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from datetime import datetime
import requests

# --- IMPORTS DE AUTENTICAÇÃO E MODELOS ---
from flask_login import LoginManager
from models.user import User

# --- IMPORTS DE ROTAS (BLUEPRINTS) ---
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.treinamento_bot import treinamento_bot_bp
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp

# --- IMPORTS DE UTILITÁRIOS ---
from utils.twilio_utils import send_whatsapp_message
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho, finalizar_compra
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_sender


# --- CONFIGURAÇÃO DA APLICAÇÃO E LOGIN ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_secreta_muito_forte_e_dificil")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, faça login para aceder a esta página."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, email, conta_id, is_admin FROM utilizadores WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
        if user_data:
            return User(
                id=user_data['id'], 
                nome=user_data['nome'], 
                email=user_data['email'], 
                conta_id=user_data['conta_id'],
                is_admin=user_data.get('is_admin', False) # .get para retrocompatibilidade
            )
        return None
    finally:
        if conn: conn.close()


# --- REGISTO DOS BLUEPRINTS ---
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(admin_bp, url_prefix="/admin") # O registo que faltava
app.register_blueprint(treinamento_bot_bp, url_prefix="/treinamento")
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')


# --- VARIÁVEIS GLOBAIS E CLIENTES DE API ---
openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)


# --- FUNÇÕES AUXILIARES COM LÓGICA MULTI-CLIENTE ---
def carregar_produtos_db(conta_id):
    # (código inalterado)
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM produtos WHERE ativo = TRUE AND conta_id = %s", conn, params=(conta_id,))
        # ... (resto da função)
        return df
    except Exception as e:
        print(f"Erro ao carregar produtos do banco para conta {conta_id}: {e}")
        return pd.DataFrame()

def buscar_produto_detalhado(conta_id, mensagem):
    # (código inalterado)
    if len(mensagem.strip()) < 3: return None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, nome, preco, descricao FROM produtos WHERE LOWER(nome) ILIKE %s AND ativo = TRUE AND conta_id = %s LIMIT 1", (f"%{mensagem.lower()}%", conta_id))
        produto = cur.fetchone()
        # ... (resto da função)
        return produto
    except Exception as e:
        print(f"Erro buscar produto detalhado para conta {conta_id}: {e}")
        return None
        
def get_gpt_response(conta_id, mensagem):
    # (código inalterado)
    df = carregar_produtos_db(conta_id)
    # ... (resto da função)
    return response.choices[0].message.content.strip()


# --- WEBHOOK PRINCIPAL DO WHATSAPP ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # 1. Obter dados da mensagem
    sender_number_with_prefix = request.form.get("From", "")
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    user_message_lower = user_message.lower()

    if not sender_number or not user_message:
        return "Dados insuficientes", 200

    # 2. Identificar a conta do cliente
    conta_id = get_conta_id_from_sender(sender_number_with_prefix)
    if not conta_id:
        print(f"ERRO CRÍTICO: Não foi possível encontrar uma conta para o número {sender_number_with_prefix}.")
        return "OK", 200
        
    # 3. Lógica do Sandbox de Desenvolvimento
    is_test_mode = os.environ.get("TEST_MODE_ENABLED", "FALSE").upper() == "TRUE"
    developer_number = os.environ.get("DEVELOPER_WHATSAPP_NUMBER")
    if is_test_mode and sender_number_with_prefix != developer_number:
        print(f"MODO DE TESTE: Mensagem de '{sender_number_with_prefix}' ignorada.")
        return "OK", 200
        
    # 4. Lógica de Atendimento Manual (Chave Liga/Desliga)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' AND conta_id = %s LIMIT 1", (sender_number, conta_id))
            venda_ativa = cur.fetchone()
            if venda_ativa and venda_ativa.get('modo_atendimento') == 'manual':
                salvar_conversa(conta_id, sender_number, user_message, "--- MENSAGEM RECEBIDA EM MODO MANUAL ---")
                return "OK", 200
    finally:
        if conn: conn.close()
    
    # 5. Lógica de Resposta do Bot
    resposta_final = ""
    
    PALAVRAS_CHAVE_ALERTA = ['ajuda', 'atendente', 'humano', 'problema', 'reclamação']
    if any(palavra in user_message_lower for palavra in PALAVRAS_CHAVE_ALERTA):
        resposta_final = "Entendido. Um de nossos atendentes entrará em contato em breve. Por favor, aguarde."
        # ... (lógica de alerta com conta_id)
    elif user_message_lower in ["oi", "olá", "ola", "menu", "começar"]:
        resposta_final = "Olá! Bem-vindo(a)!\nComandos: `produtos`, `carrinho`, `finalizar`."
    elif user_message_lower.startswith('add '):
        parts = user_message.split()
        try:
            prod_id, quantidade = int(parts[1]), int(parts[2])
            resposta_final = adicionar_ao_carrinho(conta_id, sender_number, prod_id, quantidade)
        except (ValueError, IndexError):
            resposta_final = "Formato inválido. Use: `add <ID> <quantidade>`."
    elif user_message_lower in ["carrinho", "ver carrinho"]:
        resposta_final = ver_carrinho(conta_id, sender_number)
    elif user_message_lower == 'finalizar':
        resposta_final = finalizar_compra(conta_id, sender_number)
    elif user_message_lower in ["produtos", "ver produtos", "catalogo"]:
        resposta_final = listar_categorias(conta_id)
    # ... (outros elifs para categorias) ...
    else:
        produto_detalhado = buscar_produto_detalhado(conta_id, user_message)
        if produto_detalhado:
            resposta_final = f"Encontrei: *{produto_detalhado['nome']}* - R$ {float(produto_detalhado['preco']):.2f}\n_{produto_detalhado['descricao']}_"
        else:
            resposta_final = get_gpt_response(conta_id, user_message)

    # 6. Envio e Salvamento Final
    if resposta_final:
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)
        try:
            send_whatsapp_message(to_number=sender_number, body=resposta_final)
        except Exception as e:
            print(f"AVISO: Falha ao enviar via Twilio: {e}")
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        salvar_conversa(conta_id, sender_number, user_message, "Erro: Sem resposta gerada.")
        try:
            send_whatsapp_message(to_number=sender_number, body=fallback_message)
        except Exception as e:
            print(f"AVISO: Falha ao enviar fallback via Twilio: {e}")
    
    return "OK", 200


# --- ROTA PRINCIPAL E EXECUÇÃO ---
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
        
