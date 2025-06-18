from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
import os

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
            user_data = cur.fetchone()
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(id=user_data['id'], nome=user_data['nome'], email=user_data['email'], conta_id=user_data['conta_id'])
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            flash('Email ou senha inválidos.', 'danger')
    return render_template('login.html')

@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        flash('A funcionalidade de registo não está configurada pelo administrador.', 'danger')
        return redirect(url_for('auth.login'))

    # Se o utilizador ainda não tiver acesso garantido na sessão...
    if not session.get('registration_access_granted'):
        # ... e estiver a tentar submeter a senha de admin...
        if request.method == 'POST':
            admin_key_attempt = request.form.get('admin_key')
            if admin_key_attempt == secret_key:
                session['registration_access_granted'] = True
                flash('Acesso de administrador concedido. Pode agora registar uma nova loja.', 'success')
                return redirect(url_for('auth.registro'))
            else:
                flash('Senha de administrador incorreta.', 'danger')
        # ... ou se for um acesso GET, mostramos a página de pedido de senha.
        return render_template('registro_gate.html')

    # Se o acesso foi garantido, mostramos o formulário de registo completo.
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        nome_empresa = request.form.get('nome_empresa')

        if password != password_confirm:
            flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
            return redirect(url_for('auth.registro'))
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
                if cur.fetchone():
                    flash('Este endereço de email já está registado.', 'warning')
                    return redirect(url_for('auth.registro'))
                
                cur.execute("INSERT INTO contas (nome_empresa) VALUES (%s) RETURNING id", (nome_empresa,))
                conta_id = cur.fetchone()['id']
                password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                cur.execute("INSERT INTO utilizadores (nome, email, password_hash, conta_id) VALUES (%s, %s, %s, %s)", (nome, email, password_hash, conta_id))
                cur.execute("INSERT INTO configuracoes_bot (conta_id, nome_loja_publico) VALUES (%s, %s)", (conta_id, nome_empresa))
                conn.commit()
                flash('Nova conta criada com sucesso!', 'info')
                return redirect(url_for('auth.registro'))
        except Exception as e:
            if conn: conn.rollback()
            flash('Ocorreu um erro ao criar a conta.', 'danger')
        finally:
            if conn: conn.close()

    return render_template('registro.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('registration_access_granted', None)
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))

