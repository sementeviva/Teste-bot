from flask import Blueprint, render_template, jsonify, request
# --- NOVOS IMPORTS ---
# login_required para proteger as rotas.
# current_user para obter os dados do utilizador que está na sessão.
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection, salvar_conversa
from utils.twilio_utils import send_whatsapp_message

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')


@ver_conversas_bp.route('/', methods=['GET'])
@login_required # Protege a rota. Apenas utilizadores logados podem aceder.
def listar_contatos():
    """
    Lista os contactos e o seu status, mas apenas para a conta
    do utilizador que está atualmente logado.
    """
    # A nossa constante desaparece! Usamos a informação real da sessão.
    conta_id_logada = current_user.conta_id
    
    conn = get_db_connection()
    # A query agora filtra todas as conversas pelo conta_id do utilizador logado.
    query = """
        SELECT
            c.contato,
            COUNT(c.id) as total_mensagens,
            MAX(c.data_hora) as ultima_mensagem,
            SUM(CASE WHEN c.lido = FALSE THEN 1 ELSE 0 END) as nao_lidas,
            v.status_atendimento
        FROM conversas c
        LEFT JOIN vendas v ON c.contato = v.cliente_id AND v.status = 'aberto' AND v.conta_id = %s
        WHERE c.conta_id = %s
        GROUP BY c.contato, v.status_atendimento
        ORDER BY ultima_mensagem DESC;
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Passamos o conta_id como parâmetro para a query
            cur.execute(query, (conta_id_logada, conta_id_logada))
            contatos_resumo = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar resumo de contactos para conta {conta_id_logada}: {e}")
        contatos_resumo = []
    finally:
        if conn: conn.close()
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)

@ver_conversas_bp.route('/api/conversas/<string:contato>', methods=['GET'])
@login_required
def get_historico_contato(contato):
    """Busca o histórico de um contacto, garantindo que ele pertence à conta logada."""
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Todas as operações são filtradas pelo conta_id para segurança.
            cur.execute("UPDATE conversas SET lido = TRUE WHERE conta_id = %s AND contato = %s AND lido = FALSE", (conta_id_logada, contato))
            query = "SELECT * FROM conversas WHERE conta_id = %s AND contato = %s ORDER BY data_hora ASC;"
            cur.execute(query, (conta_id_logada, contato))
            historico = cur.fetchall()
            conn.commit()
            return jsonify(historico)
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

@ver_conversas_bp.route('/api/status_atendimento/<string:contato>', methods=['GET', 'POST'])
@login_required
def status_atendimento(contato):
    """Obtém ou altera o status do atendimento para a conta atual."""
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, status_atendimento FROM vendas WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto' LIMIT 1", (conta_id_logada, contato))
            venda_ativa = cur.fetchone()

            if request.method == 'POST':
                novo_status = request.json.get('status')
                if not venda_ativa:
                    return jsonify({'error': 'Nenhum atendimento ativo para atualizar o status'}), 404
                cur.execute("UPDATE vendas SET status_atendimento = %s WHERE id = %s", (novo_status, venda_ativa['id']))
                conn.commit()
                return jsonify({'success': True, 'novo_status': novo_status})

            return jsonify({'status': venda_ativa['status_atendimento'] if venda_ativa else 'novo'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

@ver_conversas_bp.route('/api/modo_atendimento/<string:contato>', methods=['GET', 'POST'])
@login_required
def modo_atendimento(contato):
    """Obtém ou altera o modo de atendimento (bot/manual) para a conta atual."""
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, modo_atendimento FROM vendas WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto' LIMIT 1", (conta_id_logada, contato))
            venda_ativa = cur.fetchone()
            if request.method == 'POST':
                novo_modo = request.json.get('modo')
                if novo_modo not in ['bot', 'manual']:
                    return jsonify({'error': 'Modo inválido'}), 400
                if venda_ativa:
                    cur.execute("UPDATE vendas SET modo_atendimento = %s WHERE id = %s", (novo_modo, venda_ativa['id']))
                else:
                    # Ao criar, também associamos o conta_id do utilizador logado.
                    cur.execute("INSERT INTO vendas (conta_id, cliente_id, status, modo_atendimento) VALUES (%s, %s, 'aberto', %s)", (conta_id_logada, contato, novo_modo))
                conn.commit()
                return jsonify({'success': True, 'novo_modo': novo_modo})
            return jsonify({'modo': venda_ativa['modo_atendimento'] if venda_ativa else 'bot'})
    finally:
        if conn: conn.close()

@ver_conversas_bp.route('/api/responder', methods=['POST'])
@login_required
def responder_cliente():
    """Envia uma resposta manual do painel, associada à conta correta."""
    conta_id_logada = current_user.conta_id
    data = request.get_json()
    contato = data.get('contato')
    mensagem = data.get('mensagem')
    if not contato or not mensagem:
        return jsonify({'error': 'Contato e mensagem são obrigatórios'}), 400
    try:
        send_whatsapp_message(to_number=contato, body=mensagem)
        resposta_formatada = f"[ATENDENTE]: {mensagem}"
        # Salva a conversa usando o conta_id do utilizador logado.
        salvar_conversa(conta_id_logada, contato, "--- RESPOSTA MANUAL DO PAINEL ---", resposta_formatada)
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE vendas SET modo_atendimento = 'manual' WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto'", (conta_id_logada, contato))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

