import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from datetime import datetime
import json

# Importa utilitários e Blueprints
from utils.twilio_utils import send_whatsapp_message, send_interactive_message
# ATENÇÃO: As funções foram refatoradas
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria
from utils.db_utils import get_db_connection, salvar_conversa, get_conta_id_from_sender

# ... (registros de blueprint continuam os mesmos)
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp
from routes.gerenciar_vendas import gerenciar_vendas_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_padrao_dev")

app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas")
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

openai_api_key = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_api_key)


def get_configuracoes_bot(conta_id):
    """Busca as configurações personalizadas do bot para uma conta específica."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM configuracoes_bot WHERE conta_id = %s", (conta_id,))
            return cur.fetchone()
    finally:
        if conn: conn.close()


def processar_conversa_ia(conta_id, user_message):
    """
    O novo "cérebro" do bot. Usa o GPT para analisar a mensagem do usuário
    e retorna um JSON estruturado com a intenção e entidades.
    """
    config = get_configuracoes_bot(conta_id)
    
    # Monta o prompt dinamicamente com as configurações do cliente
    prompt_personalizado = config.get('diretriz_principal_prompt', """
        Você é um assistente de vendas. Seu objetivo é ajudar os clientes a encontrarem o que precisam e guiá-los para falar com um atendente para finalizar a compra.
        Sempre que possível, ofereça opções claras.
    """)
    conhecimento_especifico = config.get('conhecimento_especifico', 'Nenhum conhecimento específico fornecido.')
    
    # Adiciona o conhecimento específico ao prompt
    prompt_final = f"""
    {prompt_personalizado}

    Use o seguinte conhecimento específico sobre a loja para enriquecer suas respostas:
    ---
    {conhecimento_especifico}
    ---

    Analise a mensagem do usuário e retorne um objeto JSON com a "intenção" e as "entidades" (parâmetros).
    Intenções possíveis: 'saudacao', 'ver_catalogo', 'ver_produtos_categoria', 'fazer_pergunta_produto', 'falar_com_atendente', 'pergunta_geral'.

    Exemplo de Mensagem: "queria ver seus chás"
    JSON de Saída: {{"intenção": "ver_produtos_categoria", "entidades": {{"categoria": "chás"}}}}

    Exemplo de Mensagem: "qual o preço do item 5?"
    JSON de Saída: {{"intenção": "fazer_pergunta_produto", "entidades": {{"id_produto": 5}}}}

    Mensagem do usuário: "{user_message}"
    JSON de Saída:
    """

    try:
        response = client_openai.chat.completions.create(
            model="gpt-4o",  # Usando um modelo mais recente para melhor performance em JSON
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Você é um assistente que analisa conversas e retorna apenas um objeto JSON estruturado."},
                {"role": "user", "content": prompt_final}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erro ao processar com IA: {e}")
        return {"intenção": "pergunta_geral", "entidades": {}}


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number_with_prefix = request.form.get("From", "")
    sender_number = sender_number_with_prefix.replace("whatsapp:", "")
    
    # A mensagem pode ser texto ou a ação de um botão
    user_message = request.form.get("Body", "").strip()
    if not user_message: # Se for um clique em botão, a mensagem vem no 'interactive'
        user_message = request.form.get("ButtonText", "").strip()
        
    if not sender_number or not user_message: return "OK", 200

    conta_id = get_conta_id_from_sender(sender_number_with_prefix)
    if not conta_id: return "OK", 200

    # ... (lógica do modo de teste e modo manual continua aqui)
    
    # --- NOVO FLUXO BASEADO EM INTENÇÕES ---
    
    intent_data = processar_conversa_ia(conta_id, user_message)
    intent = intent_data.get("intenção", "pergunta_geral")
    entities = intent_data.get("entidades", {})
    
    config = get_configuracoes_bot(conta_id)
    saudacao = config.get('saudacao_personalizada', 'Olá! Bem-vindo(a)! Como posso ajudar?')

    if intent == 'saudacao':
        buttons = [
            {'id': 'btn_catalogo', 'title': 'Ver Catálogo'},
            {'id': 'btn_atendente', 'title': 'Falar com Atendente'},
            {'id': 'btn_horario', 'title': 'Nosso Horário'}
        ]
        send_interactive_message(sender_number, saudacao, buttons)
        salvar_conversa(conta_id, sender_number, user_message, saudacao + " [Com Botões]")

    elif intent == 'ver_catalogo':
        categorias = listar_categorias(conta_id)
        if categorias:
            # A API da Twilio tem um limite de 10 itens para listas
            list_items = [{'id': f"cat_{cat}", 'title': cat} for cat in categorias[:10]]
            send_interactive_message(sender_number, "Ótima escolha! Selecione uma categoria para explorar:", list_items, message_type='list')
            salvar_conversa(conta_id, sender_number, user_message, "Mostrando categorias...")
        else:
            send_whatsapp_message(sender_number, "Ainda não temos produtos cadastrados. Um atendente entrará em contato.")

    elif intent == 'ver_produtos_categoria':
        categoria = entities.get('categoria')
        if categoria:
            produtos = listar_produtos_categoria(conta_id, categoria)
            if produtos:
                resposta_texto = f"Produtos em *{categoria.capitalize()}*:\n\n"
                for p in produtos:
                    resposta_texto += f"• ID {p['id']}: {p['nome']} - R$ {float(p['preco']):.2f}\n"
                resposta_texto += "\nAlgum destes lhe interessa? Posso dar mais detalhes ou chamar um atendente para finalizar o pedido."
                send_whatsapp_message(sender_number, resposta_texto)
                salvar_conversa(conta_id, sender_number, user_message, resposta_texto)

    elif intent == 'falar_com_atendente':
        resposta_final = "Entendido. Um de nossos atendentes entrará em contato em breve. Por favor, aguarde um momento."
        send_whatsapp_message(sender_number, resposta_final)
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)
        # Aqui também entraria a lógica de marcar a conversa como 'requer_atencao'
        
    else: # pergunta_geral ou outra intenção
        # Para simplificar, a resposta genérica ainda usa a função antiga, mas agora com o contexto da conta
        resposta_final = get_gpt_response(conta_id, user_message)
        send_whatsapp_message(sender_number, resposta_final)
        salvar_conversa(conta_id, sender_number, user_message, resposta_final)

    return "OK", 200

# ... (outras rotas e o if __name__ == "__main__":)
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


