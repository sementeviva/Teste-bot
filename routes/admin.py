from flask import Blueprint, render_template

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates')

@admin_bp.route('/dashboard')
def dashboard():
    """
    O painel de controlo principal do administrador.
    Esta página agora é "burra" e apenas exibe o HTML.
    A segurança é garantida pela rota de entrada.
    """
    return render_template('admin/dashboard.html')
