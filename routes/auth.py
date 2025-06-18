from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
import os

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # A lógica de login continua a mesma...
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
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Email ou senha inválidos. Por favor, tente novamente.', 'danger')
    return render_template('login.html')

@auth_bp.route('/registo', methods=['GET', 'POST'])
def registo():
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    token_from_url = request.args.get('token')

    if not secret_key or token_from_url != secret_key:
        flash('Acesso negado. A página de registo é privada.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        # NOVO: Obtemos o campo de confirmação de senha
        password_confirm = request.form.get('password_confirm')
        nome_empresa = request.form.get('nome_empresa')

        # --- INÍCIO DA NOVA LÓGICA DE VALIDAÇÃO ---
        if password != password_confirm:
            flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
            # Mantemos o token no URL ao redirecionar para a página de registo
            return redirect(url_for('auth.registo', token=secret_key))
        # --- FIM DA NOVA LÓGICA DE VALIDAÇÃO ---

        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Este endereço de email já está registado.', 'warning')
                return redirect(url_for('auth.registo', token=secret_key))
            
            try:
                cur.execute("INSERT INTO contas (nome_empresa) VALUES (%s) RETURNING id", (nome_empresa,))
                conta_id = cur.fetchone()['id']
                password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                cur.execute("INSERT INTO utilizadores (nome, email, password_hash, conta_id) VALUES (%s, %s, %s, %s)", (nome, email, password_hash, conta_id))
                cur.execute("INSERT INTO configuracoes_bot (conta_id, nome_loja_publico) VALUES (%s, %s)", (conta_id, nome_empresa))
                conn.commit()
                flash('Nova conta criada com sucesso! Pode agora fazer login.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                conn.rollback()
                flash('Ocorreu um erro ao criar a conta.', 'danger')
                print(f"Erro no registo: {e}")
        conn.close()

    return render_template('registro.html', token=secret_key)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))
    
