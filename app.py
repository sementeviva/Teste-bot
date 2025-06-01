import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response, abort
from openai import OpenAI
from datetime import datetime

# Importa o utilitário Twilio centralizado
from utils.twilio_utils import send_whatsapp_message
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho
# IMPORTANTE: A função get_db_connection E salvar_conversa DEVEM SER IMPORTADAS de um módulo centralizado
from utils.db_utils import get_db_connection, salvar_conversa # <--- CORREÇÃO 3: IMPORTA SALVAR_CONVERSA TAMBÉM

# Blueprints
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp # <--- CORREÇÃO 2: IMPORTA O BLUEPRINT DE CONVERSAS
from routes.gerenciar_vendas import gerenciar_vendas_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_upload")

# Registre os blueprints (TODOS eles)
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas") # <--- CORREÇÃO 2: REGISTRA O BLUEPRINT DE CONVERSAS
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

# Variáveis de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
RENDER_BASE_URL = "https://teste-bot-9ppl.onrender.com"  # Seu domínio público do Render
client_openai = OpenAI(api_key=openai_api_key)

# As funções get_db_connection e salvar_conversa foram movidas para utils/db_utils.py (Melhoria 2 e 4)
# Código anterior de get_db_connection e salvar_conversa removido daqui.

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

# Funções renomeadas para refletir o uso do banco de dados (Melhoria 3)
def buscar_produto_no_db(mensagem):
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

def gerar_contexto_do_db():
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
        return None # Importante retornar None em caso de erro

def get_gpt_response(mensagem):
    contexto_produtos = gerar_contexto_do_db()
    prompt = f"""
Você é um assistente virtual de vendas da loja Semente Viva, especializada em produtos naturais.
Seu objetivo é oferecer um atendimento humanizado, simpático e eficiente, guiando o cliente durante toda a jornada de compra.
Funil de Vendas:
- Identifique o estágio do cliente: descoberta, consideração, decisão, pós-venda.
- No início da conversa, descubra as necessidades ou objetivos do cliente com perguntas abertas.
- Apresente produtos relevantes conforme o estágio (ex: para novos clientes, foque em apresentação de categorias e benefícios; para clientes recorrentes, apresente promoções e complementos).
- Sempre convide o cliente a avançar para o próximo passo do funil: olhar produtos, tirar dúvidas, montar o carrinho, fechar a compra.
Carrinho de Compras:
- Ajude o cliente a adicionar, remover e revisar produtos no carrinho.
- Informe sempre que um produto foi adicionado ou removido.
- Permita que ele consulte o carrinho a qualquer momento ("Deseja ver o que já escolheu?").
- Mostre um resumo do carrinho antes do fechamento do pedido (produtos, quantidades, valores).
Fotos dos Produtos:
- Sempre que apresentar ou recomendar um produto, envie também a foto correspondente, se disponível, para ajudar o cliente na escolha.
- Só envie a imagem do produto correspondente ao que está sendo perguntado ou sugerido.
- Utilize a informação abaixo para localizar ou identificar a foto de cada produto e descreva a imagem de forma complementar para ajudar clientes com possíveis limitações visuais.
Diretrizes do atendimento aprimoradas:
1. Sempre utilize linguagem personalizada, cordial e animada.
2. Proponha próximos passos claros conforme o estágio de compra do cliente.
3. Use, sempre que possível, histórico da conversa e preferências para personalizar sugestões.
4. Mantenha respostas diretas, com informações objetivas e relevantes.
5. Demonstre empatia e ofereça ajuda ativa.
6. Nunca solicite dados sensíveis.
7. Encaminhe para atendimento humano caso necessário.
8. Finalize cada atendimento agradecendo e se colocando à disposição para dúvidas ou acompanhamentos futuros.
Catálogo de produtos (com fotos):
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

# =========================
# ROTAS PARA IMAGEM PRODUTO - REMOVIDAS DE APP.PY (Melhoria 1)
# ELAS ESTÃO AGORA APENAS NO BLUEPRINT ver_produtos_bp
# =========================

# =========================
# Webhook WhatsApp
# =========================

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From", "").replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    if not sender_number or not user_message:
        return "Dados insuficientes", 400

    user_message_lower = user_message.lower()

    # Atalhos para menu/carrinho/categoria
    if user_message_lower in ["menu", "ver produtos", "produtos"]:
        resposta_final = listar_categorias()
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        salvar_conversa(sender_number, user_message, resposta_final)
        return "OK", 200

    elif user_message_lower in ["carrinho", "ver carrinho"]:
        resposta_final = ver_carrinho(sender_number)
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        salvar_conversa(sender_number, user_message, resposta_final)
        return "OK", 200

    elif user_message.isdigit():
        resposta_final = adicionar_ao_carrinho(sender_number, int(user_message))
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        salvar_conversa(sender_number, user_message, resposta_final)
        return "OK", 200

    elif user_message_lower in ["chá", "chás", "suplementos", "óleos", "veganos"]:
        resposta_final = listar_produtos_categoria(user_message_lower)
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        salvar_conversa(sender_number, user_message, resposta_final)
        return "OK", 200

    # NOVO: resposta para consultas por produto com envio de imagem
    produto_detalhado = buscar_produto_detalhado(user_message)

    if produto_detalhado:
        resposta_final = (
            f"{produto_detalhado['nome'].capitalize()} - R$ {produto_detalhado['preco']}\n"
            f"{produto_detalhado['descricao']}\n"
            "Confira a imagem do produto abaixo." if produto_detalhado["tem_imagem"] else ""
        )
        if produto_detalhado["tem_imagem"]:
            # A URL da imagem agora aponta para o Blueprint ver_produtos_bp
            img_url = f"{RENDER_BASE_URL}/ver_produtos/imagem/{produto_detalhado['id']}"
            send_whatsapp_message(
                to_number=sender_number,
                body=resposta_final,
                media_url=img_url
            )
        else:
            send_whatsapp_message(
                to_number=sender_number,
                body=resposta_final
            )
        salvar_conversa(sender_number, user_message, resposta_final)
        return "OK", 200

    # Caso não encontre produto, segue fluxo padrão com busca por nome ou IA
    resposta_db = buscar_produto_no_db(user_message)
    if resposta_db:
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_db
        )
        resposta_final = resposta_db
    else:
        resposta_final = get_gpt_response(user_message)
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )

    salvar_conversa(sender_number, user_message, resposta_final)
    return "OK", 200

# <--- CORREÇÃO 1: ROTA /conversas REMOVIDA DE APP.PY
# Ela agora é gerenciada EXCLUSIVAMENTE pelo Blueprint ver_conversas_bp em routes/ver_conversas.py
# @app.route("/conversas", methods=["GET", "POST"])
# def ver_conversas():
#     # ... (código removido) ...

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
