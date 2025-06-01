import psycopg2
import os
from datetime import datetime

# Função para conectar ao banco de dados (Renomeada para 'get_db_connection' e variáveis de ambiente padronizadas)
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),      # Padronizado para DB_HOST
        database=os.environ.get('DB_NAME'),  # Padronizado para DB_NAME
        user=os.environ.get('DB_USER'),      # Padronizado para DB_USER
        password=os.environ.get('DB_PASSWORD'), # Padronizado para DB_PASSWORD
        port=os.environ.get('DB_PORT', 5432) # Padronizado para DB_PORT
    )

# Função para salvar conversas no banco de dados (Adaptada para a lógica do app.py)
def salvar_conversa(contato, mensagem_usuario, resposta_bot):
    try:
        conn = get_db_connection() # Usando a função de conexão renomeada
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
