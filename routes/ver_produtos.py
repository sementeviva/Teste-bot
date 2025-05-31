# routes/ver_produtos.py

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
)
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
    """Exibe lista dos produtos com filtros opcionais."""
    nome = request.args.get('nome', '').strip()
    categoria = request.args.get('categoria', '').strip()
    status = request.args.get('status', '').strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = "SELECT id, nome, descricao, preco, categoria, ativo, imagem FROM produtos WHERE TRUE"
        params = []
        if nome:
            query += " AND nome ILIKE %s"
            params.append(f"%{nome}%")
        if categoria:
            query += " AND categoria = %s"
            params.append(categoria)
        if status:
            # status deve ser 'ativo' ou 'inativo'
            if status.lower() == 'ativo':
                query += " AND ativo = TRUE"
            elif status.lower() == 'inativo':
                query += " AND ativo = FALSE"

        query += " ORDER BY id"
        cur.execute(query, params)

        produtos = []
        for row in cur.fetchall():
            produtos.append({
                'id': row[0],
                'nome': row[1],
                'descricao': row[2],
                'preco': row[3],
                'categoria': row[4],
                'ativo': row[5],
                'imagem_url': url_for('ver_produtos.imagem_produto', produto_id=row[0]) if row[6] else None
            })

        # Para preencher o filtro de categorias com opções únicas presentes no DB
        categorias_unicas = sorted(set(p['categoria'] for p in produtos if p['categoria']))
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
        categorias=categorias_unicas,
        nome_filtro=nome,
        categoria_filtro=categoria,
        ativo_filtro=status
    )

@ver_produtos_bp.route('/upload_imagem/<int:produto_id>', methods=['POST'])
def upload_imagem(produto_id):
    """Rota para upload de uma imagem associada ao produto."""
    if 'imagem' not in request.files:
        flash('Nenhum arquivo de imagem selecionado.', 'danger')
        return redirect(url_for('ver_produtos.ver_produtos'))
    imagem = request.files['imagem']
    if not imagem or imagem.filename == '':
        flash('Nenhum arquivo de imagem selecionado.', 'danger')
        return redirect(url_for('ver_produtos.ver_produtos'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Salva o arquivo binário no campo imagem
        cur.execute("UPDATE produtos SET imagem = %s WHERE id = %s", (psycopg2.Binary(imagem.read()), produto_id))
        conn.commit()
        flash("Imagem enviada com sucesso!", "success")
    except Exception as e:
        current_app.logger.exception("Erro ao fazer upload da imagem")
        flash(f"Erro ao fazer upload da imagem: {e}", "danger")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
    return redirect(url_for('ver_produtos.ver_produtos'))

@ver_produtos_bp.route('/imagem/<int:produto_id>')
def imagem_produto(produto_id):
    """Serve a imagem binária de um produto."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT imagem FROM produtos WHERE id = %s", (produto_id,))
        result = cur.fetchone()
        if result and result[0]:
            # JPEG é padrão, ajuste se usar outros formatos
            return send_file(BytesIO(result[0]), mimetype='image/jpeg')
        else:
            flash("Imagem não encontrada.", "warning")
            return '', 404
    except Exception as e:
        current_app.logger.exception(f"Erro ao recuperar a imagem do produto {produto_id}")
        return f"Erro ao recuperar a imagem: {e}", 500
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
