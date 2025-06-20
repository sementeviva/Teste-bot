# Teste-bot-main/routes/ver_conversas.py

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import os

from utils.db_utils import get_db_connection, salvar_conversa
from utils.twilio_utils import send_text

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

@ver_conversas_bp.route('/', methods=['GET'])
@login_required
def listar_contatos():
    """Lista os contactos e o seu status para a conta do utilizador logado."""
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    contatos_resumo = []
    
    query = """
        SELECT c.contato, COUNT(c.id) as total_mensagens, MAX(c.data_hora) as ultima_mensagem,
               SUM(CASE WHEN c.lido = FALSE THEN 1 ELSE 0 END) as nao_lidas, v.status_atendimento
        FROM conversas c
        LEFT JOIN vendas v ON c.contato = v.cliente_id AND v.status = 'aberto' AND v.conta_id = %s
        WHERE c.conta_id = %s
        GROUP BY c.contato, v.status_atendimento ORDER BY ultima_mensagem DESC;
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (conta_id_logada, conta_id_logada))
            contatos_resumo = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar resumo de contactos para conta {conta_id_logada}: {e}")
    finally:
        if conn: conn.close()
        
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)

@ver_conversas_bp.route('/api/conversas/<path:contato>', methods=['GET'])
@login_required
def get_historico_contato(contato):
    """Busca o histórico de um contacto e formata a data para JSON."""
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("UPDATE conversas SET lido = TRUE WHERE conta_id = %s AND contato = %s AND lido = FALSE", (conta_id_logada, contato))
            query = "SELECT * FROM conversas WHERE conta_id = %s AND contato = %s ORDER BY data_hora ASC;"
            cur.execute(query, (conta_id_logada, contato))
            historico = cur.fetchall()
            conn.commit()
            
            # CORREÇÃO: Converte a data/hora para uma string que o JavaScript entende
            for mensagem in historico:
                if mensagem.get('data_hora'):
                    mensagem['data_hora'] = mensagem['data_hora'].isoformat()
            
            return jsonify(historico)
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# As outras funções da API (responder, etc.) permanecem como estão
# ...

