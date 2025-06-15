import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response, abort
from openai import OpenAI
from datetime import datetime
import json

# Importa o utilitário Twilio centralizado
from utils.twilio_utils import send_whatsapp_message
# ATUALIZADO: Importe as novas funções do fluxo de vendas
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho, finalizar_compra
# IMPORTANTE: A função get_db_connection E salvar_conversa DEVEM SER IMPORTADAS de um módulo centralizado
from utils.db_utils import get_db_connection, salvar_conversa, get_last_bot_message

# Blueprints
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_padrao_dev")

# Registre os blueprints
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

# Variáveis de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
RENDER_BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
client_openai = OpenAI(api_key=openai_api_key)

# Funções de DB e OpenAI (sem alterações significativas)
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
        return pd.DataFrame(columns=["nome", "descricao", "preco", "categoria"])

def gerar_contexto_do_db():
    df = carregar_produtos_db()
    contextos = []
    for _, row in df.iterrows():
        contexto = f"ID {row['id']}: {row['nome'].capitalize()} - R$ {row['preco']:.2f} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

# NOVA FUNÇÃO: Usa o GPT para entender a intenção e o estado do usuário
def get_user_state_and_intent(sender_number, user_message):
    """
    Analisa a mensagem do usuário para determinar sua intenção e o estado atual da conversa.
    """
    last_bot_message = get_last_bot_message(sender_number) or "Nenhuma conversa anterior."
    
    prompt = f"""
    Analise a conversa e retorne um objeto JSON com a 'intenção' do usuário e o 'estado_da_conversa' atual.

    Intenções possíveis:
    - 'saudacao': O usuário está apenas começando a conversa (oi, olá, bom dia).
    - 'ver_produtos': O usuário quer ver produtos, categorias ou o catálogo.
    - 'adicionar_ao_carrinho': O usuário expressa desejo de adicionar um item (ex: "quero o item 5", "adicione 2 do item 10").
    - 'ver_carrinho': O usuário quer ver o que já escolheu.
    - 'finalizar_compra': O usuário quer pagar ou fechar o pedido.
    - 'pergunta_geral': O usuário está fazendo uma pergunta sobre um produto ou qualquer outra coisa.
    - 'intencao_desconhecida': Não foi possível determinar a intenção.

    Estados da Conversa possíveis:
    - 'inicio': Começo da interação.
    - 'navegando_produtos': Usuário está vendo o catálogo ou categorias.
    - 'gerenciando_carrinho': Usuário está adicionando itens ou vendo o carrinho.
    - 'finalizando': Usuário está no processo de fechar o pedido.
    
    Exemplo de análise:
    - Última mensagem do Bot: "Temos produtos nas categorias: Chás, Suplementos..."
    - Mensagem do Usuário: "chás"
    - JSON de saída: {{"intenção": "ver_produtos", "estado_da_conversa": "navegando_produtos", "parametros": {{"categoria": "chás"}}}}

    - Última mensagem do Bot: "Produtos na categoria 'Suplementos': ..."
    - Mensagem do Usuário: "quero adicionar 2 do item 5"
    - JSON de saída: {{"intenção": "adicionar_ao_carrinho", "estado_da_conversa": "gerenciando_carrinho", "parametros": {{"id_produto": 5, "quantidade": 2}}}}
    
    --- CONVERSA ATUAL ---
    Última mensagem do Bot: "{last_bot_message}"
    Mensagem do Usuário: "{user_message}"

    JSON de saída:
    """

    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Você é um assistente que analisa conversas e retorna apenas um objeto JSON estruturado."},
                {"role": "user", "content": prompt}
            ]
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"Erro ao obter intenção do GPT: {e}")
        # Fallback para lógica de palavras-chave se o GPT falhar
        if "add" in user_message.lower() or "adicionar" in user_message.lower():
            return {"intenção": "adicionar_ao_carrinho", "parametros": {}}
        if "carrinho" in user_message.lower():
            return {"intenção": "ver_carrinho", "parametros": {}}
        # Adicione outros fallbacks conforme necessário
        return {"intenção": "intencao_desconhecida", "parametros": {}}

# ====================================================================
# Webhook WhatsApp - LÓGICA DE CONVERSA TOTALMENTE REFEITA
# ====================================================================

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From", "").replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()

    if not sender_number or not user_message:
        return "Dados insuficientes", 400

    # 1. Obter a intenção e o estado do usuário
    intent_data = get_user_state_and_intent(sender_number, user_message)
    intent = intent_data.get("intenção", "intencao_desconhecida")
    params = intent_data.get("parametros", {})

    resposta_final = ""

    # 2. Processar a intenção
    if intent == 'saudacao':
        resposta_final = ("Olá! Bem-vindo(a) à Semente Viva! 🌱\n"
                          "Sou seu assistente de compras. O que você gostaria de fazer?\n\n"
                          "Você pode pedir para **ver os produtos**, **ver seu carrinho** ou **fazer uma pergunta** sobre um item específico.")

    elif intent == 'ver_produtos':
        categoria = params.get("categoria")
        if categoria:
            resposta_final = listar_produtos_categoria(categoria)
        else:
            resposta_final = listar_categorias()
        resposta_final += "\n\nPara adicionar um item, me diga o **ID do produto e a quantidade** (ex: 'quero 2 do item 5')."

    elif intent == 'adicionar_ao_carrinho':
        prod_id = params.get("id_produto")
        quantidade = params.get("quantidade")
        if prod_id and quantidade:
            resposta_final = adicionar_ao_carrinho(sender_number, prod_id, quantidade)
            resposta_final += "\n\nO que faremos agora? Continuar comprando ou fechar o pedido?"
        else:
            # Se o GPT não conseguiu extrair, pedimos novamente
            resposta_final = "Não entendi qual produto você quer. Por favor, me diga o ID e a quantidade. Ex: 'adicionar 2 do produto 10'."

    elif intent == 'ver_carrinho':
        resposta_final = ver_carrinho(sender_number)
        resposta_final += "\n\nPara fechar o pedido, diga **'finalizar'** ou **'quero pagar'**."

    elif intent == 'finalizar_compra':
        resposta_final = finalizar_compra(sender_number)

    elif intent == 'pergunta_geral':
        # Para perguntas gerais, usamos uma chamada mais simples ao GPT
        # (a função antiga, renomeada para clareza)
        resposta_final = responder_pergunta_geral(user_message)

    else: # intencao_desconhecida
        resposta_final = "Desculpe, não entendi muito bem. Você pode tentar reformular? Lembre-se que posso te mostrar os `produtos`, seu `carrinho` ou `finalizar` a compra."

    # 3. Enviar a resposta e salvar a conversa
    if resposta_final:
        send_whatsapp_message(to_number=sender_number, body=resposta_final)
        salvar_conversa(sender_number, user_message, resposta_final)
    
    return "OK", 200

def responder_pergunta_geral(mensagem):
    """Função para responder perguntas abertas usando o contexto dos produtos."""
    contexto_produtos = gerar_contexto_do_db()
    prompt = f"""
    Você é um assistente de vendas da loja Semente Viva.
    Responda a pergunta do cliente da forma mais útil e amigável possível, usando o contexto do catálogo abaixo.
    Seja breve e direto. Ao final, sempre incentive o cliente a dar o próximo passo na compra.
    
    Catálogo de referência:
    {contexto_produtos}

    Pergunta do cliente: "{mensagem}"
    """
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Seu objetivo é ser um vendedor prestativo."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=250,
        temperature=0.5
    )
    resposta = response.choices[0].message.content.strip()
    resposta += "\n\nPosso te ajudar com mais alguma coisa? Que tal ver nosso catálogo? É só pedir!"
    return resposta


@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    # Garante que os diretórios necessários existem
    if not os.path.exists('/tmp'):
        os.makedirs('/tmp')
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


