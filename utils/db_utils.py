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

# --- FUNÇÃO ATUALIZADA (ANTERIORMENTE get_conta_id_from_sender) ---
def get_conta_id_from_number(twilio_number):
    """
    Descobre a qual 'conta' um número de WhatsApp da Twilio está associado.
    Esta função é o pilar da lógica multi-inquilino.

    Para esta função operar, é **essencial** que a sua tabela `contas`
    possua uma coluna (ex: 'twilio_whatsapp_number') que armazene o número
    de WhatsApp completo (formato 'whatsapp:+14155238886') vinculado
    a cada conta de cliente.

    Args:
        twilio_number (str): O número do destinatário da mensagem,
                             fornecido pelo webhook da Twilio no campo 'To'.

    Returns:
        int: O ID da conta correspondente, ou None se nenhuma conta for encontrada.
    """
    conn = None
    conta_id = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # A query busca na tabela 'contas' pelo número de telefone da Twilio.
            # Substitua 'twilio_whatsapp_number' pelo nome real da coluna em seu banco de dados.
            cur.execute(
                """
                SELECT id FROM contas
                WHERE twilio_whatsapp_number = %s
                LIMIT 1
                """,
                (twilio_number,)
            )
            result = cur.fetchone()
            if result:
                conta_id = result[0]
    except Exception as e:
        print(f"Erro CRÍTICO em get_conta_id_from_number: {e}")
        return None # Retorna None em caso de erro para evitar comportamento inesperado.
    finally:
        if conn:
            conn.close()

    return conta_id


# --- FUNÇÃO ATUALIZADA ---
def salvar_conversa(conta_id, contato, mensagem_usuario, resposta_bot):
    """
    Salva um registro da interação na tabela 'conversas', garantindo
    que ele esteja sempre associado a uma 'conta' específica.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # A query já incluía a coluna 'conta_id', está correta.
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

# --- FUNÇÃO ATUALIZADA ---
def get_last_bot_message(conta_id, contato):
    """
    Busca a última mensagem enviada pelo bot para um contato específico,
    dentro do contexto de uma 'conta' específica.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # A query já filtrava por conta_id, está correta.
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
        if conn:
            conn.close()


