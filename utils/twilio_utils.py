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
    """
    Envia uma mensagem com até 3 botões de resposta rápida (Quick Reply) de forma livre.
    `buttons` é uma lista de dicionários: [{'id': 'payload_1', 'title': 'Botão 1'}, ...]
    """
    client = _get_twilio_client_for_account(conta_id)
    
    # Monta a estrutura de ações para os botões
    actions = [{"type": "reply", "reply": btn} for btn in buttons[:3]]
    interactive_message = {"type": "button", "body": {"text": body}, "action": {"buttons": actions}}

    try:
        # Envia a mensagem interativa diretamente, sem usar templates
        client.messages.create(
            from_=from_number,
            to=to_number,
            actions=actions,
            body=body # O corpo é necessário como fallback para notificações
        )
    except Exception as e:
        print(f"ERRO ao enviar botões de resposta para conta {conta_id}: {e}")
        # Lógica de fallback se o envio interativo falhar
        fallback_text = f"{body}\n\n" + "\n".join([f"*{i+1}* - {btn['title']}" for i, btn in enumerate(buttons)]) + "\n\n_Responda com o número da opção desejada._"
        send_text(to_number, from_number, fallback_text, conta_id)

def send_list_picker(to_number, from_number, body, button_text, sections, conta_id):
    """Envia uma mensagem com uma lista de opções (List Picker) de forma livre."""
    client = _get_twilio_client_for_account(conta_id)

    # Monta a estrutura completa para a mensagem de lista
    action = {"button": button_text, "sections": sections}
    
    try:
        # Envia a mensagem de lista diretamente
        client.messages.create(
            from_=from_number,
            to=to_number,
            action=action,
            body=body # O corpo é necessário como fallback
        )
    except Exception as e:
        print(f"ERRO ao enviar lista de opções para conta {conta_id}: {e}")
        fallback_text = f"{body}\n\n" + "\n".join([f"*{sec['title']}*\n" + "\n".join([f"- {row['title']}" for row in sec['rows']]) for sec in sections])
        send_text(to_number, from_number, fallback_text, conta_id)


                                                                         
