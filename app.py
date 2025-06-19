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
# ATUALIZADO: Importa a função de carregar configs
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_sid, get_bot_config


# --- CONFIGURAÇÃO DA APLICAÇÃO E LOGIN (código inalterado) ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_secreta_muito_forte_e_dificil")
# ... (resto da configuração do LoginManager e Blueprints inalterado) ...
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
    try:
        conn = get_db_connection()
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
        cur.execute("SELECT id, nome, preco, descricao FROM produtos WHERE LOWER(nome) ILIKE %s AND ativo = TRUE AND conta_id = %s LIMIT 1", (f"%{mensagem.lower()}%", conta_id))
        produto = cur.fetchone()
        cur.close()
        return produto
    except Exception as e:
        print(f"Erro buscar produto detalhado para conta {conta_id}: {e}")
        return None
    finally:
        if conn: conn.close()

# --- ATUALIZADO: get_gpt_response agora usa as configs do bot ---
def get_gpt_response(conta_id, mensagem, config):
    df_produtos = carregar_produtos_db(conta_id)
    if df_produtos.empty:
        return "Desculpe, não tenho informações sobre os produtos no momento."

    lista_produtos = "\n".join([f"- {row['nome']} (ID: {row['id']}): R$ {row['preco']:.2f}. Descrição: {row['descricao']}" for _, row in df_produtos.iterrows()])

    # Constrói o prompt com base nas configurações personalizadas do bot
    prompt = f"""
        Você é '{config.get('nome_assistente', 'Assistente')}', o assistente de vendas da loja '{config.get('nome_loja_publico', 'nossa loja')}'.
        
        Siga estas diretrizes de personalidade: {config.get('diretriz_principal_prompt', 'Seja prestativo e amigável.')}

        Aqui estão informações importantes sobre a loja:
        - Endereço: {config.get('endereco', 'não informado')}
        - Horário de funcionamento: {config.get('horario_funcionamento', 'não informado')}
        - Conhecimento adicional: {config.get('conhecimento_especifico', 'Nenhum.')}

        Produtos disponíveis:
        {lista_produtos}

        Sua tarefa é responder à pergunta do cliente de forma breve, útil e seguindo a personalidade definida.
        Não invente produtos ou informações. Se não souber a resposta, diga que vai verificar com um atendente.
        
        Pergunta do cliente: "{mensagem}"
    """
    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao chamar a API da OpenAI para conta {conta_id}: {e}")
        return "Não consegui processar sua solicitação no momento. Tente novamente mais tarde."


# --- WEBHOOK PRINCIPAL DO WHATSAPP (LÓGICA ATUALIZADA) ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # 1. Obter dados da mensagem
    sender_number_with_prefix = request.form.get("From", "")
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    to_number = request.form.get("To", "")
    account_sid = request.form.get("AccountSid")

    if not all([sender_number, user_message, to_number, account_sid]):
        print("AVISO: Webhook recebido com dados insuficientes.")
        return "Dados insuficientes", 200

    # 2. Identificar a conta e carregar suas configurações
    conta_id = get_conta_id_from_sid(account_sid)
    if not conta_id:
        print(f"ERRO CRÍTICO: Nenhuma conta encontrada para o AccountSid '{account_sid}'.")
        return "OK", 200
        
    # **NOVO**: Carrega as configurações específicas do bot para esta conta
    bot_config = get_bot_config(conta_id)
    print(f"INFO: Mensagem de '{sender_number}' para Conta ID: {conta_id}. Configs do bot carregadas.")

    # 3. Lógica do Sandbox de Desenvolvimento (inalterada)
    # ...

    # 4. Lógica de Atendimento Manual (inalterada)
    # ...

    # 5. Lógica de Resposta do Bot (ATUALIZADA)
    resposta_final = ""
    user_message_lower = user_message.lower()

    # --- INÍCIO DA LÓGICA DE RESPOSTA ---
    # Passo 5.1: Verificar se é uma pergunta do FAQ
    if bot_config.get('faq_list'):
        for faq_item in bot_config['faq_list']:
            # Compara a pergunta do usuário (em minúsculas) com a pergunta do FAQ
            if user_message_lower == faq_item.get('question', '').lower():
                resposta_final = faq_item.get('answer')
                print(f"INFO: Mensagem correspondeu a uma pergunta do FAQ para conta {conta_id}.")
                break # Encontrou a resposta, sai do loop
    
    # Se não encontrou no FAQ, continua a lógica normal
    if not resposta_final:
        PALAVRAS_CHAVE_ALERTA = ['ajuda', 'atendente', 'humano', 'problema', 'reclamação']
        if any(palavra in user_message_lower for palavra in PALAVRAS_CHAVE_ALERTA):
            resposta_final = "Entendido. Um de nossos atendentes entrará em contato em breve. Por favor, aguarde."
        
        elif user_message_lower in ["oi", "olá", "ola", "menu", "começar"]:
            # **NOVO**: Usa a saudação personalizada do painel
            resposta_final = bot_config.get('saudacao_personalizada', "Olá! Bem-vindo(a)! Como posso ajudar?")
            resposta_final += "\n\nComandos: `produtos`, `carrinho`, `finalizar`."

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
            categorias = listar_categorias(conta_id)
            if categorias:
                resposta_final = "Estas são as nossas categorias de produtos:\n" + "\n".join([f"- {cat}" for cat in categorias])
                resposta_final += "\n\nDigite o nome de uma categoria para ver os produtos."
            else:
                resposta_final = "Nenhum produto cadastrado no momento."

        elif any(user_message_lower == cat.lower() for cat in listar_categorias(conta_id)):
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
                # **NOVO**: Passa as configurações do bot para a função da OpenAI
                resposta_final = get_gpt_response(conta_id, user_message, bot_config)
    # --- FIM DA LÓGICA DE RESPOSTA ---

    # 6. Envio e Salvamento Final (inalterado)
    if resposta_final:
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)
        try:
            send_whatsapp_message(to_number=sender_number, from_number=to_number, body=resposta_final, conta_id=conta_id)
        except Exception as e:
            print(f"AVISO: Falha ao enviar via Twilio para conta {conta_id}: {e}")
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        salvar_conversa(conta_id, sender_number, user_message, "Erro: Sem resposta gerada.")
        try:
            send_whatsapp_message(to_number=sender_number, from_number=to_number, body=fallback_message, conta_id=conta_id)
        except Exception as e:
            print(f"AVISO: Falha ao enviar fallback via Twilio para conta {conta_id}: {e}")

    return "OK", 200


# --- ROTA PRINCIPAL E EXECUÇÃO (código inalterado) ---
@app.route("/")
def home():
    # Esta rota deve ser protegida por @login_required se for um painel
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

                                       
