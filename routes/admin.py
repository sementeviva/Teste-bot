from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import os

from utils.db_utils import get_db_connection

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates')

# Função auxiliar para verificar se o utilizador tem acesso de admin na sessão
def admin_access_granted():
    return session.get('admin_access_granted', False)

@admin_bp.route('/', methods=['GET', 'POST'])
def dashboard_gate():
    """
    Esta é a porta de entrada para toda a área de admin.
    Primeiro, pede a chave secreta. Se correta, concede acesso à sessão.
    """
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        # Se a chave não estiver configurada no Render, o acesso é impossível.
        return "Erro: A chave de acesso de administrador não está configurada no servidor.", 500

    if request.method == 'POST':
        admin_key_attempt = request.form.get('admin_key')
        if admin_key_attempt == secret_key:
            # Chave correta! Guardamos na sessão que o acesso foi concedido.
            session['admin_access_granted'] = True
            return redirect(url_for('admin_bp.dashboard'))
        else:
            flash('Chave de acesso incorreta.', 'danger')

    # Se o utilizador já tiver acesso, redireciona-o para o dashboard.
    if admin_access_granted():
        return redirect(url_for('admin_bp.dashboard'))

    # Se não, mostra a página para inserir a chave.
    return render_template('admin/admin_gate.html')


@admin_bp.route('/dashboard')
def dashboard():
    """O painel de controlo principal do administrador."""
    if not admin_access_granted():
        return redirect(url_for('admin_bp.dashboard_gate'))
    
    # Passamos a chave secreta para o template, para que ele possa construir
    # o link correto para a página de registo.
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    return render_template('admin/dashboard.html', registration_token=secret_key)


@admin_bp.route('/clientes')
def ver_clientes():
    """Página para visualizar todos os clientes (contas) cadastrados."""
    if not admin_access_granted():
        return redirect(url_for('admin_bp.dashboard_gate'))

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome_empresa, plano_assinado, creditos_disponiveis, data_criacao FROM contas ORDER BY id ASC")
            clientes = cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
        clientes = []
    finally:
        if conn: conn.close()
    
    return render_template('admin/ver_clientes.html', clientes=clientes)


@admin_bp.route('/logout')
def logout():
    """Remove o acesso de admin da sessão."""
    session.pop('admin_access_granted', None)
    flash('Acesso de administrador encerrado.', 'info')
    return redirect(url_for('admin_bp.dashboard_gate'))


