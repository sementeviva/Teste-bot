import os
from flask import Flask, request
from twilio.rest import Client
import openai

app = Flask(__name__)

# Configurações (pegas do ambiente)
openai.api_key = os.environ.get("OPENAI_API_KEY")
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

client = Client(twilio_sid, twilio_token)

def get_gpt_response(message):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um assistente inteligente que responde em português."},
            {"role": "user", "content": message}
        ],
        max_tokens=200,
        temperature=0.7
    )
    return response['choices'][0]['message']['content'].strip()

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From")
    user_message = request.form.get("Body")

    response_text = get_gpt_response(user_message)

    client.messages.create(
        from_=twilio_number,
        to=sender_number,
        body=response_text
    )

    return "OK", 200

if __name__ == "__main__":
    app.run()
