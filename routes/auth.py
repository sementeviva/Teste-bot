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
    # A lógica de login do cliente final continua igual...
    # ...

# --- ROTA DE REGISTO COM LÓGICA DE DUPLA AUTENTICAÇÃO ---
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')
    if not secret_key:
        flash('A funcionalidade de registo não está configurada.', 'danger')
        return redirect(url_for('auth.login'))

    # Se o método for POST, precisamos de saber se é uma tentativa de desbloqueio ou um registo.
    if request.method == 'POST':
        # Cenário 1: O utilizador está a tentar desbloquear a página.
        if 'admin_key' in request.form:
            if request.form.get('admin_key') == secret_key:
                # Chave correta! Mostramos o formulário de registo completo.
                # Guardamos na sessão que o acesso foi concedido para esta página.
                session['can_register'] = True
                return render_template('registro.html')
            else:
                flash('Chave de acesso incorreta.', 'danger')
                return redirect(url_for('auth.registro'))
        
        # Cenário 2: O utilizador está a submeter o formulário de registo.
        elif 'email' in request.form:
            # Verificamos se ele tinha permissão para ver este formulário.
            if not session.get('can_register'):
                flash('Sessão expirada. Por favor, autentique-se novamente.', 'warning')
                return redirect(url_for('auth.registro'))
            
            # Limpa a permissão após um uso, para segurança.
            session.pop('can_register', None)
            
            # A lógica de criar a conta continua a mesma...
            # ...
            password = request.form.get('password')
            password_confirm = request.form.get('password_confirm')
            if password != password_confirm:
                flash('As senhas não coincidem.', 'danger')
                return render_template('registro.html') # Mostra o formulário novamente

            # ... (código para guardar no banco de dados) ...
            
            flash('Nova conta criada com sucesso!', 'success')
            return redirect(url_for('auth.login'))

    # Se for um acesso GET, mostramos sempre a "porta" de autenticação.
    session.pop('can_register', None) # Limpa permissões antigas
    return render_template('registro_gate.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # A lógica de logout do cliente final continua igual...
    # ...

