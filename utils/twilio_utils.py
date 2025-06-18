import os
from twilio.rest import Client
import json

def _get_twilio_client():
    """Cria e retorna um cliente Twilio."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    if not all([account_sid, auth_token]):
        raise Exception("Variáveis de ambiente Twilio (SID e Auth Token) não configuradas.")
    return Client(account_sid, auth_token)

def send_whatsapp_message(to_number, body):
    """Envia uma mensagem de texto simples."""
    client = _get_twilio_client()
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number
    
    try:
        message = client.messages.create(from_=from_number, to=to, body=body)
        print(f"Mensagem de texto enviada: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Erro Twilio (texto): {e}")
        raise

def send_interactive_message(to_number, text_body, items, message_type='button'):
    """
    Envia uma mensagem interativa (botões ou lista).
    'items' para botões: uma lista de dicionários [{'id': '...', 'title': '...'}]
    'items' para lista: uma lista de dicionários [{'id': '...', 'title': '...', 'description': '...'}]
    """
    client = _get_twilio_client()
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number

    actions = []
    if message_type == 'button':
        if len(items) > 3: raise ValueError("O número máximo de botões é 3.")
        for item in items:
            actions.append({'type': 'reply', 'reply': {'id': item['id'], 'title': item['title']}})
        interactive_payload = {
            'type': 'button',
            'body': {'text': text_body},
            'action': {'buttons': actions}
        }
    elif message_type == 'list':
        if len(items) > 10: raise ValueError("O número máximo de itens na lista é 10.")
        rows = []
        for item in items:
            rows.append({'id': item['id'], 'title': item['title'], 'description': item.get('description', '')})
        interactive_payload = {
            'type': 'list',
            'body': {'text': text_body},
            'action': {
                'button': 'Opções',
                'sections': [{'title': 'Selecione uma opção', 'rows': rows}]
            }
        }
    else:
        raise ValueError("Tipo de mensagem interativa inválido. Use 'button' ou 'list'.")

    try:
        message = client.messages.create(
            from_=from_number,
            to=to,
            content_sid='HXb8c7e2a9b3a3a3a7b6b3e3e7a7e3e4e1', # Content Template (Apenas Exemplo)
            content_variables=json.dumps({
                '1': 'interactive',
                '2': json.dumps(interactive_payload)
            })
        )
        print(f"Mensagem interativa enviada: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Erro Twilio (interativo): {e}")
        # Fallback para mensagem de texto se a interativa falhar
        fallback_text = text_body + "\n\n"
        for item in items:
            fallback_text += f"- {item['title']}\n"
        return send_whatsapp_message(to_number, fallback_text)


