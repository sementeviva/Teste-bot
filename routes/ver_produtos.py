from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, send_file, current_app, jsonify
)
import psycopg2
import os
from io import BytesIO

ver_produtos_bp = Blueprint('ver_produtos', __name__, template_folder='../templates')

def get_db_connection():
    # CONFIRA se sua função está igual ou ajuste para seu ambiente!
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

# 1. Página com produtos e edição inline
@ver_produtos_bp.route('/ver_produtos/', methods=['GET'])
def ver_produtos():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, preco, descricao, categoria, imagem, ativo FROM produtos")
        produtos = cur.fetchall()
        categorias_unicas = sorted({p[4] for p in produtos if p[4]})  # lista única de categorias
    except Exception as e:
        current_app.logger.exception("Erro ao listar produtos")
        flash(f"Erro ao listar produtos: {e}", "danger")
        produtos = []
        categorias_unicas = []
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
    return render_template(
        'ver_produtos.html',
        produtos=produtos,
        categorias=categorias_unicas
    )

# 2. Atualização via AJAX (campo texto, número, ativo/inativo)
@ver_produtos_bp.route('/editar_produto/', methods=['POST'])
def editar_produto():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            UPDATE produtos
            SET nome=%s, preco=%s, descricao=%s, categoria=%s, ativo=%s
            WHERE id=%s
        """
        cur.execute(
            query,
            (
                data['nome'],
                float(data['preco']),
                data['descricao'],
                data['categoria'],
                data['ativo'],
                data['id']
            )
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Produto atualizado!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

# 3. Upload de imagem
@ver_produtos_bp.route('/upload_imagem/<int:produto_id>', methods=['POST'])
def upload_imagem(produto_id):
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado.'})
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado.'})
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE produtos SET imagem = %s WHERE id = %s", (psycopg2.Binary(file.read()), produto_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Imagem enviada!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

# 4. Visualização de imagem
@ver_produtos_bp.route('/imagem/<int:produto_id>')
def imagem_produto(produto_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT imagem FROM produtos WHERE id = %s", (produto_id,))
        imagem = cur.fetchone()
        if imagem and imagem[0]:
            return send_file(BytesIO(imagem[0]), mimetype='image/jpeg')
        return "Imagem não encontrada", 404
    except Exception as e:
        return f"Erro: {e}", 500
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
