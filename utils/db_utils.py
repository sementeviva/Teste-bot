import psycopg2
import os
from datetime import datetime

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

def salvar_conversa(contato, mensagem_usuario, resposta_bot):
    """
    Salva um registro da interação (mensagem do usuário e resposta do bot)
    na tabela 'conversas' do banco de dados.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversas (contato, mensagem_usuario, resposta_bot, data_hora)
            VALUES (%s, %s, %s, %s)
            """,
            (contato, mensagem_usuario, resposta_bot, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar conversa: {e}")

def get_last_bot_message(contato):
    """
    Busca a última mensagem enviada pelo bot para um contato específico.
    Isso ajuda a dar contexto para a próxima interação.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT resposta_bot FROM conversas
            WHERE contato = %s
            ORDER BY data_hora DESC
            LIMIT 1
            """,
            (contato,)
        )
        result = cur.fetchone()
        # Retorna a mensagem se encontrar, caso contrário retorna None
        return result[0] if result else None
    except Exception as e:
        print(f"Erro ao buscar a última mensagem do bot: {e}")
        return None
    finally:
        if conn:
            conn.close()

