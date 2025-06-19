# Teste-bot-main/app.py

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
# ATUALIZADO: Importa a função correta
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_sid


# --- CONFIGURAÇÃO DA APLICAÇÃO E LOGIN (código inalterado) ---
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
                is_admin=user_data.get('is_admin', False)
            )
        return None
    finally:
        if conn: conn.close()

# --- REGISTO DOS BLUEPRINTS (código inalterado) ---
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(treinamento_bot_bp, url_prefix="/treinamento")
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

# --- VARIÁVEIS GLOBAIS E CLIENTES DE API (código inalterado) ---
openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)

# --- FUNÇÕES AUXILIARES (código inalterado) ---
def carregar_produtos_db(conta_id):
    # ... (código existente)
    pass
def buscar_produto_detalhado(conta_id, mensagem):
    # ... (código existente)
    pass
def get_gpt_response(conta_id, mensagem):
    # ... (código existente)
    pass

# --- WEBHOOK PRINCIPAL DO WHATSAPP (LÓGICA ATUALIZADA) ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # 1. Obter dados da mensagem
    sender_number_with_prefix = request.form.get("From", "")
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    
    # O número da sua empresa que recebeu a mensagem (será o remetente da resposta)
    to_number = request.form.get("To", "")
    
    # **NOVO**: O SID da subconta que recebeu a mensagem.
    # Se a mensagem for para a conta principal, será o SID principal.
    account_sid = request.form.get("AccountSid")

    if not all([sender_number, user_message, to_number, account_sid]):
        print("AVISO: Webhook recebido com dados insuficientes (From, Body, To ou AccountSid).")
        return "Dados insuficientes", 200

    # 2. Identificar a conta do cliente (LÓGICA ATUALIZADA)
    conta_id = get_conta_id_from_sid(account_sid)
    
    if not conta_id:
        # Se nenhuma conta for encontrada para o SID, não há como prosseguir.
        print(f"ERRO CRÍTICO: Nenhuma conta encontrada para o AccountSid '{account_sid}'. O webhook não pode ser processado.")
        return "OK", 200

    print(f"INFO: Mensagem recebida de '{sender_number}' para a Conta ID: {conta_id} (SID: '{account_sid}')")

    # O restante do código (passos 3, 4, 5, 6) permanece o mesmo,
    # pois já está corretamente parametrizado com 'conta_id'.
    # A única mudança é no final, ao chamar send_whatsapp_message.

    # 3. Lógica do Sandbox ... (inalterada)
    # 4. Lógica de Atendimento Manual ... (inalterada)
    # 5. Lógica de Resposta do Bot ... (inalterada)
    # ... (aqui vai toda a sua lógica de if/elif/else para gerar a `resposta_final`)
    resposta_final = "" # Substitua pela sua lógica
    user_message_lower = user_message.lower()
    if user_message_lower == 'menu': # Exemplo
        resposta_final = "Este é o menu..."
    else:
        resposta_final = "Não entendi, digite menu."

    # 6. Envio e Salvamento Final (LÓGICA ATUALIZADA)
    if resposta_final:
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)
        try:
            # Passamos conta_id para que a função de envio possa usar as credenciais corretas.
            # Passamos to_number para que a resposta venha do número certo.
            send_whatsapp_message(
                to_number=sender_number,
                from_number=to_number,
                body=resposta_final,
                conta_id=conta_id
            )
        except Exception as e:
            print(f"AVISO: Falha ao enviar via Twilio para conta {conta_id}: {e}")
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        salvar_conversa(conta_id, sender_number, user_message, "Erro: Sem resposta gerada.")
        try:
            send_whatsapp_message(
                to_number=sender_number,
                from_number=to_number,
                body=fallback_message,
                conta_id=conta_id
            )
        except Exception as e:
            print(f"AVISO: Falha ao enviar fallback via Twilio para conta {conta_id}: {e}")

    return "OK", 200


# --- ROTA PRINCIPAL E EXECUÇÃO (código inalterado) ---
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

