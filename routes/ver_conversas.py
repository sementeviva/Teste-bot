# Teste-bot-main/routes/ver_conversas.py

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import os # Importa a biblioteca OS para aceder às variáveis de ambiente

from utils.db_utils import get_db_connection, salvar_conversa
# ATUALIZADO: Importa a função correta 'send_text' em vez da antiga
from utils.twilio_utils import send_text

ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')


@ver_conversas_bp.route('/', methods=['GET'])
@login_required
def listar_contatos():
    """
    Lista os contactos e o seu status para a conta do utilizador logado.
    """
    conta_id_logada = current_user.conta_id
    
    conn = get_db_connection()
    # A query já está correta, filtrando por conta_id
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
            cur.execute(query, (conta_id_logada, conta_id_logada))
            contatos_resumo = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar resumo de contactos para conta {conta_id_logada}: {e}")
        contatos_resumo = []
    finally:
        if conn: conn.close()
    return render_template('ver_conversas_agrupado.html', contatos=contatos_resumo)

# As rotas de API get_historico_contato, status_atendimento, e modo_atendimento
# continuam corretas e não precisam de alteração.
# ... (código inalterado)

@ver_conversas_bp.route('/api/responder', methods=['POST'])
@login_required
def responder_cliente():
    """
    Envia uma resposta manual do painel, associada à conta correta.
    Esta função foi ATUALIZADA para usar a nova função de envio.
    """
    conta_id_logada = current_user.conta_id
    data = request.get_json()
    contato = data.get('contato')
    mensagem = data.get('mensagem')
    
    if not contato or not mensagem:
        return jsonify({'error': 'Contato e mensagem são obrigatórios'}), 400

    try:
        # ATUALIZADO: Determina de qual número enviar a mensagem.
        # A forma ideal seria buscar o número associado à conta_id no banco.
        # Como fallback seguro, usamos o número principal da conta Twilio,
        # que deve estar nas suas variáveis de ambiente.
        from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
        if not from_number:
            raise ValueError("A variável de ambiente TWILIO_WHATSAPP_NUMBER não está configurada.")

        # ATUALIZADO: Usa a nova função `send_text` com os parâmetros corretos.
        send_text(
            to_number=contato,
            from_number=from_number,
            body=mensagem,
            conta_id=conta_id_logada
        )
        
        # O resto da lógica para salvar a conversa e atualizar o modo está correto.
        resposta_formatada = f"[ATENDENTE]: {mensagem}"
        salvar_conversa(conta_id_logada, contato, "--- RESPOSTA MANUAL DO PAINEL ---", resposta_formatada)
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE vendas SET modo_atendimento = 'manual' WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto'", (conta_id_logada, contato))
            conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"ERRO em /api/responder: {e}")
        return jsonify({'error': str(e)}), 500

