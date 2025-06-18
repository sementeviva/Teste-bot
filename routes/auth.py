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
    """Gere o processo de login para os clientes (donos de loja)."""
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
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Email ou senha inválidos. Por favor, tente novamente.', 'danger')
        except Exception as e:
            flash('Ocorreu um erro durante o login.', 'danger')
            print(f"Erro no login: {e}")
        finally:
            if conn: conn.close()
    
    return render_template('login.html')

# --- ROTA DE REGISTO COM LÓGICA DE DUPLA AUTENTICAÇÃO ---
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Gere o processo de registo, protegido por uma chave de administrador."""
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        flash('A funcionalidade de registo não está configurada.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        # Cenário 1: O utilizador está a tentar desbloquear a página com a chave de admin.
        if 'admin_key' in request.form:
            if request.form.get('admin_key') == secret_key:
                session['can_register'] = True
                flash('Acesso concedido. Pode agora registar a nova loja.', 'success')
                return redirect(url_for('auth.registro'))
            else:
                flash('Chave de acesso incorreta.', 'danger')
                return redirect(url_for('auth.registro'))
        
        # Cenário 2: O utilizador está a submeter o formulário de registo da nova loja.
        elif 'email' in request.form:
            if not session.get('can_register'):
                flash('Sessão expirada. Por favor, autentique-se novamente com a chave de administrador.', 'warning')
                return redirect(url_for('auth.registro'))
            
            # Limpa a permissão após um uso, por segurança.
            session.pop('can_register', None)
            
            password = request.form.get('password')
            password_confirm = request.form.get('password_confirm')
            if password != password_confirm:
                flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
                session['can_register'] = True # Devolve a permissão para tentar de novo
                return render_template('registro.html')

            nome = request.form.get('nome')
            email = request.form.get('email')
            nome_empresa = request.form.get('nome_empresa')
            
            conn = get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # O resto da lógica para inserir no banco de dados...
                    cur.execute("INSERT INTO contas (nome_empresa) VALUES (%s) RETURNING id", (nome_empresa,))
                    conta_id = cur.fetchone()['id']
                    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                    cur.execute("INSERT INTO utilizadores (nome, email, password_hash, conta_id) VALUES (%s, %s, %s, %s)", (nome, email, password_hash, conta_id))
                    cur.execute("INSERT INTO configuracoes_bot (conta_id, nome_loja_publico) VALUES (%s, %s)", (conta_id, nome_empresa))
                    conn.commit()
                flash('Nova conta criada com sucesso!', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                if conn: conn.rollback()
                flash(f'Ocorreu um erro ao criar a conta: {e}', 'danger')
                session['can_register'] = True
                return render_template('registro.html')
            finally:
                if conn: conn.close()

    # Se for um acesso GET...
    # Se o utilizador já tiver permissão na sessão, mostra o formulário completo.
    if session.get('can_register'):
        return render_template('registro.html')
    else:
        # Se não, mostra a "porta" para pedir a chave de admin.
        return render_template('registro_gate.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Gere o logout do cliente (dono de loja)."""
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))

