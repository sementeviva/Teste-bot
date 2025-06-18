from flask import Blueprint, render_template, request, flash, redirect, url_for
import os

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates')

@admin_bp.route('/', methods=['GET', 'POST'])
def gate():
    """Esta é a porta de entrada para a área de admin. Pede a chave secreta."""
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        return "Erro: A chave de administrador não está configurada.", 500

    if request.method == 'POST':
        if request.form.get('admin_key') == secret_key:
            # Se a chave estiver correta, redireciona para o dashboard.
            return redirect(url_for('admin_bp.dashboard'))
        else:
            flash('Chave de acesso incorreta.', 'danger')
            
    return render_template('admin/admin_gate.html')


@admin_bp.route('/dashboard')
def dashboard():
    """O painel de controlo principal do administrador."""
    # Neste modelo simples, não verificamos a sessão aqui, pois o acesso direto
    # a esta página não revela informações sensíveis. A segurança está nos links.
    return render_template('admin/dashboard.html')

