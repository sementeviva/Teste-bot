from flask import Blueprint, render_template, request, flash, current_app
# Importa a função de conexão do banco de dados centralizada
from utils.db_utils import get_db_connection
import psycopg2 # Importa psycopg2 para lidar com erros específicos ou tipos de dados como Binary se necessário.

# Definindo o Blueprint com o nome 'ver_conversas_bp'
# O 'template_folder' aponta para onde os templates HTML associados a este Blueprint estão.
ver_conversas_bp = Blueprint('ver_conversas_bp', __name__, template_folder='../templates')

# Rota para visualizar as conversas
# A rota será acessada como /ver_conversas/ se o Blueprint for registrado com url_prefix='/ver_conversas'
@ver_conversas_bp.route('/', methods=['GET', 'POST'])
def ver_conversas():
    conn = None # Inicializa conn para garantir que esteja definida
    conversas = []
    contato_filtro = request.form.get('contato', '') # Pega o valor do filtro de contato do formulário
    data_filtro = request.form.get('data', '')     # Pega o valor do filtro de data do formulário

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            query = "SELECT id, contato, mensagem, data_hora FROM conversas WHERE 1=1"
            params = []

            if contato_filtro:
                query += " AND contato ILIKE %s" # ILIKE para busca case-insensitive no PostgreSQL
                params.append(f"%{contato_filtro}%")

            if data_filtro:
                # DATE(data_hora) para comparar apenas a parte da data
                query += " AND DATE(data_hora) = %s"
                params.append(data_filtro)
            
            query += " ORDER BY data_hora DESC" # Ordena as conversas pelas mais recentes primeiro

            cur.execute(query, params)
            # Para facilitar o acesso no template, pode ser útil buscar como dicionário (opcional)
            # Se seu cursor não retornar dicionários por padrão, pode precisar de `cursor_factory=psycopg2.extras.DictCursor`
            # ao criar o cursor, ou converter manualmente as tuplas em dicionários.
            conversas = cur.fetchall()

    except Exception as e:
        flash(f"Erro ao buscar conversas: {e}", "danger")
        current_app.logger.exception("Erro ao buscar conversas no ver_conversas_bp")
    finally:
        if conn: # Fecha a conexão se ela foi aberta
            conn.close()

    # Passa os dados e os valores dos filtros para o template
    return render_template('ver_conversas.html', 
                           conversas=conversas, 
                           contato=contato_filtro, 
                           data=data_filtro)
