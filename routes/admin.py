from flask import Blueprint, render_template, abort, flash, redirect, url_for, request
from flask_login import login_required, current_user
from utils.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime
from werkzeug.security import generate_password_hash
import functools # Importamos functools

admin_bp = Blueprint('admin_bp', __name__, template_folder='../templates/admin')

# --- Função auxiliar para verificar se o usuário é admin (AGORA COM WRAPS) ---
def requires_admin(f):
    """Decorator para verificar se o utilizador logado é administrador."""
    @functools.wraps(f) # <<< Adicionamos esta linha
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
                    twilio_subaccount_sid
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
        print(f"Erro ao buscar clientes na área admin: {e}")
        clientes = [] # Garante que 'clientes' seja uma lista vazia em caso de erro

    finally:
        if conn:
            conn.close()

    # Passa a lista de clientes para o template
    return render_template('ver_clientes.html', clientes=clientes)


# Rota para editar um cliente (conta e utilizador principal)
@admin_bp.route('/editar_cliente/<int:conta_id>', methods=['GET', 'POST'])
@requires_admin # Protege esta rota, apenas admins podem editar clientes
def editar_cliente(conta_id):
    """
    Exibe e processa o formulário para editar os detalhes de uma conta (loja)
    e do seu utilizador principal.
    """
    conn = None
    cliente = None
    utilizador_principal = None

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # --- Lógica para POST (Salvar Alterações) ---
            if request.method == 'POST':
                # Dados da Conta (tabela contas)
                nome_empresa = request.form.get('nome_empresa')
                plano_assinado = request.form.get('plano_assinado')
                # Converte créditos_disponiveis para int, tratando possível erro
                creditos_disponiveis_str = request.form.get('creditos_disponiveis')
                try:
                    creditos_disponiveis = int(creditos_disponiveis_str) if creditos_disponiveis_str else 0
                except ValueError:
                    flash('Créditos disponíveis deve ser um número inteiro válido.', 'danger')
                    # Recarrega dados atuais para preencher o formulário
                    cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                    cliente = cur.fetchone()
                    cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s ORDER BY id LIMIT 1", (conta_id,))
                    utilizador_principal = cur.fetchone()
                    return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)


                twilio_subaccount_sid = request.form.get('twilio_subaccount_sid', '') # Default vazio
                twilio_auth_token = request.form.get('twilio_auth_token', '')       # Default vazio


                # Dados do Utilizador Principal (tabela utilizadores)
                utilizador_id_str = request.form.get('utilizador_id')
                try:
                     utilizador_id = int(utilizador_id_str) if utilizador_id_str else None
                except ValueError:
                     flash('ID do utilizador inválido.', 'danger')
                     # Recarrega dados atuais
                     cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                     cliente = cur.fetchone()
                     return render_template('editar_cliente.html', cliente=cliente, utilizador=None) # Não podemos buscar user sem ID válido

                nome_utilizador = request.form.get('nome_utilizador')
                email_utilizador = request.form.get('email_utilizador')
                nova_senha = request.form.get('nova_senha')

                # Validação básica
                if not nome_empresa or not plano_assinado or creditos_disponiveis is None or not nome_utilizador or not email_utilizador or utilizador_id is None:
                    flash('Nome da Empresa, Plano, Créditos, Nome, Email do Utilizador e ID do Utilizador são obrigatórios.', 'danger')
                    # Recarrega os dados atuais para preencher o formulário novamente
                    cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                    cliente = cur.fetchone()
                    # Busca o utilizador específico que estamos tentando editar
                    if utilizador_id:
                         cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s AND id = %s LIMIT 1", (conta_id, utilizador_id))
                         utilizador_principal = cur.fetchone()
                    else:
                         utilizador_principal = None # Ou busca o primeiro se não tiver ID válido submetido


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
                         cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s AND id = %s LIMIT 1", (conta_id, utilizador_id))
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

                # Verifica se alguma linha foi afetada para a conta e utilizador
                # Embora não seja 100% infalível (UPDATE pode não mudar nada mas afetar 1 row),
                # serve como uma verificação básica.
                if cur.rowcount == 0: # Se nem a conta nem o utilizador foram atualizados
                     # Uma verificação mais precisa envolveria checar cur.rowcount após cada UPDATE,
                     # mas essa abordagem combinada já pega casos onde o ID da conta/utilizador não existe
                     flash('Erro: Cliente ou utilizador não encontrado.', 'danger')
                     # Não redireciona, fica na página de edição com o erro
                     # Recarrega os dados para exibir o estado atual (ou 'não encontrado')
                     cur.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                     cliente = cur.fetchone()
                     cur.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s AND id = %s LIMIT 1", (conta_id, utilizador_id))
                     utilizador_principal = cur.fetchone()
                     return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)


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
                # Assumimos o primeiro utilizador encontrado ORDER BY id LIMIT 1
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
        # Para requisições GET com erro, tenta buscar os dados novamente para re-renderizar com erro
        # Se a busca original falhou totalmente, cliente/utilizador_principal serão None e o template tratará
        if request.method == 'GET':
             try:
                 conn_retry = get_db_connection()
                 with conn_retry.cursor(cursor_factory=RealDictCursor) as cur_retry:
                      cur_retry.execute("SELECT * FROM contas WHERE id = %s", (conta_id,))
                      cliente = cur_retry.fetchone()
                      if cliente:
                          cur_retry.execute("SELECT id, nome, email, is_admin FROM utilizadores WHERE conta_id = %s ORDER BY id LIMIT 1", (conta_id,))
                          utilizador_principal = cur_retry.fetchone()
                          if not utilizador_principal:
                               utilizador_principal = {'id': None, 'nome': 'N/A', 'email': 'N/A', 'is_admin': False}
                 if conn_retry: conn_retry.close()
             except Exception as retry_e:
                 print(f"Erro no retry ao carregar dados do cliente para edição: {retry_e}")
                 cliente = None
                 utilizador_principal = None
        # Se for POST e der erro, a lógica de validação/rollback já lida com o retorno
        pass


    finally:
        if conn:
            conn.close()

    # Renderiza o template com os dados (para GET) ou após falha no POST que não redirecionou
    return render_template('editar_cliente.html', cliente=cliente, utilizador=utilizador_principal)


# --- Rota de Logout para a Área Admin (opcional, pode usar o logout da área auth) ---
# @admin_bp.route('/logout')
# @requires_admin # Protege esta rota
# def logout():
#     logout_user() # Função do Flask-Login
#     flash('Você saiu da sessão administrativa.', 'info')
#     return redirect(url_for('auth.login')) # Redireciona para a página de login principal
