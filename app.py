import os
import pandas as pd
from flask import Flask, request
from twilio.rest import Client
from openai import OpenAI

app = Flask(__name__)

# Chaves de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

# Clientes
client_openai = OpenAI(api_key=openai_api_key)
client_twilio = Client(twilio_sid, twilio_token)

# Função para buscar produtos relacionados à pergunta
def filtrar_produtos(mensagem_usuario):
    try:
        df = pd.read_csv("produtos_semente_viva.csv")
        mensagem_lower = mensagem_usuario.lower()
        resultados = df[df.apply(lambda row: mensagem_lower in row.astype(str).str.lower().to_string(), axis=1)]
        if resultados.empty:
            return "Nenhum produto encontrado relacionado à sua busca."
        produtos = []
        for _, row in resultados.iterrows():
            produto = f"{row['Nome']} - {row['Categoria']} - R$ {row['Preço']} - {row['Descrição']}"
            produtos.append(produto)
        return "\n".join(produtos)
    except Exception as e:
        return f"Erro ao buscar produtos: {str(e)}"

# Função para gerar resposta do GPT com base nos produtos filtrados
def get_gpt_response(message):
    produtos_relacionados = filtrar_produtos(message)
    prompt_sistema = (
        "Você é um assistente de vendas inteligente que responde sempre em português. "
        "Use os produtos abaixo para ajudar o cliente:\n\n" + produtos_relacionados
    )

    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": message}
        ],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# Webhook do WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From")
    user_message = request.form.get("Body")

    response_text = get_gpt_response(user_message)

    client_twilio.messages.create(
        from_=twilio_number,
        to=sender_number,
        body=response_text
    )

    return "OK", 200

# Inicialização
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
