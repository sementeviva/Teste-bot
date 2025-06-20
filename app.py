# Teste-bot-main/app.py

import os
from flask import Flask, request, render_template
from flask_login import LoginManager, login_required
from psycopg2.extras import RealDictCursor
from models.user import User
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.treinamento_bot import treinamento_bot_bp
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp
from utils.db_utils import get_db_connection, get_conta_id_from_sid, get_bot_config, get_last_bot_message
from utils.fluxo_vendas import adicionar_ao_carrinho
import utils.view_handlers as views
from utils.twilio_utils import send_text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_secreta_muito_forte_e_dificil")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, email, conta_id, is_admin FROM utilizadores WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
        if user_data:
            return User(id=user_data['id'], nome=user_data['nome'], email=user_data['email'], conta_id=user_data['conta_id'], is_admin=user_data.get('is_admin', False))
        return None
    except Exception as e:
        print(f"Erro ao carregar utilizador (ID: {user_id}): {e}")
        return None
    finally:
        if conn: conn.close()

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(treinamento_bot_bp, url_prefix="/treinamento")
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    form_data = request.form.to_dict()
    sender_number = form_data.get("From")
    to_number = form_data.get("To")
    account_sid = form_data.get("AccountSid")
    
    if not all([sender_number, to_number, account_sid]): return "OK", 200

    conta_id = get_conta_id_from_sid(account_sid)
    if not conta_id: return "OK", 200

    # Twilio envia o payload de botões em 'ButtonText' quando é uma resposta de Quick Reply
    button_payload_text = form_data.get("ButtonText", "").lower() 
    button_payload_id = form_data.get("ButtonPayload")
    list_reply_id = form_data.get("List-Reply-Id")
    user_message_body = form_data.get("Body", "").strip()

    if button_payload_id:
        # A nova API de botões envia o ID aqui
        payload = button_payload_id
    elif list_reply_id:
        payload = list_reply_id
    else:
        payload = None

    if payload:
        if payload == 'view_categories':
            views.send_categories_view(conta_id, sender_number, to_number)
        elif payload == 'talk_to_human':
            views.send_talk_to_human_view(conta_id, sender_number, to_number)
        elif payload.startswith('add_cart_'):
            product_id = payload.replace('add_cart_', '')
            resposta = adicionar_ao_carrinho(conta_id, sender_number.replace('whatsapp:',''), int(product_id), 1)
            send_text(sender_number, to_number, f"✅ {resposta}", conta_id)
        elif payload.startswith('category_'):
            category_name = payload.replace('category_', '')
            views.send_products_from_category_view(conta_id, sender_number, to_number, category_name)
    
    elif user_message_body:
        greetings = ["oi", "olá", "ola", "menu", "começar", "bom dia", "boa tarde", "boa noite"]
        if user_message_body.lower() in greetings:
            views.send_initial_view(conta_id, sender_number, to_number)
        else:
            # TODO FASE 2: Aqui entrará a lógica de FAQ e IA
            bot_config = get_bot_config(conta_id)
            fallback_text = "Desculpe, não entendi. Use os botões para navegar ou digite 'Menu' para recomeçar."
            send_text(sender_number, to_number, fallback_text, conta_id)
            
    return "OK", 200

@app.route("/")
@login_required
def home():
    return render_template("index.html")

