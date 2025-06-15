from flask import Blueprint, render_template, jsonify, request
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection
from utils.twilio_utils import send_whatsapp_message
# Importamos a função de salvar para a resposta rápida
from utils.db_utils import salvar_conversa

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

# --- ROTA PRINCIPAL ATUALIZADA ---
@ver_conversas_bp.route('/', methods=['GET'])
def listar_contatos():
    """
    Busca uma lista de contatos e agora também conta
    quantas mensagens não lidas cada um tem.
    """
    conn = None
    contatos_resumo = []
    # ATUALIZADO: A query agora inclui um contador para 'nao_lidas'.
    # Usamos SUM e CASE para contar 1 para cada mensagem com 'lido = FALSE'.
    query = """
        SELECT
            contato,
            COUNT(id) as total_mensagens,
            MAX(data_hora) as ultima_mensagem,
            SUM(CASE WHEN lido = FALSE THEN 1 ELSE 0 END) as nao_lidas
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


# --- ROTA DA API ATUALIZADA ---
@ver_conversas_bp.route('/api/conversas/<string:contato>', methods=['GET'])
def get_historico_contato(contato):
    """
    Busca o histórico de um contato e, crucialmente, marca
    todas as suas mensagens como lidas no processo.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ATUALIZADO: Primeiro, marcamos todas as mensagens deste contato como lidas.
            cur.execute("UPDATE conversas SET lido = TRUE WHERE contato = %s AND lido = FALSE", (contato,))
            
            # Depois, buscamos o histórico completo como antes.
            query = "SELECT * FROM conversas WHERE contato = %s ORDER BY data_hora ASC;"
            cur.execute(query, (contato,))
            historico = cur.fetchall()

            # Por fim, salvamos (commit) a alteração do status 'lido'.
            conn.commit()
            
            return jsonify(historico)
    except Exception as e:
        print(f"Erro ao buscar histórico do contato {contato}: {e}")
        # Se der erro, desfazemos qualquer alteração pendente
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# As rotas de modo_atendimento e responder continuam iguais
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
        print(f"--- ERRO ao enviar resposta rápida: {e} ---")
        return jsonify({'error': str(e)}), 500

