import psycopg2 import os from datetime import datetime

Função para conectar ao banco de dados

def conectar_db(): return psycopg2.connect( host=os.environ.get('db_host'), database=os.environ.get('db_name'), user=os.environ.get('db_user'), password=os.environ.get('db_password'), port=os.environ.get('db_port', 5432) )

Função para salvar mensagem no banco de dados

def salvar_mensagem(telefone, mensagem, origem): try: conn = conectar_db() cur = conn.cursor() cur.execute( """ INSERT INTO conversas (telefone, mensagem, origem, data_hora) VALUES (%s, %s, %s, %s) """, (telefone, mensagem, origem, datetime.now()) ) conn.commit() cur.close() conn.close() except Exception as e: print(f"Erro ao salvar mensagem: {e}")

                                           
