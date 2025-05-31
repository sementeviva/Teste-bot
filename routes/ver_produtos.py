# routes/ver_produtos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
import psycopg2
import os
from io import BytesIO

ver_produtos_bp = Blueprint('ver_produtos', __name__, template_folder='../templates')

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

@ver_produtos_bp.route('/', methods=['GET'])
def ver_produtos():
    nome = request.args.get('nome', '')
    categoria = request.args.get('categoria', '')
    status = request.args.get('status', '')
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT id, nome, descricao, preco, categoria, ativo, imagem FROM produtos WHERE 1=1"
    params = []
    if nome:
        query += " AND nome ILIKE %s"
        params.append(f"%{nome}%")
    if categoria:
        query += " AND categoria = %s"
        params.append(categoria)
    if status:
        query += " AND ativo = %s"
        params.append(status == 'ativo')
    query += " ORDER BY id"
    cur.execute(query, params)
    produtos = []
    for row in cur.fetchall():
        produto = {
            'id': row[0],
            'nome': row[1],
            'descricao': row[2],
            'preco': row[3],
            'categoria': row[4],
            'ativo': row[5],
            'imagem_url': url_for('ver_produtos.imagem_produto', produto_id=row[0]) if row[6] else None
        }
        produtos.append(produto)
    cur.close()
    conn.close()
    # Ajuste as categorias conforme seu banco:
    categorias = [p['categoria'] for p in produtos]
    categorias_unicas = sorted(set(categorias))
    return render_template(
        'ver_produtos.html',
        produtos=produtos,
        categorias=categorias_unicas,
        nome_filtro=nome,
        categoria_filtro=categoria,
        ativo_filtro=status
    )

@ver_produtos_bp.route('/upload_imagem/<int:produto_id>', methods=['POST'])
def upload_imagem(produto_id):
    if 'imagem' not in request.files:
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(url_for('ver_produtos.ver_produtos'))
    imagem = request.files['imagem']
    if imagem.filename == '':
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(url_for('ver_produtos.ver_produtos'))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE produtos SET imagem = %s WHERE id = %s", (psycopg2.Binary(imagem.read()), produto_id))
        conn.commit()
        flash("Upload de imagem realizado com sucesso!", "success")
    except Exception as e:
        current_app.logger.exception("Erro ao fazer upload da imagem")
        flash(f"Erro ao fazer upload da imagem: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('ver_produtos.ver_produtos'))

@ver_produtos_bp.route('/imagem/<int:produto_id>')
def imagem_produto(produto_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT imagem FROM produtos WHERE id = %s", (produto_id,))
        imagem = cur.fetchone()[0]
        if imagem:
            return send_file(BytesIO(imagem), mimetype='image/jpeg')
        else:
            return "Imagem não encontrada", 404
    except Exception as e:
        current_app.logger.exception(f"Erro ao recuperar a imagem: {e}")
        return f"Erro ao recuperar a imagem: {e}", 500
    finally:
        cur.close()
        conn.close()
