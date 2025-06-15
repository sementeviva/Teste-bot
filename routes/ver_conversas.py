from flask import Blueprint, render_template, jsonify, request
from psycopg2.extras import RealDictCursor
# Adicionamos os imports que vamos precisar
from utils.db_utils import get_db_connection, salvar_conversa
from utils.twilio_utils import send_whatsapp_message

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

# As rotas existentes continuam as mesmas
@ver_conversas_bp.route('/', methods=['GET'])
def listar_contatos():
    conn = None
    contatos_resumo = []
    query = """
        SELECT contato, COUNT(id) as total_mensagens, MAX(data_hora) as ultima_mensagem
        FROM conversas GROUP BY contato ORDER BY ultima_mensagem DESC;
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
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM conversas WHERE contato = %s ORDER BY data_hora ASC;", (contato,))
            historico = cur.fetchall()
        return jsonify(historico)
    finally:
        if conn: conn.close()

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


# --- INÍCIO DA NOVA ROTA PARA RESPOSTA RÁPIDA ---
@ver_conversas_bp.route('/api/responder', methods=['POST'])
def responder_cliente():
    """
    Recebe uma mensagem do painel, envia para o cliente via Twilio
    e salva no banco como uma mensagem do atendente.
    """
    data = request.get_json()
    contato = data.get('contato')
    mensagem = data.get('mensagem')

    if not contato or not mensagem:
        return jsonify({'error': 'Contato e mensagem são obrigatórios'}), 400

    try:
        # Envia a mensagem para o cliente pelo WhatsApp
        send_whatsapp_message(to_number=contato, body=mensagem)

        # Salva a mensagem do atendente no nosso banco de dados
        # Usamos um prefixo para identificar que foi um humano que enviou
        resposta_formatada = f"[ATENDENTE]: {mensagem}"
        salvar_conversa(contato, "--- RESPOSTA MANUAL DO PAINEL ---", resposta_formatada)
        
        # BÔNUS: Garante que a conversa continue em modo manual
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE vendas SET modo_atendimento = 'manual' WHERE cliente_id = %s AND status = 'aberto'", (contato,))
            conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        print(f"--- ERRO ao enviar resposta rápida: {e} ---")
        return jsonify({'error': str(e)}), 500
# --- FIM DA NOVA ROTA ---

