# Teste-bot-main/utils/twilio_utils.py

import os
import json
from twilio.rest import Client
from .db_utils import get_db_connection

def _get_twilio_client_for_account(conta_id):
    """Cria um cliente Twilio com as credenciais da subconta ou principais."""
    account_sid_master = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token_master = os.environ.get('TWILIO_AUTH_TOKEN')
    
    final_sid, final_token = account_sid_master, auth_token_master

    if conta_id:
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT twilio_subaccount_sid, twilio_auth_token FROM contas WHERE id = %s", (conta_id,))
                creds = cur.fetchone()
                if creds and creds[0] and creds[1]:
                    final_sid, final_token = creds[0], creds[1]
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
        client.messages.create(from_=from_number, to=to_number, body=body)
    except Exception as e:
        print(f"Erro ao enviar mensagem de texto para conta {conta_id}: {e}")

def send_reply_buttons(to_number, from_number, body, buttons, conta_id):
    """Envia uma mensagem com até 3 botões de resposta rápida (Quick Reply)."""
    client = _get_twilio_client_for_account(conta_id)
    
    # ATENÇÃO: Substitua este SID pelo SID do seu template 'assistente_botoes'
    template_sid = os.environ.get("TWILIO_BUTTON_TEMPLATE_SID", "HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    if template_sid == "HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX":
        print("AVISO: O SID do template de botões não foi configurado. A mensagem interativa irá falhar.")

    # A API espera um objeto JSON com as ações dos botões
    actions = [{"type": "reply", "reply": btn} for btn in buttons[:3]]
    
    try:
        client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=template_sid,
            content_variables={
                '1': body,
                '2': json.dumps(actions)
            }
        )
    except Exception as e:
        print(f"ERRO ao enviar botões de resposta para conta {conta_id}: {e}")
        fallback_text = body + "\n\n"
        for i, btn in enumerate(buttons):
            fallback_text += f"*{i+1}* - {btn['title']}\n"
        fallback_text += "\n_Responda com o número da opção desejada._"
        send_text(to_number, from_number, fallback_text, conta_id)

def send_list_picker(to_number, from_number, body, button_text, sections, conta_id):
    """Envia uma mensagem com uma lista de opções (List Picker)."""
    client = _get_twilio_client_for_account(conta_id)

    # ATENÇÃO: Substitua este SID pelo SID do seu template 'assistente_lista'
    template_sid = os.environ.get("TWILIO_LIST_TEMPLATE_SID", "HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    if template_sid == "HXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX":
        print("AVISO: O SID do template de lista não foi configurado. A mensagem interativa irá falhar.")

    # Para Listas, toda a estrutura interativa é enviada numa única variável
    interactive_data = {
        "type": "list",
        "body": {"text": body},
        "action": {"button": button_text, "sections": sections}
    }
    
    try:
        client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=template_sid,
            content_variables={'1': json.dumps(interactive_data)}
        )
    except Exception as e:
        print(f"ERRO ao enviar lista de opções para conta {conta_id}: {e}")
        fallback_text = body + "\n\n"
        for section in sections:
            fallback_text += f"*{section['title']}*\n"
            for row in section['rows']:
                fallback_text += f"- {row['title']}\n"
        send_text(to_number, from_number, fallback_text, conta_id)


