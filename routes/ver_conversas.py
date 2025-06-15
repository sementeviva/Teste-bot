from flask import Blueprint, render_template, jsonify, request
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection

# O nome do blueprint continua o mesmo
ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

# Esta rota, que carrega a página inicial, está correta e não precisa de mudanças.
@ver_conversas_bp.route('/', methods=['GET'])
def listar_contatos():
    conn = None
    contatos_resumo = []
    query = """
        SELECT
            contato,
            COUNT(id) as total_mensagens,
            MAX(data_hora) as ultima_mensagem
        FROM conversas
        GROUP BY contato
        ORDER BY ultima_mensagem DESC;
    """
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            contatos_resumo = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar resumo de contatos: {e}")
    finally:
        if conn: conn.close()
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)

# Esta API, que busca o histórico, também está correta.
@ver_conversas_bp.route('/api/conversas/<string:contato>', methods=['GET'])
def get_historico_contato(contato):
    conn = None
    historico = []
    query = "SELECT * FROM conversas WHERE contato = %s ORDER BY data_hora ASC;"
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (contato,))
            historico = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar histórico do contato {contato}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()
    return jsonify(historico)


# --- ATUALIZAÇÃO PRINCIPAL ESTÁ AQUI ---
# Esta é a rota que continha o erro lógico.
@ver_conversas_bp.route('/api/modo_atendimento/<string:contato>', methods=['GET', 'POST'])
def modo_atendimento(contato):
    """
    GET: Retorna o modo de atendimento atual para a conversa ativa do contato.
    POST: Atualiza o modo de atendimento. Se não houver um atendimento ativo, cria um.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Tenta encontrar um atendimento ativo para o cliente.
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1", (contato,))
            venda_ativa = cur.fetchone()

            if request.method == 'POST':
                # Esta é a lógica para quando você clica em "Assumir Conversa".
                novo_modo = request.json.get('modo')
                if novo_modo not in ['bot', 'manual']:
                    return jsonify({'error': 'Modo inválido'}), 400

                if venda_ativa:
                    # CASO 1: Já existe um atendimento. Apenas atualize o modo.
                    print(f"--- INFO: Atendimento existente. Mudando modo para '{novo_modo}' para o contato {contato}.")
                    cur.execute("UPDATE vendas SET modo_atendimento = %s WHERE id = %s", (novo_modo, venda_ativa['id']))
                else:
                    # CASO 2 (A CORREÇÃO): Não existe um atendimento. Crie um novo JÁ no modo manual.
                    print(f"--- INFO: Nenhum atendimento ativo. Criando um novo em modo '{novo_modo}' para o contato {contato}.")
                    cur.execute(
                        "INSERT INTO vendas (cliente_id, status, modo_atendimento) VALUES (%s, 'aberto', %s)",
                        (contato, novo_modo)
                    )
                
                conn.commit() # Salva a alteração (UPDATE ou INSERT)
                return jsonify({'success': True, 'novo_modo': novo_modo})

            # Lógica para GET (quando a página carrega)
            if venda_ativa:
                # Se encontrou um atendimento, retorna o modo dele.
                return jsonify({'modo': venda_ativa['modo_atendimento']})
            else:
                # Se não encontrou, o modo padrão é 'bot'.
                return jsonify({'modo': 'bot'})

    except Exception as e:
        print(f"--- ERRO na rota modo_atendimento: {e} ---")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


