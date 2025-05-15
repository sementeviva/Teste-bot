import os
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

# Função para obter resposta do GPT
def get_gpt_response(message):
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é um assistente inteligente que responde em português."},
            {"role": "user", "content": message}
        ],
        max_tokens=200,
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
