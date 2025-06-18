# Teste-bot-main/utils/twilio_utils.py

import os
from twilio.rest import Client
import json

def _get_twilio_client_for_account(conta_id=None):
    """
    Cria e retorna um cliente Twilio.
    ATUALIZAÇÃO: No futuro, esta função pode ser modificada para buscar as
    credenciais (SID e Auth Token) específicas de uma subconta da Twilio
    com base no conta_id, permitindo que cada cliente use suas próprias
    credenciais de forma isolada.

    Por enquanto, continua usando as credenciais principais da conta mestre.
    """
    # Lógica atual: Usa as credenciais principais do ambiente.
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    # Lógica futura (exemplo comentado):
    # if conta_id:
    #     conn = get_db_connection()
    #     cur = conn.cursor()
    #     cur.execute("SELECT twilio_subaccount_sid, twilio_auth_token FROM contas WHERE id = %s", (conta_id,))
    #     creds = cur.fetchone()
    #     if creds and creds[0] and creds[1]:
    #         account_sid, auth_token = creds[0], creds[1]
    #     conn.close()

    if not all([account_sid, auth_token]):
        raise Exception("Variáveis de ambiente Twilio (SID e Auth Token) não configuradas.")
    return Client(account_sid, auth_token)

def send_whatsapp_message(to_number, from_number, body, conta_id=None):
    """
    Envia uma mensagem de texto simples.
    ATUALIZAÇÃO: Adicionado 'from_number'. O bot deve responder a partir
    do mesmo número que recebeu a mensagem.
    """
    client = _get_twilio_client_for_account(conta_id)
    
    # Formata os números se não estiverem no formato correto.
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number
    from_ = f"whatsapp:{from_number}" if not str(from_number).startswith("whatsapp:") else from_number

    try:
        message = client.messages.create(from_=from_, to=to, body=body)
        print(f"Mensagem de texto enviada de {from_} para {to}: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Erro Twilio (texto): {e}")
        raise

# A função de mensagem interativa também precisaria ser ajustada para aceitar 'from_number'
# mas, como não está sendo usada ativamente no webhook principal, mantenho-a como está por clareza.
# Se for usá-la, lembre-se de passar o 'from_number' para ela também.
def send_interactive_message(to_number, text_body, items, message_type='button'):
    """Envia uma mensagem interativa (botões ou lista)."""
    # (código inalterado, mas precisa de revisão se for ser usado)
    client = _get_twilio_client_for_account()
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER') # CUIDADO: Este número está fixo!
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number

    # ... resto da função inalterado

