# Teste-bot-main/utils/db_utils.py

import psycopg2
import os
from datetime import datetime
from psycopg2.extras import RealDictCursor
import json

def get_db_connection():
    """Estabelece e retorna uma conexão com o banco de dados PostgreSQL."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

def get_conta_id_from_sid(account_sid):
    """Descobre a qual 'conta' um SID de subconta da Twilio pertence."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM contas WHERE twilio_subaccount_sid = %s LIMIT 1", (account_sid,))
            result = cur.fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"ERRO CRÍTICO em get_conta_id_from_sid: {e}")
        return None
    finally:
        if conn: conn.close()

def get_bot_config(conta_id):
    """Busca as configurações do bot para uma conta específica."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM configuracoes_bot WHERE conta_id = %s", (conta_id,))
            config = cur.fetchone()

        if config:
            try:
                faq_data = config.get('faq_conhecimento')
                if isinstance(faq_data, str):
                     config['faq_list'] = json.loads(faq_data)
                elif isinstance(faq_data, list):
                     config['faq_list'] = faq_data
                else:
                     config['faq_list'] = []
            except (json.JSONDecodeError, TypeError):
                config['faq_list'] = []
            return config
            
    except Exception as e:
        print(f"Erro ao buscar configurações do bot para conta {conta_id}: {e}")
    finally:
        if conn: conn.close()

    # Retorna um dicionário de fallback com valores padrão
    return {
        'saudacao_personalizada': 'Olá! Bem-vindo(a)! Como posso ajudar?',
        'faq_list': [],
        'nome_assistente': 'Assistente',
    }

def salvar_conversa(conta_id, contato, mensagem_usuario, resposta_bot):
    """Salva um registro da interação na tabela 'conversas'."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn: conn.close()

# --- NOVA FUNÇÃO ADICIONADA ---
def get_last_bot_message(conta_id, contato):
    """
    Busca a última mensagem enviada pelo bot para um contato específico,
    dentro do contexto de uma 'conta' específica.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # A query agora filtra por conta_id e contato
            cur.execute(
                """
                SELECT resposta_bot FROM conversas
                WHERE conta_id = %s AND contato = %s
                ORDER BY data_hora DESC
                LIMIT 1
                """,
                (conta_id, contato)
            )
            result = cur.fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"Erro ao buscar a última mensagem do bot para conta_id {conta_id}: {e}")
        return None
    finally:
        if conn: conn.close()


