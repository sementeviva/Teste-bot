# Teste-bot-main/app.py

# --- IMPORTS ---
import os
from flask import Flask, request
from psycopg2.extras import RealDictCursor
from openai import OpenAI

# --- NOSSOS IMPORTS ---
from models.user import User
from routes.auth import auth_bp
# ... (todos os outros imports de rotas)
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_sid, get_bot_config
from utils.fluxo_vendas import adicionar_ao_carrinho
# NOVO: Importa os gestores de telas
import utils.view_handlers as views

# --- CONFIGURAÇÃO DA APLICAÇÃO (inalterada) ---
app = Flask(__name__)
# ... (código de configuração e blueprints inalterado)

# --- WEBHOOK PRINCIPAL REESTRUTURADO ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # 1. Obter dados e identificar a conta (inalterado)
    form_data = request.form.to_dict()
    sender_number = form_data.get("From")
    to_number = form_data.get("To")
    account_sid = form_data.get("AccountSid")
    
    if not all([sender_number, to_number, account_sid]):
        return "OK", 200

    conta_id = get_conta_id_from_sid(account_sid)
    if not conta_id:
        print(f"ERRO CRÍTICO: Nenhuma conta para o SID {account_sid}")
        return "OK", 200

    # 2. Analisar o tipo de mensagem: Botão, Lista ou Texto
    button_payload = form_data.get("ButtonPayload")
    list_reply_id = form_data.get("List-Reply-Id")
    user_message_body = form_data.get("Body", "").strip()

    # Guarda a interação inicial no banco (opcional, pode ser movido para o fim)
    # salvar_conversa(conta_id, sender_number, user_message_body or f"Clique: {button_payload or list_reply_id}", "...")

    # 3. Controlador de Fluxo: Direciona para a ação correta
    
    # --- AÇÃO: CLIQUE EM BOTÃO DE RESPOSTA ---
    if button_payload:
        if button_payload == 'view_categories':
            views.send_categories_view(conta_id, sender_number, to_number)
        
        elif button_payload == 'talk_to_human':
            views.send_talk_to_human_view(conta_id, sender_number, to_number)
        
        elif button_payload.startswith('add_cart_'):
            product_id = button_payload.replace('add_cart_', '')
            # Adiciona 1 unidade por padrão. Fase 2 pode perguntar a quantidade.
            resposta = adicionar_ao_carrinho(conta_id, sender_number.replace('whatsapp:',''), int(product_id), 1)
            views.send_text(sender_number, to_number, f"✅ {resposta}", conta_id)
        
        # Adicionar outras lógicas de botão aqui (ex: more_details_)
        
    # --- AÇÃO: SELEÇÃO EM LISTA ---
    elif list_reply_id:
        if list_reply_id.startswith('category_'):
            category_name = list_reply_id.replace('category_', '')
            views.send_products_from_category_view(conta_id, sender_number, to_number, category_name)
        
        # Adicionar outras lógicas de lista aqui (ex: faq_)

    # --- AÇÃO: MENSAGEM DE TEXTO LIVRE ---
    elif user_message_body:
        # Palavras-chave para (re)iniciar a conversa
        greetings = ["oi", "olá", "ola", "menu", "começar", "bom dia", "boa tarde", "boa noite"]
        if user_message_body.lower() in greetings:
            views.send_initial_view(conta_id, sender_number, to_number)
        else:
            # TODO FASE 2: Implementar FAQ e chamada à IA aqui
            # Por agora, um fallback simples
            bot_config = get_bot_config(conta_id)
            fallback_text = bot_config.get('fallback_message', "Desculpe, não entendi. Use os botões para navegar ou digite 'Menu' para recomeçar.")
            views.send_text(sender_number, to_number, fallback_text, conta_id)
            
    return "OK", 200

# O resto do seu app.py (rotas do painel, etc.) continua aqui...
# (Omitido por brevidado, mas deve ser mantido no seu ficheiro)

