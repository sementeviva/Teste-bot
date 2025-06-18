from flask import Blueprint, render_template, abort, flash, redirect, url_for, request
from flask_login import login_required, current_user
from utils.db_utils import get_db_connection # Importa a função de conexão com o banco
from psycopg2.extras import RealDictCursor # Importa RealDictCursor para facilitar o acesso aos dados
from datetime import datetime # Pode ser útil para formatar datas, embora a formatação final possa ser no template
from werkzeug.security import generate_password_hash # Precisamos disso se permitirmos alterar a senha do utilizador

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates/admin')

# --- Função auxiliar para verificar se o usuário é admin ---
def requires_admin(f):
    """Decorator para verificar se o utilizador logado é administrador."""
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Você não tem permissão para aceder a esta área.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Rota de "portão" administrativo (assumindo que você já tem a lógica de verificação de chave aqui)
# @admin_bp.route('/admin_entry', methods=['GET', 'POST'])
# def admin_entry():
#    pass # Implementação completa não estava no arquivo unificado.

# Rota do Painel de Controlo Principal do Administrador
@admin_bp.route('/dashboard')
@requires_admin # Usa o novo decorador para proteger a rota
def dashboard():
    """
    O painel de controlo principal do administrador.
    Esta página agora é 'burra' e apenas exibe o HTML.
    A segurança é garantida pela rota de entrada e pelo @requires_admin.
    """
    # A verificação de is_admin agora é feita pelo decorador @requires_admin
    return render_template('dashboard.html')

# Rota para listar os clientes da plataforma
@admin_bp.route('/ver_clientes')
@requires_admin # Protege esta rota
def ver_clientes():
    """
    Exibe uma lista de todos os clientes (contas de loja) cadastradas na plataforma.
    Apenas acessível para usuários administradores.
    """
    # A verificação de is_admin agora é feita pelo decorador @requires_admin
    conn = None
    clientes = []
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Busca todos os registros da tabela 'contas'
            cur.execute("""
                SELECT
                    id,
                    nome_empresa,
                    plano_assinado,
                    creditos_disponiveis,
                    data_criacao,
                    twilio_subaccount_sid -- Incluindo campos Twilio para possível exibição
                FROM
                    contas
                ORDER BY
                    data_criacao DESC;
            """)
            clientes = cur.fetchall()

            # Opcional: Formatar a data_criacao aqui se preferir no backend
            # for cliente in clientes:
            #     if isinstance(cliente['data_criacao'], datetime):
            #         cliente['data_criacao'] = cliente['data_criacao'].strftime('%d/%m/%Y %H:%M')

    except Exception as e:
        flash(f'Erro ao carregar dados dos clientes: {e}', 'danger')
        print(f"Erro ao buscar clientes na área admin: {e}") # Logar o erro no servidor
        clientes = [] # Garante que 'clientes' seja uma lista vazia em caso de erro

    finally:
        if conn:
            conn.close() # Garante que a conexão com o banco seja fechada

    # Passa a lista de clientes para o template
    return render_template('ver_clientes.html', clientes=clientes)


# NOVO: Rota para editar um cliente (conta e utilizador principal)
@admin_bp.route('/editar_cliente/<int:conta_id>', methods=['GET', 'POST'])
@requires_admin # Protege esta rota, apenas admins podem editar clientes
def editar_cliente(conta_id):
    """
    Exibe e processa o formulário para editar os detalhes de uma conta (loja)
    e do seu utilizador principal.
    """
    conn = None
    cliente = None # Dados da conta (tabela contas)
    utilizador_principal = None # Dados do utilizador (tabela utilizadores)

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # --- Lógica para POST (Salvar Alterações) ---
            if request.method == 'POST':
                # Dados da Conta (tabela contas)
                nome_empresa = request.form.get('nome_empresa')
                plano_assinado = request.form.get('plano_assinado')
                creditos_disponiveis = request.form.get('creditos_disponiveis')
                twilio_subaccount_sid = request.form.get('twilio_subaccount_sid')
                twilio_auth_token = request.form.get('twilio_auth_token')

                # Dados do Utilizador Principal (tabela utilizadores)
                utilizador_id = request.form.get('utilizador_id') # ID do utilizador a ser editado
                nome_utilizador = request.form.get('nome_utilizador')
                email_utilizador = request.form.get('email_utilizador')
                nova_senha = request.form.get('nova_senha') # Campo opcional para nova senha

                # Validação básica
                if not nome_empresa or not plano_assinado or creditos_disponiveis is None or not nome_utilizador or not email_utilizador:
                    flash('Nome da Empresa, Plano, Créditos, Nome e Email do Utilizador são obrigatórios.', 'danger')
                    # Recarrega os dados atuais para preencher o formulário novamente
                    cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                    cliente = cur.fetchone()
                    cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s ORDER BY id LIMIT 1", (conta_id,))
                    utilizador_principal = cur.fetchone()
                    # Retorna para a página de edição com a mensagem de erro
                    return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)

                # 1. Atualizar tabela 'contas'
                cur.execute(
                    """
                    UPDATE contas
                    SET nome_empresa = %s, plano_assinado = %s, creditos_disponiveis = %s,
                        twilio_subaccount_sid = %s, twilio_auth_token = %s
                    WHERE id = %s;
                    """,
                    (nome_empresa, plano_assinado, creditos_disponiveis,
                     twilio_subaccount_sid, twilio_auth_token, conta_id)
                )

                # 2. Atualizar tabela 'utilizadores' para o utilizador principal
                update_user_query = """
                    UPDATE utilizadores
                    SET nome = %s, email = %s
                    WHERE id = %s AND conta_id = %s; -- Garante que estamos atualizando o user correto da conta
                """
                user_params = [nome_utilizador, email_utilizador, utilizador_id, conta_id]

                # Se uma nova senha foi fornecida, atualiza o password_hash
                if nova_senha:
                    if len(nova_senha) < 6: # Exemplo de validação básica de senha
                         flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                         # Recarrega os dados atuais para preencher o formulário novamente
                         cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                         cliente = cur.fetchone()
                         cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s AND id = %s", (conta_id, utilizador_id))
                         utilizador_principal = cur.fetchone()
                         return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)

                    password_hash = generate_password_hash(nova_senha)
                    update_user_query = """
                        UPDATE utilizadores
                        SET nome = %s, email = %s, password_hash = %s
                        WHERE id = %s AND conta_id = %s;
                    """
                    user_params = [nome_utilizador, email_utilizador, password_hash, utilizador_id, conta_id]

                cur.execute(update_user_query, user_params)


                conn.commit() # Salva as alterações
                flash(f'Dados do cliente (Conta ID: {conta_id}) atualizados com sucesso!', 'success')
                return redirect(url_for('admin_bp.ver_clientes')) # Redireciona de volta para a lista

            # --- Lógica para GET (Exibir Formulário de Edição) ---
            else:
                # Busca os dados da conta pela conta_id
                cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                cliente = cur.fetchone()

                if not cliente:
                    flash('Cliente não encontrado.', 'danger')
                    return redirect(url_for('admin_bp.ver_clientes'))

                # Busca o utilizador principal associado a esta conta
                # Assumimos o primeiro utilizador encontrado para simplificar.
                # Em um sistema mais complexo, pode ser necessário um campo 'owner_id' na tabela 'contas'
                # ou uma forma de listar e selecionar utilizadores.
                cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s ORDER BY id LIMIT 1", (conta_id,))
                utilizador_principal = cur.fetchone()

                if not utilizador_principal:
                     flash('Utilizador principal não encontrado para esta conta.', 'warning')
                     # Cria um objeto placeholder se não encontrar, para evitar erros no template
                     utilizador_principal = {'id': None, 'nome': 'N/A', 'email': 'N/A', 'is_admin': False}


    except Exception as e:
        # Em caso de erro geral no banco
        if conn:
            conn.rollback() # Desfaz qualquer alteração pendente
        flash(f'Ocorreu um erro ao processar a solicitação: {e}', 'danger')
        print(f"Erro na edição do cliente (Conta ID: {conta_id}): {e}")
        # Tenta redirecionar de volta para a lista, ou fica na página atual com erro
        # Se for POST, já retornamos acima. Se for GET e der erro, renderiza a página com dados parciais/vazios e erro flash
        # Ou redireciona para a lista: return redirect(url_for('admin_bp.ver_clientes'))
        pass # Mantém cliente e utilizador_principal como None ou dados parciais

    finally:
        if conn:
            conn.close() # Garante que a conexão seja fechada

    # Renderiza o template com os dados (para GET) ou após falha no POST
    return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)


# --- Rota de Logout para a Área Admin (opcional, pode usar o logout da área auth) ---
# @admin_bp.route('/logout')
# @requires_admin # Protege esta rota
# def logout():
#     logout_user() # Função do Flask-Login
#     flash('Você saiu da sessão administrativa.', 'info')
#     return redirect(url_for('auth.login')) # Redireciona para a página de login principal
