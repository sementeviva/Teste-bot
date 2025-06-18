from flask import Blueprint, render_template, request, redirect, url_for, flash
# --- NOVOS IMPORTS ---
from flask_login import login_required, current_user

from utils.db_utils import get_db_connection

edit_produtos_bp = Blueprint('edit_produtos_bp', __name__, template_folder='../templates')

@edit_produtos_bp.route('/<int:produto_id>', methods=['GET', 'POST'])
@login_required # Protege toda a rota de edição/criação
def editar_produto(produto_id):
    """
    Gere a criação e edição de produtos, garantindo que todas as operações
    sejam restritas à conta do utilizador logado.
    """
    # Obtém o ID da conta a partir da sessão do utilizador logado.
    conta_id_logada = current_user.conta_id
    conn = None
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Obter categorias existentes, mas apenas da conta atual.
            cur.execute("SELECT DISTINCT categoria FROM produtos WHERE conta_id = %s AND categoria IS NOT NULL AND categoria != '' ORDER BY categoria", (conta_id_logada,))
            categorias = [row[0] for row in cur.fetchall()]

            if request.method == 'POST':
                nome = request.form.get('nome')
                descricao = request.form.get('descricao')
                preco = request.form.get('preco')
                categoria = request.form.get('categoria')
                ativo = 'ativo' in request.form # Forma mais segura de verificar checkbox

                if not nome or not preco or not categoria:
                    flash('Nome, Preço e Categoria são campos obrigatórios.', 'danger')
                    produto = {'id': produto_id, 'nome': nome, 'descricao': descricao, 'preco': preco, 'categoria': categoria, 'ativo': ativo}
                    return render_template('editar_produto.html', produto=produto, categorias=categorias)

                if produto_id == 0: # Operação de INSERÇÃO
                    # Ao inserir, associamos o produto à conta correta.
                    cur.execute(
                        """
                        INSERT INTO produtos (conta_id, nome, descricao, preco, categoria, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                        """,
                        (conta_id_logada, nome, descricao, preco, categoria, ativo)
                    )
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    flash(f'Produto "{nome}" adicionado com sucesso!', 'success')
                    return redirect(url_for('edit_produtos_bp.editar_produto', produto_id=new_id))
                else: # Operação de ATUALIZAÇÃO
                    # A cláusula WHERE agora verifica o ID do produto E o ID da conta para segurança.
                    cur.execute(
                        "UPDATE produtos SET nome = %s, descricao = %s, preco = %s, categoria = %s, ativo = %s WHERE id = %s AND conta_id = %s",
                        (nome, descricao, preco, categoria, ativo, produto_id, conta_id_logada)
                    )
                    conn.commit()
                    if cur.rowcount == 0:
                        flash('Erro: Produto não encontrado ou não pertence à sua conta.', 'danger')
                        return redirect(url_for('ver_produtos_bp.ver_produtos'))
                    flash('Produto atualizado com sucesso!', 'success')
                    return redirect(url_for('ver_produtos_bp.ver_produtos'))
            
            else: # Método GET
                if produto_id == 0: # Criar novo
                    produto = {'id': 0, 'nome': '', 'descricao': '', 'preco': '', 'categoria': '', 'ativo': True}
                else: # Editar existente
                    # A busca pelo produto também filtra pelo conta_id.
                    cur.execute("SELECT id, nome, descricao, preco, categoria, ativo FROM produtos WHERE id = %s AND conta_id = %s", (produto_id, conta_id_logada))
                    p = cur.fetchone()
                    if p:
                        produto = {'id': p[0], 'nome': p[1], 'descricao': p[2], 'preco': f"{p[3]:.2f}", 'categoria': p[4], 'ativo': p[5]}
                    else:
                        flash('Produto não encontrado ou não pertence à sua conta.', 'danger')
                        return redirect(url_for('ver_produtos_bp.ver_produtos'))

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        print(f"Erro na operação de produto (ID: {produto_id}) para conta {conta_id_logada}: {e}")
        return redirect(url_for('ver_produtos_bp.ver_produtos'))
    finally:
        if conn:
            conn.close()

    return render_template('editar_produto.html', produto=produto, categorias=categorias)

