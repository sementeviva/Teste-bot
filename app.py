import os
import pandas as pd
from flask import Flask, request
from twilio.rest import Client
from openai import OpenAI

app = Flask(__name__)
app.secret_key = "chave_secreta_upload"  # necessário para flash messages

# Blueprints (mova para antes do app.run)
from routes.upload_csv import upload_csv_bp
app.register_blueprint(upload_csv_bp)

# Chaves de ambiente
openai_api_key = os.environ.get("OPENAI_API_KEY")
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

# Clientes
client_openai = OpenAI(api_key=openai_api_key)
client_twilio = Client(twilio_sid, twilio_token)

# Carrega produtos
def carregar_produtos():
    df = pd.read_csv("produtos_semente_viva.csv")
    df.columns = [col.strip().lower() for col in df.columns]
    df.fillna("", inplace=True)
    colunas_necessarias = ["nome", "preco", "descricao"]
    for coluna in colunas_necessarias:
        if coluna not in df.columns:
            raise KeyError(f"Coluna '{coluna}' não encontrada no CSV.")
    df["nome"] = df["nome"].astype(str).str.lower()
    return df

produtos_df = carregar_produtos()

# Busca por palavra-chave
def buscar_produto_csv(mensagem):
    mensagem_lower = mensagem.lower()
    resultados = produtos_df[produtos_df["nome"].str.contains(mensagem_lower)]
    if not resultados.empty:
        respostas = []
        for _, row in resultados.iterrows():
            resposta = f"{row['nome'].capitalize()} - R$ {row['preco']}\n{row['descricao']}"
            respostas.append(resposta)
        return "\n\n".join(respostas)
    return None

# Contexto GPT
def gerar_contexto_csv():
    contextos = []
    for _, row in produtos_df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preco']} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

contexto_produtos = gerar_contexto_csv()

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
