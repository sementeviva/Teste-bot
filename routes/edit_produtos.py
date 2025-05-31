# routes/edit_produtos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import psycopg2
import os

edit_produtos_bp = Blueprint('edit_produtos', __name__, template_folder='../templates')

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

@edit_produtos_bp.route('/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        preco = request.form.get('preco')
        categoria = request.form.get('categoria')
        ativo = request.form.get('ativo') == 'on'
        try:
            cur.execute(
                "UPDATE produtos SET nome = %s, descricao = %s, preco = %s, categoria = %s, ativo = %s WHERE id = %s",
                (nome, descricao, preco, categoria, ativo, id)
            )
            conn.commit()
            flash('Produto atualizado com sucesso!', 'success')
            return redirect(url_for('ver_produtos.ver_produtos'))
        except Exception as e:
            flash(f'Erro ao atualizar o produto: {e}', 'danger')
        finally:
            cur.close()
            conn.close()
    else:
        cur.execute("SELECT id, nome, descricao, preco, categoria, ativo FROM produtos WHERE id = %s", (id,))
        produto = cur.fetchone()
        cur.close()
        conn.close()
        if produto:
            return render_template('editar_produto.html', produto=produto)
        else:
            flash('Produto não encontrado.', 'danger')
            return redirect(url_for('ver_produtos.ver_produtos'))
