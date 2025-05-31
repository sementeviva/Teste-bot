import os
from twilio.rest import Client

# Carrega as credenciais do Twilio de variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Cria a instância do cliente Twilio
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_whatsapp_message(to_number, body, media_url=None):
    """
    Envia uma mensagem pelo WhatsApp usando Twilio.
    Pode enviar com ou sem mídia.
    - to_number: número do destinatário no formato '+5511999999999'
    - body: texto da mensagem
    - media_url: url da imagem ou mídia (opcional)
    """
    try:
        # O formato do número no WhatsApp para Twilio é 'whatsapp:+55xxxxxxxxxx'
        destination = f"whatsapp:{to_number}"

        # Prepara os parâmetros básicos
        params = {
            "from_": f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            "body": body,
            "to": destination
        }

        # Adiciona URL da mídia se fornecida
        if media_url:
            params["media_url"] = [media_url] if isinstance(media_url, str) else media_url

        message = client.messages.create(**params)
        return {
            "status": "success",
            "sid": message.sid,
            "to": to_number,
            "body": body,
            "media_url": media_url
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def get_message_status(message_sid):
    """
    Consulta o status de uma mensagem específica enviada pelo Twilio.
    - message_sid: SID retornado pelo envio da mensagem
    """
    try:
        message = client.messages(message_sid).fetch()
        return {
            "status": message.status,
            "from": message.from_,
            "to": message.to,
            "body": message.body
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Exemplo prático de uso:
if __name__ == "__main__":
    # Envie teste para seu próprio número
    TO_NUMBER = os.getenv("TEST_WHATSAPP_TO") # coloque '+5511999998888' nas env ou altere aqui
    BODY = "Olá! Mensagem de teste do bot Semente Viva 🟢"
    MEDIA = None  # Ou coloque uma URL de imagem, tipo "https://exemplo.com/imagem.jpg"

    response = send_whatsapp_message(TO_NUMBER, BODY, MEDIA)
    print(response)
