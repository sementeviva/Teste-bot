from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app # <--- AQUI: Adicionado 'current_app'
# IMPORTANTE: Removido o 'import psycopg2' e 'import os' daqui
# A função get_db_connection será importada do módulo centralizado
from utils.db_utils import get_db_connection # Importa a função de conexão centralizada

# Renomeado o objeto Blueprint para consistência com app.py se necessário no registro
# Se no app.py você registra: app.register_blueprint(edit_produtos_bp, url_prefix='/edit_produtos')
# e o nome do blueprint é 'edit_produtos', então está ok.
edit_produtos_bp = Blueprint('edit_produtos_bp', __name__, template_folder='../templates')

@edit_produtos_bp.route('/editar/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    conn = None # Inicializa conn para garantir que esteja definida
    produto = None # Para o template
    categorias = [] # Para o template, para popular o select

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Obter categorias existentes para o campo de seleção
            cur.execute("SELECT DISTINCT categoria FROM produtos WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
            categorias = [row[0] for row in cur.fetchall()]

            if request.method == 'POST':
                nome = request.form.get('nome')
                descricao = request.form.get('descricao')
                preco = request.form.get('preco')
                categoria = request.form.get('categoria')
                ativo = request.form.get('ativo') == 'on' # Checkbox retorna 'on' ou None
                
                # Validação básica
                if not nome or not preco or not categoria:
                    flash('Nome, Preço e Categoria são campos obrigatórios.', 'danger')
                    # Tenta manter os dados no formulário em caso de erro
                    produto = {
                        'id': produto_id, 'nome': nome, 'descricao': descricao,
                        'preco': preco, 'categoria': categoria, 'ativo': ativo
                    }
                    return render_template('editar_produto.html', produto=produto, categorias=categorias)

                if produto_id == 0: # Operação de INSERÇÃO
                    cur.execute(
                        """
                        INSERT INTO produtos (nome, descricao, preco, categoria, ativo, data_criacao)
                        VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id
                        """,
                        (nome, descricao, preco, categoria, ativo)
                    )
                    new_id = cur.fetchone()[0] # Obtém o ID do novo produto
                    conn.commit()
                    flash(f'Produto "{nome}" adicionado com sucesso! ID: {new_id}', 'success')
                    # Redireciona para editar o novo produto, ou para a lista geral
                    return redirect(url_for('edit_produtos_bp.editar_produto', produto_id=new_id))
                else: # Operação de ATUALIZAÇÃO
                    cur.execute(
                        "UPDATE produtos SET nome = %s, descricao = %s, preco = %s, categoria = %s, ativo = %s WHERE id = %s",
                        (nome, descricao, preco, categoria, ativo, produto_id)
                    )
                    conn.commit()
                    flash('Produto atualizado com sucesso!', 'success')
                    return redirect(url_for('ver_produtos_bp.ver_produtos')) # Redireciona para a lista
            else: # Método GET: carregar dados para edição ou preparar para novo
                if produto_id == 0: # Criar um novo produto
                    # Passa um dicionário vazio para o template para que os campos fiquem vazios
                    produto = {'id': 0, 'nome': '', 'descricao': '', 'preco': 0.0, 'categoria': '', 'ativo': True}
                else: # Editar um produto existente
                    cur.execute("SELECT id, nome, descricao, preco, categoria, ativo FROM produtos WHERE id = %s", (produto_id,))
                    produto = cur.fetchone()
                    if produto:
                        # Converte a tupla em dicionário para facilitar o acesso no template
                        produto = {
                            'id': produto[0], 'nome': produto[1], 'descricao': produto[2],
                            'preco': produto[3], 'categoria': produto[4], 'ativo': produto[5]
                        }
                    else:
                        flash('Produto não encontrado.', 'danger')
                        return redirect(url_for('ver_produtos_bp.ver_produtos'))

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        current_app.logger.exception(f"Erro na operação de produto (ID: {produto_id})")
        # Em caso de erro grave, redireciona para a lista para evitar tela em branco
        return redirect(url_for('ver_produtos_bp.ver_produtos'))
    finally:
        if conn:
            conn.close()

    # Renderiza o template com o produto (seja existente ou novo) e as categorias
    return render_template('editar_produto.html', produto=produto, categorias=categorias)
