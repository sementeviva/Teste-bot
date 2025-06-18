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

# --- NOVA FUNÇÃO ESSENCIAL ---
def get_conta_id_from_sender(sender_number_with_prefix):
    """
    Descobre a qual 'conta' um número de WhatsApp (cliente final) está associado.
    Isto é crucial para saber para qual loja o bot deve trabalhar.

    NOTA: No futuro, esta função será mais robusta. Ela usaria o número do Twilio 
    que recebeu a mensagem para encontrar o `twilio_subaccount_sid` correspondente
    na nossa tabela `contas`. Por agora, para desenvolvimento, vamos retornar
    um valor fixo para a nossa primeira conta.
    """
    # Lógica de Platzhalter (placeholder) para desenvolvimento:
    # Quando tivermos múltiplos clientes, esta função fará uma consulta no banco de dados.
    # Por enquanto, vamos assumir que estamos a trabalhar com a primeira conta (ID = 1).
    print(f"DEBUG: get_conta_id_from_sender a retornar ID de conta '1' para {sender_number_with_prefix}")
    return 1


# --- FUNÇÃO ATUALIZADA ---
def salvar_conversa(conta_id, contato, mensagem_usuario, resposta_bot):
    """
    Salva um registro da interação na tabela 'conversas', garantindo
    que ele esteja sempre associado a uma 'conta' específica.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # A query agora inclui a coluna 'conta_id'
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
        if conn:
            conn.close()

