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

# Carrega produtos e limpa texto
def carregar_produtos():
    df = pd.read_csv("produtos_semente_viva.csv")
    df.columns = [col.strip().lower() for col in df.columns]  # Normaliza os nomes das colunas
    df.fillna("", inplace=True)
    
    if "nome" in df.columns:
        df["nome"] = df["nome"].str.lower()
    else:
        print("Coluna 'nome' não encontrada.")
    
    return df

produtos_df = carregar_produtos()

# Busca por palavras-chave no CSV
def buscar_produto_csv(mensagem):
    mensagem_lower = mensagem.lower()
    resultados = produtos_df[produtos_df["nome"].str.contains(mensagem_lower)]
    
    if not resultados.empty:
        respostas = []
        for _, row in resultados.iterrows():
            resposta = f"{row['nome'].capitalize()} - R$ {row['preço']}\n{row['descrição']}"
            respostas.append(resposta)
        return "\n\n".join(respostas)
    return None

# GPT com contexto geral
def get_gpt_response(mensagem, contexto_produtos):
    prompt = f"""
Você é um assistente de vendas de uma loja chamada Semente Viva.
Use o seguinte catálogo para responder perguntas dos clientes de forma natural e clara.

Catálogo de produtos:
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

# Formata o catálogo para contexto do GPT
def gerar_contexto_csv():
    contextos = []
    for _, row in produtos_df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preço']} - {row['descrição']}"
        contextos.append(contexto)
    return "\n".join(contextos)

contexto_produtos = gerar_contexto_csv()

# Webhook do WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From")
    user_message = request.form.get("Body")

    resposta_csv = buscar_produto_csv(user_message)
    
    if resposta_csv:
        resposta_final = resposta_csv
    else:
        resposta_final = get_gpt_response(user_message, contexto_produtos)

    client_twilio.messages.create(
        from_=twilio_number,
        to=sender_number,
        body=resposta_final
    )

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
