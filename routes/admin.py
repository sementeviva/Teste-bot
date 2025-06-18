from flask import Blueprint, render_template, request, flash, redirect, url_for, session
import os

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates')

@admin_bp.route('/', methods=['GET', 'POST'])
def admin_entry():
    """
    Esta é a ÚNICA porta de entrada para a área de admin.
    Ela verifica se o utilizador já tem acesso via sessão.
    Se não, pede a chave secreta.
    """
    # Se o utilizador já tem acesso, vai direto para o dashboard.
    if session.get('admin_access_granted'):
        return redirect(url_for('admin_bp.dashboard'))
        
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        return "Erro: A chave de acesso de administrador não está configurada no servidor.", 500

    # Se ele está a tentar fazer login com a chave...
    if request.method == 'POST':
        admin_key_attempt = request.form.get('admin_key')
        if admin_key_attempt == secret_key:
            session['admin_access_granted'] = True
            flash('Acesso de administrador concedido!', 'success')
            return redirect(url_for('admin_bp.dashboard'))
        else:
            flash('Chave de acesso incorreta.', 'danger')
            
    # Se for um acesso GET e não tiver permissão, mostra a página para inserir a chave.
    return render_template('admin/admin_gate.html')


@admin_bp.route('/dashboard')
def dashboard():
    """O painel de controlo principal do administrador."""
    # Se o utilizador tentar aceder ao dashboard sem ter passado pela porta, é expulso.
    if not session.get('admin_access_granted'):
        return redirect(url_for('admin_bp.admin_entry'))
    
    return render_template('admin/dashboard.html')


@admin_bp.route('/logout')
def logout():
    """Remove o acesso de admin da sessão."""
    session.pop('admin_access_granted', None)
    flash('Sessão de administrador encerrada.', 'info')
    return redirect(url_for('admin_bp.admin_entry'))

