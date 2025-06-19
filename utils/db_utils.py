# Teste-bot-main/utils/db_utils.py

import psycopg2
import os
from datetime import datetime
from psycopg2.extras import RealDictCursor
import json # Importa a biblioteca JSON

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
    """
    conn = None
    conta_id = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM contas WHERE twilio_subaccount_sid = %s LIMIT 1",
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

# --- NOVA FUNÇÃO ---
def get_bot_config(conta_id):
    """
    Busca as configurações do bot para uma conta específica.

    Args:
        conta_id (int): O ID da conta para a qual buscar as configurações.

    Returns:
        dict: Um dicionário com as configurações do bot. Retorna um dicionário
              com valores padrão se nenhuma configuração for encontrada.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM configuracoes_bot WHERE conta_id = %s", (conta_id,))
            config = cur.fetchone()

        # Se encontrou configurações, processa o FAQ
        if config:
            # Tenta decodificar o JSON do FAQ. Se falhar, usa uma lista vazia.
            try:
                # O campo faq_conhecimento pode ser uma string JSON ou já um dict/list
                # dependendo do driver do banco. `json.loads` garante que seja uma lista Python.
                if isinstance(config.get('faq_conhecimento'), str):
                     config['faq_list'] = json.loads(config['faq_conhecimento'])
                elif isinstance(config.get('faq_conhecimento'), list):
                     config['faq_list'] = config['faq_conhecimento']
                else:
                     config['faq_list'] = []
            except (json.JSONDecodeError, TypeError):
                config['faq_list'] = []
            return config
            
    except Exception as e:
        print(f"Erro ao buscar configurações do bot para conta {conta_id}: {e}")
    finally:
        if conn: conn.close()

    # Retorna um dicionário de fallback com valores padrão se nada for encontrado ou der erro
    return {
        'saudacao_personalizada': 'Olá! Bem-vindo(a)! Como posso ajudar?',
        'faq_list': [],
        'nome_assistente': 'Assistente',
        'nome_loja_publico': 'nossa loja',
        'horario_funcionamento': 'não informado',
        'endereco': 'não informado',
        'diretriz_principal_prompt': 'Seja um assistente de vendas prestativo e amigável.',
        'conhecimento_especifico': ''
    }


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

