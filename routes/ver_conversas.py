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
    # ... (código inalterado)
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    query = "..." # sua query aqui
    # ...
    return render_template('ver_conversas_agrupado.html', contatos=[])


@ver_conversas_bp.route('/api/conversas/<path:contato>', methods=['GET'])
@login_required
def get_historico_contato(contato):
    """
    Busca o histórico de um contacto.
    ATUALIZADO para formatar a data e corrigir o erro de JSON.
    """
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Marca as mensagens como lidas
            cur.execute("UPDATE conversas SET lido = TRUE WHERE conta_id = %s AND contato = %s AND lido = FALSE", (conta_id_logada, contato))
            
            # Busca o histórico
            query = "SELECT * FROM conversas WHERE conta_id = %s AND contato = %s ORDER BY data_hora ASC;"
            cur.execute(query, (conta_id_logada, contato))
            historico = cur.fetchall()
            conn.commit()

            # --- A CORREÇÃO ESTÁ AQUI ---
            # Itera sobre cada mensagem e converte a data/hora para uma string no formato ISO
            for mensagem in historico:
                if mensagem.get('data_hora'):
                    mensagem['data_hora'] = mensagem['data_hora'].isoformat()
            
            return jsonify(historico)
            
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERRO em /api/conversas: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# As outras rotas da API e a de responder_cliente permanecem como na versão anterior.
# ... (código restante do ficheiro inalterado)

