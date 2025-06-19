# Teste-bot-main/utils/db_utils.py

import psycopg2
import os
from datetime import datetime
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados PostgreSQL
    usando as variáveis de ambiente para as credenciais.
    """
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

def get_conta_id_from_sid(account_sid):
    """
    Descobre a qual 'conta' um SID de subconta da Twilio pertence.
    Esta é a implementação correta para uma arquitetura multi-inquilino.

    Args:
        account_sid (str): O AccountSid fornecido pelo webhook da Twilio,
                           que pode ser o SID da conta principal ou de uma subconta.

    Returns:
        int: O ID da conta correspondente, ou None se não for encontrada.
    """
    conn = None
    conta_id = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # A query busca na tabela 'contas' pelo SID da subconta.
            cur.execute(
                """
                SELECT id FROM contas
                WHERE twilio_subaccount_sid = %s
                LIMIT 1
                """,
                (account_sid,)
            )
            result = cur.fetchone()
            if result:
                conta_id = result[0]
    except Exception as e:
        print(f"ERRO CRÍTICO em get_conta_id_from_sid: {e}")
        return None
    finally:
        if conn:
            conn.close()

    return conta_id


def salvar_conversa(conta_id, contato, mensagem_usuario, resposta_bot):
    """
    Salva um registro da interação na tabela 'conversas', associado a uma 'conta'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversas (conta_id, contato, mensagem_usuario, resposta_bot, data_hora)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (conta_id, contato, mensagem_usuario, resposta_bot, datetime.now())
            )
            conn.commit()
    except Exception as e:
        print(f"Erro ao salvar conversa para conta_id {conta_id}: {e}")
    finally:
        if conn:
            conn.close()

# ... (outras funções utilitárias do db_utils podem permanecer aqui) ...

