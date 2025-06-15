from flask import Blueprint, render_template, jsonify
# ATENÇÃO: Adicionado o 'jsonify'
from psycopg2.extras import RealDictCursor
from ..utils.db_utils import get_db_connection

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

# --- ROTA PRINCIPAL ATUALIZADA ---
@ver_conversas_bp.route('/', methods=['GET'])
def listar_contatos():
    """
    Busca uma lista resumida de contatos que já interagiram com o bot,
    ordenados pela mensagem mais recente.
    """
    conn = None
    contatos_resumo = []
    
    # Query para agrupar por contato e pegar a última data e a contagem de mensagens
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
        if conn:
            conn.close()
            
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)


# --- NOVA ROTA DE API ---
@ver_conversas_bp.route('/api/conversas/<string:contato>', methods=['GET'])
def get_historico_contato(contato):
    """
    API que retorna o histórico de chat completo para um contato específico.
    """
    conn = None
    historico = []
    
    # Query para buscar todas as mensagens de um contato, em ordem cronológica
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
        if conn:
            conn.close()
            
    return jsonify(historico)
    
