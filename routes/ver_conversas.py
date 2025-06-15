from flask import Blueprint, render_template, jsonify, request # request foi adicionado
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

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


# --- INÍCIO DA NOVA ROTA PARA MODO DE ATENDIMENTO ---
@ver_conversas_bp.route('/api/modo_atendimento/<string:contato>', methods=['GET', 'POST'])
def modo_atendimento(contato):
    """
    GET: Retorna o modo de atendimento atual para a conversa ativa do contato.
    POST: Atualiza o modo de atendimento para 'bot' ou 'manual'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Encontra a venda ativa (atendimento) para o cliente
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1", (contato,))
            venda_ativa = cur.fetchone()

            if not venda_ativa:
                return jsonify({'modo': 'bot', 'message': 'Nenhuma conversa ativa encontrada.'}), 200

            if request.method == 'POST':
                # Atualiza o modo
                novo_modo = request.json.get('modo')
                if novo_modo not in ['bot', 'manual']:
                    return jsonify({'error': 'Modo inválido'}), 400
                
                cur.execute("UPDATE vendas SET modo_atendimento = %s WHERE id = %s", (novo_modo, venda_ativa['id']))
                conn.commit()
                return jsonify({'success': True, 'novo_modo': novo_modo})

            # Se for GET, apenas retorna o modo atual
            return jsonify({'modo': venda_ativa['modo_atendimento']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
# --- FIM DA NOVA ROTA ---

