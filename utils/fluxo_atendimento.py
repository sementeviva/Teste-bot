import psycopg2
import os

# Conexão com banco de dados
def get_connection():
    return psycopg2.connect(
        host=os.environ.get('db_host'),
        database=os.environ.get('db_name'),
        user=os.environ.get('db_user'),
        password=os.environ.get('db_password'),
        port=os.environ.get('db_port', 5432)
    )

# Inicializa o fluxo de cadastro
def iniciar_cadastro(numero):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clientes_fluxo WHERE telefone = %s", (numero,))
    cur.execute("INSERT INTO clientes_fluxo (telefone, etapa) VALUES (%s, %s)", (numero, 'nome'))
    conn.commit()
    conn.close()
    return "Vamos começar seu cadastro. Qual é o seu nome completo?"

# Processa as etapas do cadastro
def processar_cadastro(numero, mensagem):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT etapa, nome, bairro FROM clientes_fluxo WHERE telefone = %s", (numero,))
    row = cur.fetchone()

    if not row:
        return iniciar_cadastro(numero)

    etapa, nome, bairro = row

    if etapa == "nome":
        cur.execute("UPDATE clientes_fluxo SET nome = %s, etapa = %s WHERE telefone = %s", (mensagem, "bairro", numero))
        conn.commit()
        conn.close()
        return "Ótimo! Agora me informe o seu bairro."

    elif etapa == "bairro":
        # Salvar cliente na tabela principal
        cur.execute("SELECT nome FROM clientes_fluxo WHERE telefone = %s", (numero,))
        nome_result = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO clientes (nome, telefone, bairro) VALUES (%s, %s, %s)",
            (nome_result, numero, mensagem)
        )
        # Apagar da tabela temporária
        cur.execute("DELETE FROM clientes_fluxo WHERE telefone = %s", (numero,))
        conn.commit()
        conn.close()
        return "Cadastro realizado com sucesso! Agora posso te ajudar com os produtos."

    conn.close()
    return "Algo deu errado. Vamos tentar novamente digitando 'cadastro'."
