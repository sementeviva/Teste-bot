from flask import Blueprint, render_template, request, flash
# ATUALIZADO: Importe o RealDictCursor de psycopg2
from psycopg2.extras import RealDictCursor
from utils.db_utils import get_db_connection

# Blueprint continua o mesmo
ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

@ver_conversas_bp.route('/', methods=['GET', 'POST'])
def ver_conversas():
    """
    Exibe o histórico de conversas com filtros por contato e data.
    Utiliza um RealDictCursor para buscar os dados como dicionários,
    facilitando o acesso no template e tornando o código mais legível.
    """
    conn = None
    conversas = []
    # Pega os valores do formulário (funciona para GET e POST)
    contato_filtro = request.values.get('contato', '').strip()
    data_filtro = request.values.get('data', '').strip()

    try:
        conn = get_db_connection()
        # ATUALIZADO: Use o cursor_factory para obter resultados como dicionários
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # A query base seleciona todas as colunas necessárias
            query = "SELECT id, contato, mensagem_usuario, resposta_bot, data_hora FROM conversas WHERE 1=1"
            params = []

            # Adiciona os filtros à query se eles foram preenchidos
            if contato_filtro:
                query += " AND contato ILIKE %s"
                params.append(f"%{contato_filtro}%")
            
            if data_filtro:
                query += " AND DATE(data_hora) = %s"
                params.append(data_filtro)
            
            # Ordena da mais recente para a mais antiga
            query += " ORDER BY data_hora DESC"

            cur.execute(query, tuple(params))
            conversas = cur.fetchall()

    except Exception as e:
        # Em caso de erro, exibe uma mensagem para o administrador
        flash(f"Ocorreu um erro ao buscar as conversas: {e}", "danger")
        print(f"Erro ao buscar conversas: {e}") # Loga o erro no terminal também
        
    finally:
        if conn:
            conn.close()

    # Passa os resultados e os valores dos filtros para o template
    return render_template(
        'ver_conversas.html',
        conversas=conversas,
        contato_filtro=contato_filtro,
        data_filtro=data_filtro
    )
    
