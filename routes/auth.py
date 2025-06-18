from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor

# Cria um novo Blueprint chamado 'auth'
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

        # Verifica se o utilizador existe e se a senha está correta
        if user_data and check_password_hash(user_data['password_hash'], password):
            # Cria o objeto User para a sessão
            user = User(id=user_data['id'], nome=user_data['nome'], email=user_data['email'], conta_id=user_data['conta_id'])
            login_user(user, remember=True) # 'remember=True' mantém o utilizador logado
            flash('Login realizado com sucesso!', 'success')
            # Redireciona para a página principal do painel (que vamos criar)
            return redirect(url_for('home')) # Ou para um futuro 'dashboard'
        else:
            flash('Email ou senha inválidos. Por favor, tente novamente.', 'danger')

    return render_template('login.html')

@auth_bp.route('/registo', methods=['GET', 'POST'])
def registo():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        nome_empresa = request.form.get('nome_empresa')

        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verifica se o email já existe
            cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Este endereço de email já está registado.', 'warning')
                return redirect(url_for('auth.registo'))
            
            # --- Lógica Transacional para criar conta e utilizador ---
            try:
                # 1. Cria a nova conta/loja
                cur.execute(
                    "INSERT INTO contas (nome_empresa) VALUES (%s) RETURNING id",
                    (nome_empresa,)
                )
                conta_id = cur.fetchone()['id']

                # 2. Cria o novo utilizador associado a essa conta
                password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                cur.execute(
                    "INSERT INTO utilizadores (nome, email, password_hash, conta_id) VALUES (%s, %s, %s, %s)",
                    (nome, email, password_hash, conta_id)
                )
                
                # 3. (Opcional) Cria as configurações iniciais para a nova conta
                cur.execute(
                    "INSERT INTO configuracoes_bot (conta_id, nome_loja_publico) VALUES (%s, %s)",
                    (conta_id, nome_empresa)
                )

                conn.commit()
                flash('Conta criada com sucesso! Por favor, faça login.', 'success')
                return redirect(url_for('auth.login'))

            except Exception as e:
                conn.rollback() # Desfaz tudo se houver um erro
                print(f"Erro ao criar conta: {e}")
                flash('Ocorreu um erro ao criar a sua conta. Tente novamente.', 'danger')

        conn.close()

    return render_template('registo.html')


@auth_bp.route('/logout')
@login_required # Garante que apenas utilizadores logados possam fazer logout
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))

