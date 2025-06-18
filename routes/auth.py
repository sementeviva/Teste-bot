from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
import os # Importamos a biblioteca 'os' para ler variáveis de ambiente

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
    # --- INÍCIO DA NOVA LÓGICA DE SEGURANÇA ---
    # 1. Obtemos a nossa chave secreta a partir das variáveis de ambiente.
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    # 2. Obtemos o "token" que o utilizador forneceu no link (URL).
    token_from_url = request.args.get('token')

    # 3. Verificamos se a chave existe e se corresponde à do URL.
    if not secret_key or token_from_url != secret_key:
        # Se não corresponder, negamos o acesso e redirecionamos para o login.
        flash('Acesso negado. A página de registo é privada.', 'danger')
        return redirect(url_for('auth.login'))
    # --- FIM DA NOVA LÓGICA DE SEGURANÇA ---
    
    # Se a chave estiver correta, o resto da função executa normalmente.
    if request.method == 'POST':
        # ... (a lógica para criar a conta e o utilizador continua exatamente a mesma)
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        nome_empresa = request.form.get('nome_empresa')

        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Este endereço de email já está registado.', 'warning')
                # Importante: Mantemos o token no URL ao redirecionar.
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

    # Passamos o token para o template para que ele possa ser incluído nos links, se necessário.
    return render_template('registro.html', token=secret_key)

@auth_bp.route('/logout')
@login_required
def logout():
    # A lógica de logout continua a mesma...
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))
                
