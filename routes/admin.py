from flask import Blueprint, render_template, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.db_utils import get_db_connection # Importa a função de conexão com o banco
from psycopg2.extras import RealDictCursor # Importa RealDictCursor para facilitar o acesso aos dados
from datetime import datetime # Pode ser útil para formatar datas, embora a formatação final possa ser no template

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates/admin') # Ajustado template_folder para ser mais específico

# Rota de "portão" administrativo (assumindo que você já tem a lógica de verificação de chave aqui,
# que não estava completa no arquivo unificado, mas a rota auth.registro_gate existe)
# @admin_bp.route('/admin_entry', methods=['GET', 'POST'])
# def admin_entry():
#    ... (lógica para exigir a chave secreta antes de permitir acesso ao dashboard admin)
#    pass # Implementação completa não estava no arquivo unificado.

# Rota do Painel de Controlo Principal do Administrador
@admin_bp.route('/dashboard')
@login_required # Protege o dashboard admin, exigindo que o usuário esteja logado
def dashboard():
    """
    O painel de controlo principal do administrador.
    Esta página agora é 'burra' e apenas exibe o HTML.
    A segurança é garantida pela rota de entrada e pelo @login_required.
    """
    # Verifica se o usuário logado é um administrador
    if not current_user.is_admin:
        flash('Você não tem permissão para aceder a esta área.', 'danger')
        return redirect(url_for('home')) # Redireciona para a home do cliente se não for admin
        # Ou você pode usar abort(403) se preferir um erro 403 Forbidden
        # abort(403)

    return render_template('dashboard.html') # Renderiza o dashboard admin

# NOVO: Rota para listar os clientes da plataforma
@admin_bp.route('/ver_clientes')
@login_required # Protege esta rota, exigindo login
def ver_clientes():
    """
    Exibe uma lista de todos os clientes (contas de loja) cadastradas na plataforma.
    Apenas acessível para usuários administradores.
    """
    # Verifica se o usuário logado é um administrador
    if not current_user.is_admin:
        flash('Você não tem permissão para aceder a esta área.', 'danger')
        return redirect(url_for('home')) # Redireciona para a home do cliente se não for admin
        # ou abort(403)

    conn = None
    clientes = []
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur: # Usa RealDictCursor para retornar dicionários
            # Busca todos os registros da tabela 'contas'
            cur.execute("""
                SELECT
                    id,
                    nome_empresa,
                    plano_assinado,
                    creditos_disponiveis,
                    data_criacao
                FROM
                    contas
                ORDER BY
                    data_criacao DESC;
            """)
            clientes = cur.fetchall() # Obtém todos os resultados
            
            # Opcional: Formatar a data_criacao aqui se preferir no backend
            # for cliente in clientes:
            #     if isinstance(cliente['data_criacao'], datetime):
            #         cliente['data_criacao'] = cliente['data_criacao'].strftime('%d/%m/%Y %H:%M')


    except Exception as e:
        flash(f'Erro ao carregar dados dos clientes: {e}', 'danger')
        print(f"Erro ao buscar clientes na área admin: {e}") # Logar o erro no servidor
        clientes = [] # Garante que 'clientes' seja uma lista vazia em caso de erro

    finally:
        if conn:
            conn.close() # Garante que a conexão com o banco seja fechada

    # Passa a lista de clientes para o template
    return render_template('ver_clientes.html', clientes=clientes)

# --- Rota de Logout para a Área Admin (opcional, pode usar o logout da área auth) ---
# @admin_bp.route('/logout')
# @login_required # Protege esta rota
# def logout():
#     logout_user() # Função do Flask-Login
#     flash('Você saiu da sessão administrativa.', 'info')
#     return redirect(url_for('auth.login')) # Redireciona para a página de login principal
