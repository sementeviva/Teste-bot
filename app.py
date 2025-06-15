import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response
# ATUALIZADO: Garanta que este import está presente
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from datetime import datetime

# Importa utilitários e Blueprints
from utils.twilio_utils import send_whatsapp_message
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho, finalizar_compra
from utils.db_utils import get_db_connection, salvar_conversa
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_padrao_dev")

# Registra os blueprints
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

# Variáveis de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)

# Funções de DB e OpenAI (sem alterações)
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
    if len(mensagem.strip()) < 3:
        return None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, nome, preco, descricao FROM produtos WHERE LOWER(nome) ILIKE %s AND ativo = TRUE LIMIT 1",
            (f"%{mensagem.lower()}%",)
        )
        produto = cur.fetchone()
        cur.close()
        conn.close()
        return produto
    except Exception as e:
        print(f"Erro buscar produto detalhado: {e}")
        return None

def get_gpt_response(mensagem):
    df = carregar_produtos_db()
    contextos = []
    for _, row in df.iterrows():
        contexto = f"ID {row['id']}: {row['nome'].capitalize()} - R$ {row['preco']:.2f} - {row['descricao']}"
        contextos.append(contexto)
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
        messages=[
            {"role": "system", "content": "Responda sempre em português com educação e clareza."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From", "").replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    user_message_lower = user_message.lower()

    if not sender_number or not user_message:
        return "Dados insuficientes", 400

    # --- INÍCIO DA LÓGICA "LIGA/DESLIGA" (REVISADA) ---
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # DEBUG: Log para ver o número que estamos procurando
            print(f"--- DEBUG: Verificando modo para o contato: '{sender_number}' ---")

            cur.execute(
                "SELECT modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1",
                (sender_number,)
            )
            venda_ativa = cur.fetchone()

            if venda_ativa:
                modo_atual = venda_ativa['modo_atendimento']
                # DEBUG: Log para ver o que foi encontrado no banco
                print(f"--- DEBUG: Encontrada conversa ativa. Modo: '{modo_atual}' ---")
                
                if modo_atual == 'manual':
                    print(f"--- INFO: Modo manual confirmado para '{sender_number}'. Bot silenciado. ---")
                    salvar_conversa(sender_number, user_message, "--- MENSAGEM RECEBIDA EM MODO MANUAL ---")
                    conn.close() # Fechamos a conexão antes de sair
                    return "OK", 200
            else:
                # DEBUG: Log para o caso de não encontrar conversa ativa
                print(f"--- DEBUG: Nenhuma conversa ativa encontrada para '{sender_number}'. Modo padrão: 'bot'. ---")
    
    except Exception as e:
        print(f"--- ERRO: Falha ao verificar modo de atendimento: {e} ---")
    finally:
        if conn:
            conn.close()
    # --- FIM DA LÓGICA ---

    # Se o código chegou aqui, o modo é 'bot'. A lógica original continua.
    print(f"--- INFO: '{sender_number}' em modo bot. Processando mensagem... ---")
    
    resposta_final = ""

    if user_message_lower in ["oi", "olá", "ola", "oi tudo bem", "menu", "começar", "iniciar"]:
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

    if resposta_final:
        send_whatsapp_message(to_number=sender_number, body=resposta_final)
        salvar_conversa(sender_number, user_message, resposta_final)
    else:
        fallback_message = "Desculpe, não entendi. Digite 'menu' para ver as opções."
        send_whatsapp_message(to_number=sender_number, body=fallback_message)
        salvar_conversa(sender_number, user_message, "Erro: Sem resposta gerada.")

    return "OK", 200

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

