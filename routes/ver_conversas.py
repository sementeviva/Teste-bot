from flask import Blueprint, render_template, jsonify, request
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection, salvar_conversa
from utils.twilio_utils import send_whatsapp_message

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

@ver_conversas_bp.route('/', methods=['GET'])
def listar_contatos():
    """
    Busca uma lista de contactos, contando mensagens não lidas e
    agora também buscando o status do atendimento ativo.
    """
    conn = get_db_connection()
    # ATUALIZADO: Query mais complexa com LEFT JOIN para buscar o status
    # da venda/atendimento ativo, mesmo que não haja um.
    query = """
        SELECT
            c.contato,
            COUNT(c.id) as total_mensagens,
            MAX(c.data_hora) as ultima_mensagem,
            SUM(CASE WHEN c.lido = FALSE THEN 1 ELSE 0 END) as nao_lidas,
            v.status_atendimento
        FROM conversas c
        LEFT JOIN vendas v ON c.contato = v.cliente_id AND v.status = 'aberto'
        GROUP BY c.contato, v.status_atendimento
        ORDER BY ultima_mensagem DESC;
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            contatos_resumo = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar resumo de contactos: {e}")
        contatos_resumo = []
    finally:
        if conn: conn.close()
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)

@ver_conversas_bp.route('/api/conversas/<string:contato>', methods=['GET'])
def get_historico_contato(contato):
    """
    Busca o histórico e marca as mensagens como lidas.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("UPDATE conversas SET lido = TRUE WHERE contato = %s AND lido = FALSE", (contato,))
            query = "SELECT * FROM conversas WHERE contato = %s ORDER BY data_hora ASC;"
            cur.execute(query, (contato,))
            historico = cur.fetchall()
            conn.commit()
            return jsonify(historico)
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# --- NOVA ROTA PARA OBTER E ALTERAR O STATUS DO ATENDIMENTO ---
@ver_conversas_bp.route('/api/status_atendimento/<string:contato>', methods=['GET', 'POST'])
def status_atendimento(contato):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, status_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1", (contato,))
            venda_ativa = cur.fetchone()

            if request.method == 'POST':
                novo_status = request.json.get('status')
                if not venda_ativa:
                    return jsonify({'error': 'Nenhum atendimento ativo para atualizar o status'}), 404
                
                cur.execute("UPDATE vendas SET status_atendimento = %s WHERE id = %s", (novo_status, venda_ativa['id']))
                conn.commit()
                return jsonify({'success': True, 'novo_status': novo_status})

            # Se for GET, retorna o status atual ou 'novo' como padrão
            return jsonify({'status': venda_ativa['status_atendimento'] if venda_ativa else 'novo'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# As rotas de modo_atendimento e responder continuam as mesmas
@ver_conversas_bp.route('/api/modo_atendimento/<string:contato>', methods=['GET', 'POST'])
def modo_atendimento(contato):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE cliente_id = %s AND status = 'aberto' LIMIT 1", (contato,))
            venda_ativa = cur.fetchone()
            if request.method == 'POST':
                novo_modo = request.json.get('modo')
                if novo_modo not in ['bot', 'manual']:
                    return jsonify({'error': 'Modo inválido'}), 400
                if venda_ativa:
                    cur.execute("UPDATE vendas SET modo_atendimento = %s WHERE id = %s", (novo_modo, venda_ativa['id']))
                else:
                    cur.execute("INSERT INTO vendas (cliente_id, status, modo_atendimento) VALUES (%s, 'aberto', %s)", (contato, novo_modo))
                conn.commit()
                return jsonify({'success': True, 'novo_modo': novo_modo})
            return jsonify({'modo': venda_ativa['modo_atendimento'] if venda_ativa else 'bot'})
    finally:
        if conn: conn.close()

@ver_conversas_bp.route('/api/responder', methods=['POST'])
def responder_cliente():
    data = request.get_json()
    contato = data.get('contato')
    mensagem = data.get('mensagem')
    if not contato or not mensagem:
        return jsonify({'error': 'Contato e mensagem são obrigatórios'}), 400
    try:
        send_whatsapp_message(to_number=contato, body=mensagem)
        resposta_formatada = f"[ATENDENTE]: {mensagem}"
        salvar_conversa(contato, "--- RESPOSTA MANUAL DO PAINEL ---", resposta_formatada)
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE vendas SET modo_atendimento = 'manual' WHERE cliente_id = %s AND status = 'aberto'", (contato,))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

