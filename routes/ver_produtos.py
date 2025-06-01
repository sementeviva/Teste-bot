from flask import Blueprint, render_template, request, jsonify # Adicionado 'request' e 'jsonify'
from utils.db_utils import get_db_connection

ver_produtos_bp = Blueprint('ver_produtos_bp', __name__, template_folder='../templates')

@ver_produtos_bp.route('/', methods=['GET'])
def ver_produtos():
    conn = None
    produtos = []
    categorias_unicas = []
    nome_filtro = request.args.get('nome', '') # Pega o valor do filtro de nome da URL

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Obter categorias existentes para o campo de seleção (para edição inline)
            cur.execute("SELECT DISTINCT categoria FROM produtos WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
            categorias_unicas = [row[0] for row in cur.fetchall()]

            query = "SELECT id, nome, preco, descricao, categoria, imagem, ativo FROM produtos WHERE 1=1"
            params = []

            if nome_filtro:
                query += " AND nome ILIKE %s" # ILIKE para case-insensitive no PostgreSQL
                params.append(f"%{nome_filtro}%") # Passa o parâmetro para o filtro

            query += " ORDER BY nome ASC" # ORDENAÇÃO ALFABÉTICA SEMPRE

            cur.execute(query, params)
            produtos = cur.fetchall()

    except Exception as e:
        # Aqui você pode querer logar o erro com current_app.logger.exception
        print(f"Erro ao carregar produtos: {e}")
        # flash('Erro ao carregar produtos.', 'danger') # Se quiser usar flash messages
    finally:
        if conn:
            conn.close()

    return render_template('ver_produtos.html', produtos=produtos, categorias=categorias_unicas, nome_filtro=nome_filtro)


# Rota para exclusão de produto - NOVO
@ver_produtos_bp.route('/excluir/<int:produto_id>', methods=['POST'])
def excluir_produto(produto_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Produto excluído com sucesso!'})
    except Exception as e:
        # Aqui você pode querer logar o erro com current_app.logger.exception
        print(f"Erro ao excluir produto: {e}")
        return jsonify({'success': False, 'message': f'Erro ao excluir produto: {e}'})
    finally:
        if conn:
            conn.close()

# Rota para edição inline (já existente, certifique-se que ela exista e esteja funcional)
@ver_produtos_bp.route('/editar_inline', methods=['POST'])
def editar_produto_inline():
    conn = None
    try:
        data = request.get_json()
        produto_id = data['id']
        nome = data['nome']
        preco = data['preco']
        descricao = data['descricao']
        categoria = data['categoria']
        ativo = data['ativo']

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE produtos SET nome = %s, preco = %s, descricao = %s, categoria = %s, ativo = %s WHERE id = %s",
                (nome, preco, descricao, categoria, ativo, produto_id)
            )
            conn.commit()
            return jsonify({'success': True, 'message': 'Produto atualizado com sucesso!'})
    except Exception as e:
        print(f"Erro ao editar produto inline: {e}")
        return jsonify({'success': False, 'message': f'Erro ao atualizar produto: {e}'})
    finally:
        if conn:
            conn.close()

# Rota para imagem do produto (já existente)
@ver_produtos_bp.route('/imagem/<int:produto_id>')
def imagem_produto(produto_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT imagem FROM produtos WHERE id = %s", (produto_id,))
            result = cur.fetchone()
            if result and result[0]:
                # Certifique-se de que 'result[0]' é um objeto bytes da imagem
                return Response(result[0], mimetype='image/jpeg') # Ajuste o mimetype conforme o tipo da sua imagem
            else:
                return "Imagem não encontrada", 404
    except Exception as e:
        print(f"Erro ao buscar imagem: {e}")
        return "Erro ao buscar imagem", 500
    finally:
        if conn:
            conn.close()
