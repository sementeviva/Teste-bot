from flask import Blueprint, render_template, request, flash, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models.user import User # Certifique-se de que UserMixin está importado ou acessível via models.user
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor # Importado para a função load_user em app.py, mas não usado diretamente aqui
import os
from datetime import datetime # Importado para usar NOW() no timestamp, embora o SQL use NOW()

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

# --- ROTAS DE LOGIN/LOGOUT DO CLIENTE FINAL (DONO DA LOJA) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Lida com a autenticação de utilizadores (donos de loja) na plataforma.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = None # Inicializa conn como None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Busca o utilizador pelo email
                cur.execute("SELECT id, nome, email, conta_id, password_hash, is_admin FROM utilizadores WHERE email = %s", (email,))
                user_data = cur.fetchone()

            # Verifica se o utilizador existe e se a senha está correta
            if user_data and check_password_hash(user_data['password_hash'], password):
                # Cria um objeto User com os dados do utilizador
                user = User(
                    id=user_data['id'],
                    nome=user_data['nome'],
                    email=user_data['email'],
                    conta_id=user_data['conta_id'],
                    is_admin=user_data.get('is_admin', False) # Pega is_admin, default False para segurança
                )
                # Faz o login do utilizador usando Flask-Login
                login_user(user, remember=True)
                # Redireciona para a página inicial após login
                flash('Login bem-sucedido!', 'success') # Adiciona mensagem de sucesso
                return redirect(url_for('home')) # Redireciona para o painel do cliente (index.html)
            else:
                # Mensagem de erro se email ou senha estiverem incorretos
                flash('Email ou senha inválidos.', 'danger')
        except Exception as e:
            # Loga o erro e exibe uma mensagem genérica para o utilizador
            print(f"Erro durante o login: {e}")
            flash('Ocorreu um erro durante o login. Tente novamente.', 'danger')
        finally:
            # Garante que a conexão com o banco seja fechada
            if conn:
                conn.close()

    # Renderiza a página de login (GET ou POST falho)
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required # Esta rota SIM precisa de login de cliente para funcionar
def logout():
    """
    Faz logout do utilizador logado e redireciona para a página de login.
    """
    logout_user() # Função do Flask-Login para encerrar a sessão
    flash('Você saiu da sua conta.', 'info') # Mensagem informativa
    return redirect(url_for('auth.login')) # Redireciona para a página de login


# --- ROTA DE REGISTO SEGURA PARA O ADMINISTRADOR ---
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """
    Esta rota permite o registo de novas contas (lojas) na plataforma,
    protegida por uma chave secreta de administrador. Novas contas terão
    um utilizador inicial não-admin.
    """
    # Obtém a chave secreta de registro das variáveis de ambiente
    secret_key = os.environ.get('REGISTRATION_SECRET_KEY')

    # Se a chave não estiver configurada, a funcionalidade é desativada.
    if not secret_key:
        abort(404) # Retorna 404 Not Found

    # Verifica se o utilizador já tem permissão na sessão para ver o formulário
    if session.get('can_register_now'):
        # Se o método for POST, estamos a criar a conta
        if request.method == 'POST':
            # Remove a permissão da sessão, é de uso único por tentativa de submissão
            session.pop('can_register_now', None)

            # --- OBTENÇÃO DOS DADOS DO FORMULÁRIO ---
            nome_empresa = request.form.get('nome_empresa')
            nome_usuario = request.form.get('nome')
            email_usuario = request.form.get('email')
            password = request.form.get('password')
            password_confirm = request.form.get('password_confirm')

            # --- VALIDAÇÃO BÁSICA ---
            if password != password_confirm:
                flash('As senhas não coincidem. Tente novamente.', 'danger')
                # Devolve a permissão para que ele possa tentar de novo no formulário
                session['can_register_now'] = True
                return render_template('registro.html')

            if not nome_empresa or not nome_usuario or not email_usuario or not password:
                 flash('Todos os campos são obrigatórios.', 'danger')
                 session['can_register_now'] = True
                 return render_template('registro.html')

            # --- GERAÇÃO DO HASH DA SENHA ---
            password_hash = generate_password_hash(password)

            # --- CÓDIGO PARA GUARDAR NO BANCO (LÓGICA ATUALIZADA) ---
            conn = None # Inicializa conn como None
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    # Opcional: Verificar se o email do utilizador já existe
                    cur.execute("SELECT id FROM utilizadores WHERE email = %s", (email_usuario,))
                    if cur.fetchone():
                        flash('Este email já está registado.', 'danger')
                        session['can_register_now'] = True # Permite tentar novamente
                        return render_template('registro.html')

                    # 1. Criar a nova conta (loja) na tabela 'contas'
                    # Usa RETURNING id para obter o ID gerado automaticamente
                    # Preenche com valores padrão/placeholder
                    # Assumindo que 'twilio_subaccount_sid' e 'twilio_auth_token' podem ser vazios inicialmente
                    cur.execute(
                        """
                        INSERT INTO contas (nome_empresa, plano_assinado, creditos_disponiveis, twilio_subaccount_sid, twilio_auth_token, data_criacao)
                        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                        """,
                        (nome_empresa, 'Grátis', 0, '', '', datetime.now()) # Valores placeholder e timestamp com timezone
                    )
                    # Obtemos o ID da conta recém-criada
                    nova_conta_id = cur.fetchone()[0]

                    # 2. Criar o novo utilizador (dono da loja) na tabela 'utilizadores'
                    # Associamos ao ID da conta criada e definimos is_admin como FALSE
                    cur.execute(
                        """
                        INSERT INTO utilizadores (nome, email, password_hash, conta_id, data_criacao, is_admin)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (nome_usuario, email_usuario, password_hash, nova_conta_id, datetime.now(), False) # <<< is_admin=False aqui
                    )

                conn.commit() # Salva as alterações no banco
                # Mensagem de sucesso e redirecionamento
                flash(f'Conta "{nome_empresa}" criada com sucesso! O utilizador "{nome_usuario}" pode agora fazer login.', 'success')
                # Redireciona para o painel administrativo após um registro bem-sucedido controlado pelo admin
                return redirect(url_for('admin_bp.dashboard'))

            except Exception as e:
                # Loga o erro de banco de dados
                print(f"Erro ao criar nova conta no registro: {e}")
                # Desfaz as alterações em caso de erro
                if conn:
                    conn.rollback()
                # Exibe mensagem de erro genérica para o utilizador
                flash(f"Ocorreu um erro ao criar a conta. Por favor, tente novamente.", "danger")
                # Devolve a permissão na sessão para que o utilizador não precise re-inserir a chave admin
                session['can_register_now'] = True

            finally:
                # Garante que a conexão com o banco seja fechada
                if conn:
                    conn.close()

        # Se for um acesso GET com permissão na sessão, mostra o formulário de registro real
        return render_template('registro.html')

    # Se NÃO tem permissão na sessão, verificamos se ele está a tentar obtê-la via POST
    if request.method == 'POST':
        # Este POST vem da página do portão (registro_gate.html)
        admin_key_attempt = request.form.get('admin_key')
        if admin_key_attempt == secret_key:
            # Chave correta, concede permissão na sessão e redireciona para a rota GET de registro
            session['can_register_now'] = True
            flash('Chave de acesso correta. Prossiga com o registo da nova conta.', 'success') # Opcional: mensagem indicando sucesso no portão
            return redirect(url_for('auth.registro'))
        else:
            # Chave incorreta, exibe mensagem de erro no portão
            flash('Chave de acesso incorreta.', 'danger')

    # Se for um acesso GET sem permissão na sessão, mostra a página para inserir a chave (portão)
    return render_template('registro_gate.html')

# A função load_user (usada pelo Flask-Login em app.py) deve continuar definida em app.py ou importada/acessível aqui se for definida em outro lugar.
# No seu caso original, load_user está em app.py, o que é correto.
# A classe User (usada por load_user) está definida em models/user.py e importada acima.

# Outras rotas no Blueprint auth_bp (se houverem) devem vir aqui abaixo.
