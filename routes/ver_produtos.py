from flask import (
    Blueprint, render_template, request, jsonify,
    current_app, flash, Response
)
# IMPORTANTE: Removido o 'import psycopg2' e 'import os' daqui, pois não são mais necessários diretamente
# E a função get_db_connection será importada do módulo centralizado

# Importa a função de conexão do banco de dados centralizada (Melhoria 2)
from utils.db_utils import get_db_connection

# Renomeado o objeto Blueprint para consistência com app.py
ver_produtos_bp = Blueprint('ver_produtos_bp', __name__, template_folder='../templates')

# Removido get_db_connection() daqui (Melhoria 2)

# Página de listagem e edição dos produtos
@ver_produtos_bp.route('/', methods=['GET']) # Rota simplificada para '/' dentro do Blueprint
def ver_produtos():
    conn = None # Inicializa conn para garantir que esteja definida
    try:
        conn = get_db_connection()
        # Usando 'with' para garantir que o cursor seja fechado
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, preco, descricao, categoria, imagem, ativo FROM produtos")
            produtos = cur.fetchall()
            categorias_unicas = sorted({p[4] for p in produtos if p[4]})
    except Exception as e:
        current_app.logger.exception("Erro ao listar produtos")
        flash(f"Erro ao listar produtos: {e}", "danger")
        produtos = []
        categorias_unicas = []
    finally:
        if conn: # Fecha a conexão se ela foi aberta
            conn.close()
    return render_template('ver_produtos.html', produtos=produtos, categorias=categorias_unicas)

# Edição inline dos produtos (Nome da rota e função ajustados para 'editar_produto_inline')
@ver_produtos_bp.route('/editar_produto_inline', methods=['POST']) # Rota ajustada
def editar_produto_inline(): # Função ajustada
    data = request.get_json()
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
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
        return jsonify({'success': True, 'message': 'Produto atualizado com sucesso!'})
    except Exception as e:
        current_app.logger.exception("Erro ao atualizar produto inline") # Log mais específico
        return jsonify({'success': False, 'message': f"Erro ao atualizar produto: {e}"}) # Mensagem de erro mais útil
    finally:
        if conn:
            conn.close()

# Upload de imagem do produto
@ver_produtos_bp.route('/upload_imagem/<int:produto_id>', methods=['POST'])
def upload_imagem(produto_id):
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado.'})
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado.'})

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE produtos SET imagem = %s WHERE id = %s", (psycopg2.Binary(file.read()), produto_id))
            conn.commit()
        return jsonify({'success': True, 'message': 'Imagem enviada com sucesso!'})
    except Exception as e:
        current_app.logger.exception("Erro ao fazer upload da imagem")
        return jsonify({'success': False, 'message': f"Erro ao fazer upload da imagem: {e}"})
    finally:
        if conn:
            conn.close()

# Visualização da imagem do produto
@ver_produtos_bp.route('/imagem/<int:produto_id>')
def imagem_produto(produto_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT imagem FROM produtos WHERE id = %s", (produto_id,))
            imagem = cur.fetchone()
            if imagem and imagem[0]:
                return Response(imagem[0], mimetype='image/jpeg')
            return "Imagem não encontrada", 404
    except Exception as e:
        current_app.logger.exception("Erro ao recuperar imagem do produto")
        return f"Erro: {e}", 500
    finally:
        if conn:
            conn.close()
