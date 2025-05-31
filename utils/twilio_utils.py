import os
from twilio.rest import Client

def send_whatsapp_message(to_number, body, media_url=None):
    """
    Envia mensagem WhatsApp pelo Twilio.
    :param to_number: número do destinatário no formato 5599999999999 (sem 'whatsapp:')
    :param body: texto da mensagem
    :param media_url: url da mídia (imagem), string OU lista, ou None
    :return: SID da mensagem (para debug), ou erro
    """
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')  # Exemplo: whatsapp:+14155238886

    if not account_sid or not auth_token or not from_number:
        raise Exception("Variáveis de ambiente Twilio não configuradas corretamente.")

    client = Client(account_sid, auth_token)

    # Garante formato correto do número
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number

    try:
        params = {
            "body": body,
            "from_": from_number,
            "to": to
        }
        # Se media_url informado, garante formato lista e adiciona ao envio
        if media_url:
            if isinstance(media_url, str):
                params["media_url"] = [media_url]
            elif isinstance(media_url, list):
                params["media_url"] = media_url
            else:
                raise Exception("media_url deve ser string (URL) ou lista de URLs")
        message = client.messages.create(**params)
        print(f"[DEBUG Twilio] Mensagem enviada | SID: {message.sid} | Status: {message.status}")
        return message.sid
    except Exception as e:
        print(f"[ERRO Twilio] Falha ao enviar mensagem: {e}")
        raise
