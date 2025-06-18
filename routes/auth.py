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
    # A lógica de login continua a mesma
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

@auth_bp.route('/registo', methods=['GET', 'POST'])
def registo():
    # Obtém a chave secreta das variáveis de ambiente
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        flash('A funcionalidade de registo não está configurada pelo administrador.', 'danger')
        return redirect(url_for('auth.login'))

    # Verifica se o utilizador já passou pela primeira etapa (a senha de administrador)
    # A informação fica guardada na sessão do navegador dele.
    if not session.get('registration_access_granted'):
        # Se não passou, mostramos a "sala de espera" para pedir a senha.
        if request.method == 'POST':
            admin_key_attempt = request.form.get('admin_key')
            if admin_key_attempt == secret_key:
                # Senha correta! Guardamos na sessão que ele tem acesso.
                session['registration_access_granted'] = True
                flash('Acesso de administrador concedido. Pode agora registar uma nova loja.', 'success')
                return redirect(url_for('auth.registo'))
            else:
                flash('Senha de administrador incorreta.', 'danger')
        
        # Se for um GET ou a senha estiver errada, mostra a página de pedido de senha.
        return render_template('registro_gate.html')

    # --- Se o código chegou até aqui, significa que o utilizador tem acesso (`registration_access_granted` é True) ---
    # Agora, mostramos o formulário de registo completo e processamos os seus dados.
    if request.method == 'POST':
        # Esta parte é para o formulário de registo da loja, não o da senha de admin.
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        nome_empresa = request.form.get('nome_empresa')

        if password != password_confirm:
            flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
            return redirect(url_for('auth.registo'))
        
        # O resto da lógica para criar a conta continua igual...
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM utilizadores WHERE email = %s", (email,))
                if cur.fetchone():
                    flash('Este endereço de email já está registado.', 'warning')
                    return redirect(url_for('auth.registo'))
                
                cur.execute("INSERT INTO contas (nome_empresa) VALUES (%s) RETURNING id", (nome_empresa,))
                conta_id = cur.fetchone()['id']
                password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                cur.execute("INSERT INTO utilizadores (nome, email, password_hash, conta_id) VALUES (%s, %s, %s, %s)", (nome, email, password_hash, conta_id))
                cur.execute("INSERT INTO configuracoes_bot (conta_id, nome_loja_publico) VALUES (%s, %s)", (conta_id, nome_empresa))
                conn.commit()
                flash('Nova conta criada com sucesso! Pode agora criar outra ou voltar para o login.', 'info')
                return redirect(url_for('auth.registo')) # Redireciona de volta para a pág. de registo para adicionar outro cliente
        except Exception as e:
            if conn: conn.rollback()
            flash('Ocorreu um erro ao criar a conta.', 'danger')
        finally:
            if conn: conn.close()

    # Mostra o formulário de registo completo
    return render_template('registro.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Limpa a sessão, incluindo a permissão de registo
    session.pop('registration_access_granted', None)
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))

