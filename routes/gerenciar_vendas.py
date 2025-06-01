# routes/gerenciar_vendas.py
from flask import Blueprint, render_template, jsonify
from utils.db_utils import get_db_connection
from datetime import datetime

gerenciar_vendas_bp = Blueprint('gerenciar_vendas_bp', __name__, template_folder='../templates')

@gerenciar_vendas_bp.route('/')
def gerenciar_vendas():
    return render_template('gerenciar_vendas.html')

@gerenciar_vendas_bp.route('/api/vendas')
def api_vendas():
    conn = None
    vendas = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Consulta SQL com JOIN para obter o nome do cliente
            cur.execute("""
                SELECT
                    v.id,
                    v.data_hora,
                    c.nome AS nome_cliente, -- Agora selecionamos o nome do cliente
                    v.produtos_vendidos,
                    v.valor_total,
                    v.status
                FROM
                    vendas v
                JOIN
                    clientes c ON v.cliente_id = c.id -- Fazemos o JOIN com a tabela clientes
                ORDER BY
                    v.data_hora DESC
            """)
            vendas_db = cur.fetchall()

            for venda in vendas_db:
                vendas.append({
                    'id': venda[0],
                    'data_hora': venda[1].strftime('%Y-%m-%d %H:%M:%S') if isinstance(venda[1], datetime) else str(venda[1]),
                    'nome_cliente': venda[2], # Usamos 'nome_cliente' aqui
                    'produtos_vendidos': venda[3],
                    'valor_total': str(venda[4]),
                    'status': venda[5]
                })
        return jsonify(vendas)
    except Exception as e:
        print(f"Erro ao buscar vendas para API: {e}")
        return jsonify({'error': 'Erro ao carregar dados de vendas', 'details': str(e)}), 500
    finally:
        if conn:
            conn.close()
