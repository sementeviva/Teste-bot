# routes/gerenciar_vendas.py
from flask import Blueprint, render_template, jsonify
from utils.db_utils import get_db_connection
from datetime import datetime # Importe datetime para formatar a data/hora

gerenciar_vendas_bp = Blueprint('gerenciar_vendas_bp', __name__, template_folder='../templates')

@gerenciar_vendas_bp.route('/')
def gerenciar_vendas():
    """Renderiza a página de gerenciamento de vendas."""
    return render_template('gerenciar_vendas.html')

@gerenciar_vendas_bp.route('/api/vendas')
def api_vendas():
    """Fornece os dados de vendas em formato JSON para atualização em tempo real."""
    conn = None
    vendas = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Seleciona todas as colunas da tabela 'vendas' e ordena pela data/hora mais recente
            # A coluna 'imagem' não existe na tabela 'vendas', então a removi da SELECT
            cur.execute("SELECT id, data_hora, cliente_id, produtos_vendidos, valor_total, status FROM vendas ORDER BY data_hora DESC")
            vendas_db = cur.fetchall()

            for venda in vendas_db:
                # Converte a tupla para um dicionário para facilitar a manipulação no JSON
                # e formata a data/hora para um formato legível
                vendas.append({
                    'id': venda[0],
                    'data_hora': venda[1].strftime('%Y-%m-%d %H:%M:%S') if isinstance(venda[1], datetime) else str(venda[1]),
                    'cliente_id': venda[2],
                    'produtos_vendidos': venda[3],
                    'valor_total': str(venda[4]), # Converter DECIMAL para string para evitar problemas de serialização JSON
                    'status': venda[5]
                })
        return jsonify(vendas)
    except Exception as e:
        print(f"Erro ao buscar vendas para API: {e}")
        return jsonify({'error': 'Erro ao carregar dados de vendas', 'details': str(e)}), 500
    finally:
        if conn:
            conn.close()
