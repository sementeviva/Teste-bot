from flask import Blueprint, render_template, request, flash, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
import os

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

# --- ROTAS DE LOGIN/LOGOUT DO CLIENTE FINAL (DONO DA LOJA) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... (a lógica de login do seu cliente continua a mesma)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
                user_data = cur.fetchone()
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(id=user_data['id'], nome=user_data['nome'], email=user_data['email'], conta_id=user_data['conta_id'])
                login_user(user, remember=True)
                return redirect(url_for('home')) # Redireciona para o painel do cliente
            else:
                flash('Email ou senha inválidos.', 'danger')
        finally:
            if conn: conn.close()
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required # Esta rota SIM precisa de login de cliente
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))


# --- ROTA DE REGISTO SEGURA PARA O ADMINISTRADOR ---
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """
    Esta rota agora tem a sua PRÓPRIA porta de entrada,
    exigindo a chave secreta para ser acedida.
    """
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        # Se a chave não estiver configurada, a funcionalidade é desativada.
        abort(404)

    # Verifica se o utilizador já tem permissão na sessão para ver o formulário
    if session.get('can_register_now'):
        # Se o método for POST, estamos a criar a conta
        if request.method == 'POST':
            session.pop('can_register_now', None) # A permissão é de uso único
            # ... (Lógica para criar a conta, com verificação de senha, etc.)
            password = request.form.get('password')
            password_confirm = request.form.get('password_confirm')
            if password != password_confirm:
                flash('As senhas não coincidem. Tente novamente.', 'danger')
                # Devolve a permissão para que ele possa tentar de novo
                session['can_register_now'] = True
                return render_template('registro.html')

            # ... (código para guardar no banco) ...
            flash('Nova conta criada com sucesso!', 'success')
            return redirect(url_for('admin_bp.dashboard')) # Volta para o painel de admin

        # Se for um acesso GET com permissão, mostra o formulário
        return render_template('registro.html')
    
    # Se NÃO tem permissão, verificamos se ele está a tentar obtê-la
    if request.method == 'POST':
        if request.form.get('admin_key') == secret_key:
            session['can_register_now'] = True # Concede permissão
            return redirect(url_for('auth.registro'))
        else:
            flash('Chave de acesso incorreta.', 'danger')

    # Se for um acesso GET sem permissão, mostra a página para inserir a chave
    return render_template('registro_gate.html')


