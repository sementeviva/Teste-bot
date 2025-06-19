# Teste-bot-main/utils/twilio_utils.py

import os
from twilio.rest import Client
import json
from .db_utils import get_db_connection # Importa a conexão com o BD

def _get_twilio_client_for_account(conta_id):
    """
    Cria um cliente Twilio usando as credenciais específicas de uma conta
    (subconta) salvas no banco de dados. Se não encontrar, usa as credenciais
    principais como fallback.
    """
    account_sid_master = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token_master = os.environ.get('TWILIO_AUTH_TOKEN')
    
    # Por padrão, usa as credenciais da conta principal
    final_sid = account_sid_master
    final_token = auth_token_master

    # Se um conta_id foi fornecido, tenta buscar as credenciais da subconta
    if conta_id:
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Busca o SID e o Auth Token da subconta na tabela 'contas'
                cur.execute(
                    "SELECT twilio_subaccount_sid, twilio_auth_token FROM contas WHERE id = %s",
                    (conta_id,)
                )
                creds = cur.fetchone()
                # Se encontrou e os campos não estão vazios, usa essas credenciais
                if creds and creds[0] and creds[1]:
                    final_sid = creds[0]
                    final_token = creds[1]
                    print(f"INFO: Usando credenciais da subconta SID {final_sid} para Conta ID {conta_id}.")
                else:
                    print(f"AVISO: Conta ID {conta_id} não possui credenciais de subconta. Usando credenciais mestre.")
        except Exception as e:
            print(f"ERRO ao buscar credenciais para conta {conta_id}: {e}. Usando credenciais mestre.")
        finally:
            if conn: conn.close()
            
    if not all([final_sid, final_token]):
        raise Exception("Credenciais da Twilio (SID e Auth Token) não configuradas no ambiente ou no banco de dados.")
        
    return Client(final_sid, final_token)

def send_whatsapp_message(to_number, from_number, body, conta_id=None):
    """
    Envia uma mensagem de texto simples usando as credenciais da conta correta.
    """
    # ATUALIZADO: Obtém o cliente Twilio específico para a conta
    client = _get_twilio_client_for_account(conta_id)
    
    to = f"whatsapp:{to_number}" if not str(to_number).startswith("whatsapp:") else to_number
    from_ = from_number # O número 'To' do webhook já vem formatado

    try:
        message = client.messages.create(from_=from_, to=to, body=body)
        print(f"Mensagem enviada de {from_} para {to} (SID: {message.sid})")
        return message.sid
    except Exception as e:
        print(f"Erro ao enviar mensagem via Twilio para conta {conta_id}: {e}")
        raise

# A função send_interactive_message continua inalterada, mas se for usá-la,
# lembre-se de passar o 'conta_id' para que ela também use as credenciais corretas.

