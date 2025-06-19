# Teste-bot-main/utils/twilio_utils.py

import os
from twilio.rest import Client
from .db_utils import get_db_connection

def _get_twilio_client_for_account(conta_id):
    """
    Cria um cliente Twilio usando as credenciais da subconta salvas no BD.
    Usa as credenciais principais como fallback.
    """
    account_sid_master = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token_master = os.environ.get('TWILIO_AUTH_TOKEN')
    
    final_sid = account_sid_master
    final_token = auth_token_master

    if conta_id:
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT twilio_subaccount_sid, twilio_auth_token FROM contas WHERE id = %s",
                    (conta_id,)
                )
                creds = cur.fetchone()
                if creds and creds[0] and creds[1]:
                    final_sid = creds[0]
                    final_token = creds[1]
        except Exception as e:
            print(f"ERRO ao buscar credenciais para conta {conta_id}: {e}.")
        finally:
            if conn: conn.close()
            
    if not all([final_sid, final_token]):
        raise Exception("Credenciais da Twilio não configuradas.")
        
    return Client(final_sid, final_token)

def send_text(to_number, from_number, body, conta_id):
    """Envia uma mensagem de texto simples."""
    client = _get_twilio_client_for_account(conta_id)
    try:
        client.messages.create(
            from_=from_number,
            to=to_number,
            body=body
        )
    except Exception as e:
        print(f"Erro ao enviar mensagem de texto para conta {conta_id}: {e}")
        raise

def send_reply_buttons(to_number, from_number, body, buttons, conta_id):
    """
    Envia uma mensagem com até 3 botões de resposta rápida.
    `buttons` é uma lista de dicionários: [{'id': 'payload_1', 'title': 'Botão 1'}, ...]
    """
    client = _get_twilio_client_for_account(conta_id)
    if len(buttons) > 3:
        raise ValueError("O máximo de botões de resposta é 3.")
        
    actions = []
    for btn in buttons:
        actions.append({
            "type": "reply",
            "reply": {
                "id": btn['id'],
                "title": btn['title']
            }
        })

    try:
        client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid='HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', # SID do seu Content Template para botões
            content_variables={
                '1': body,
                '2': 'footer_opcional', # Pode remover ou usar
                '3': json.dumps(actions)
            }
        )
    except Exception as e:
        print(f"Erro ao enviar botões de resposta para conta {conta_id}: {e}")
        # Fallback para texto puro se a mensagem interativa falhar
        fallback_text = body + "\n\n"
        for i, btn in enumerate(buttons):
            fallback_text += f"{i+1}. {btn['title']}\n"
        send_text(to_number, from_number, fallback_text, conta_id)

def send_list_picker(to_number, from_number, body, button_text, sections, conta_id):
    """
    Envia uma mensagem com uma lista de opções.
    `sections` é uma lista de dicionários: [{'title': 'Título Seção', 'rows': [{'id': 'payload_1', 'title': 'Item 1'}, ...]}, ...]
    """
    client = _get_twilio_client_for_account(conta_id)
    
    # Validações para garantir que a estrutura está correta para a API
    if not sections or not all('rows' in s for s in sections):
         raise ValueError("A estrutura das seções é inválida.")

    interactive_data = {
        "type": "list",
        "body": {"text": body},
        "action": {
            "button": button_text,
            "sections": sections
        }
    }

    try:
        client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid='HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', # SID do seu Content Template para listas
            content_variables={
                '1': 'interactive',
                '2': json.dumps(interactive_data)
            }
        )
    except Exception as e:
        print(f"Erro ao enviar lista de opções para conta {conta_id}: {e}")
        # Fallback para texto puro
        fallback_text = body + "\n\n"
        for section in sections:
            fallback_text += f"*{section['title']}*\n"
            for row in section['rows']:
                fallback_text += f"- {row['title']}\n"
        send_text(to_number, from_number, fallback_text, conta_id)

