from flask import Blueprint, render_template, jsonify
# --- NOVOS IMPORTS ---
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection
from datetime import datetime

gerenciar_vendas_bp = Blueprint('gerenciar_vendas_bp', __name__, template_folder='../templates')

@gerenciar_vendas_bp.route('/')
@login_required # Protege a rota principal do painel de vendas
def gerenciar_vendas():
    """Renderiza a página do painel de gerenciamento de vendas."""
    return render_template('gerenciar_vendas.html')

@gerenciar_vendas_bp.route('/api/vendas')
@login_required # Protege a API que fornece os dados das vendas
def api_vendas():
    """
    Fornece os dados das vendas finalizadas, mas apenas para
    a conta do utilizador que está atualmente logado.
    """
    # Obtém o ID da conta a partir da sessão do utilizador.
    conta_id_logada = current_user.conta_id
    conn = None
    
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # A query agora filtra as vendas pelo conta_id para garantir
            # que um cliente não veja as vendas de outro.
            cur.execute("""
                SELECT
                    id,
                    data_venda,
                    cliente_id, -- O ID do cliente (número de telefone)
                    produtos_vendidos,
                    valor_total,
                    status
                FROM
                    vendas
                WHERE
                    status = 'finalizado' AND conta_id = %s
                ORDER BY
                    data_venda DESC
            """, (conta_id_logada,))
            
            # RealDictCursor já retorna uma lista de dicionários,
            # tornando o código mais limpo e seguro.
            vendas = cur.fetchall()
            
            # Formata os dados para o frontend (datas e valores numéricos)
            for venda in vendas:
                if isinstance(venda['data_venda'], datetime):
                    venda['data_venda'] = venda['data_venda'].strftime('%d/%m/%Y %H:%M')
                if venda['valor_total'] is not None:
                    venda['valor_total'] = f"{float(venda['valor_total']):.2f}"

        return jsonify(vendas)
        
    except Exception as e:
        print(f"Erro ao buscar vendas para a conta {conta_id_logada}: {e}")
        return jsonify({'error': 'Erro ao carregar dados de vendas', 'details': str(e)}), 500
    finally:
        if conn:
            conn.close()

