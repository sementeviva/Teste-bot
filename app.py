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
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_number


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
                is_admin=user_data.get('is_admin', False)
            )
        return None
    finally:
        if conn: conn.close()


# --- REGISTO DOS BLUEPRINTS ---
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(treinamento_bot_bp, url_prefix="/treinamento")
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')


# --- VARIÁVEIS GLOBAIS E CLIENTES DE API ---
openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)


# --- FUNÇÕES AUXILIARES (inalteradas) ---
def carregar_produtos_db(conta_id):
    try:
        conn = get_db_connection()
        # A query já era multi-inquilino, usando conta_id.
        df = pd.read_sql("SELECT * FROM produtos WHERE ativo = TRUE AND conta_id = %s", conn, params=(conta_id,))
        return df
    except Exception as e:
        print(f"Erro ao carregar produtos do banco para conta {conta_id}: {e}")
        return pd.DataFrame()

def buscar_produto_detalhado(conta_id, mensagem):
    if len(mensagem.strip()) < 3: return None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # A query já era multi-inquilino, usando conta_id.
        cur.execute("SELECT id, nome, preco, descricao FROM produtos WHERE LOWER(nome) ILIKE %s AND ativo = TRUE AND conta_id = %s LIMIT 1", (f"%{mensagem.lower()}%", conta_id))
        produto = cur.fetchone()
        cur.close()
        return produto
    except Exception as e:
        print(f"Erro buscar produto detalhado para conta {conta_id}: {e}")
        return None
    finally:
        if conn: conn.close()

def get_gpt_response(conta_id, mensagem):
    df = carregar_produtos_db(conta_id)
    if df.empty:
        return "Desculpe, não tenho informações sobre os produtos no momento."

    lista_produtos = "\n".join([f"- {row['nome']} (R$ {row['preco']:.2f})" for _, row in df.iterrows()])
    prompt = f"""
        Você é um assistente de vendas da loja.
        Seja breve e direto.

        Produtos disponíveis:
        {lista_produtos}

        Pergunta do cliente: "{mensagem}"
        """
    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao chamar a API da OpenAI: {e}")
        return "Não consegui processar sua solicitação no momento. Tente novamente mais tarde."


# --- WEBHOOK PRINCIPAL DO WHATSAPP (LÓGICA ATUALIZADA) ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # 1. Obter dados da mensagem
    # O número do cliente que enviou a mensagem
    sender_number_with_prefix = request.form.get("From", "")
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    
    # **NOVO**: O número da sua conta Twilio que RECEBEU a mensagem
    to_number = request.form.get("To", "")

    if not sender_number or not user_message or not to_number:
        print("AVISO: Webhook recebido com dados insuficientes (From, Body ou To).")
        return "Dados insuficientes", 200

    # 2. Identificar a conta do cliente (LÓGICA ATUALIZADA)
    # Agora usamos o número de destino para encontrar a conta correta.
    conta_id = get_conta_id_from_number(to_number)
    if not conta_id:
        # Se nenhuma conta for encontrada para o número de destino, não há como prosseguir.
        print(f"ERRO CRÍTICO: Nenhuma conta encontrada para o número Twilio '{to_number}'. O webhook não pode ser processado.")
        # Não enviamos resposta, pois não sabemos de qual empresa se trata.
        return "OK", 200

    print(f"INFO: Mensagem recebida de '{sender_number}' para a Conta ID: {conta_id} (Número Twilio: '{to_number}')")

    # 3. Lógica do Sandbox de Desenvolvimento (inalterada)
    is_test_mode = os.environ.get("TEST_MODE_ENABLED", "FALSE").upper() == "TRUE"
    developer_number = os.environ.get("DEVELOPER_WHATSAPP_NUMBER")
    if is_test_mode and sender_number_with_prefix != developer_number:
        print(f"MODO DE TESTE: Mensagem de '{sender_number_with_prefix}' ignorada.")
        return "OK", 200

    # 4. Lógica de Atendimento Manual (Chave Liga/Desliga) (inalterada)
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

    # 5. Lógica de Resposta do Bot (inalterada, pois já recebe conta_id)
    resposta_final = ""
    user_message_lower = user_message.lower()
    
    PALAVRAS_CHAVE_ALERTA = ['ajuda', 'atendente', 'humano', 'problema', 'reclamação']
    if any(palavra in user_message_lower for palavra in PALAVRAS_CHAVE_ALERTA):
        resposta_final = "Entendido. Um de nossos atendentes entrará em contato em breve. Por favor, aguarde."
        # Aqui, no futuro, pode haver uma lógica de notificação para o dono da loja (conta_id).
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
        # A função `listar_categorias` precisa ser chamada.
        # Vamos construir a resposta aqui mesmo.
        categorias = listar_categorias(conta_id)
        if categorias:
            resposta_final = "Estas são as nossas categorias de produtos:\n" + "\n".join([f"- {cat}" for cat in categorias])
            resposta_final += "\n\nDigite o nome de uma categoria para ver os produtos."
        else:
            resposta_final = "Nenhum produto cadastrado no momento."
    # Verifica se a mensagem é uma categoria exata
    elif listar_categorias(conta_id) and user_message_lower in [c.lower() for c in listar_categorias(conta_id)]:
        produtos = listar_produtos_categoria(conta_id, user_message)
        if produtos:
            resposta_final = f"Produtos em *{user_message}*:\n"
            for p in produtos:
                resposta_final += f"ID: {p['id']} - *{p['nome']}* - R$ {float(p['preco']):.2f}\n"
            resposta_final += "\nPara adicionar, use: `add <ID> <quantidade>`"
        else:
            resposta_final = f"Nenhum produto encontrado na categoria {user_message}."
    else:
        produto_detalhado = buscar_produto_detalhado(conta_id, user_message)
        if produto_detalhado:
            resposta_final = f"Encontrei: *{produto_detalhado['nome']}* - R$ {float(produto_detalhado['preco']):.2f}\n_{produto_detalhado['descricao']}_"
        else:
            resposta_final = get_gpt_response(conta_id, user_message)

    # 6. Envio e Salvamento Final (inalterada)
    if resposta_final:
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)
        try:
            send_whatsapp_message(to_number=sender_number, from_number=to_number, body=resposta_final)
        except Exception as e:
            print(f"AVISO: Falha ao enviar via Twilio: {e}")
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        salvar_conversa(conta_id, sender_number, user_message, "Erro: Sem resposta gerada.")
        try:
            send_whatsapp_message(to_number=sender_number, from_number=to_number, body=fallback_message)
        except Exception as e:
            print(f"AVISO: Falha ao enviar fallback via Twilio: {e}")

    return "OK", 200


# --- ROTA PRINCIPAL E EXECUÇÃO ---
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

