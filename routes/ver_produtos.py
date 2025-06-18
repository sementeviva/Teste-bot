from flask import Blueprint, render_template, request, jsonify, Response
# --- NOVOS IMPORTS ---
from flask_login import login_required, current_user

from utils.db_utils import get_db_connection

ver_produtos_bp = Blueprint('ver_produtos_bp', __name__, template_folder='../templates')

@ver_produtos_bp.route('/', methods=['GET'])
@login_required # Protege a rota
def ver_produtos():
    """Mostra os produtos apenas da conta do utilizador logado."""
    conta_id_logada = current_user.conta_id
    conn = None
    produtos = []
    categorias_unicas = []
    nome_filtro = request.args.get('nome', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Obter categorias existentes, mas apenas da conta atual.
            cur.execute("SELECT DISTINCT categoria FROM produtos WHERE conta_id = %s AND categoria IS NOT NULL AND categoria != '' ORDER BY categoria", (conta_id_logada,))
            categorias_unicas = [row[0] for row in cur.fetchall()]

            # A query principal agora filtra os produtos pelo conta_id.
            query = "SELECT id, nome, preco, descricao, categoria, imagem, ativo FROM produtos WHERE conta_id = %s"
            params = [conta_id_logada]

            if nome_filtro:
                query += " AND nome ILIKE %s"
                params.append(f"%{nome_filtro}%")

            query += " ORDER BY nome ASC"
            cur.execute(query, params)
            produtos = cur.fetchall()

    except Exception as e:
        print(f"Erro ao carregar produtos para a conta {conta_id_logada}: {e}")
    finally:
        if conn:
            conn.close()

    return render_template('ver_produtos.html', produtos=produtos, categorias=categorias_unicas, nome_filtro=nome_filtro)


@ver_produtos_bp.route('/excluir/<int:produto_id>', methods=['POST'])
@login_required
def excluir_produto(produto_id):
    """Exclui um produto, garantindo que ele pertence à conta logada."""
    conta_id_logada = current_user.conta_id
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Adicionamos a verificação do conta_id para segurança.
            cur.execute("DELETE FROM produtos WHERE id = %s AND conta_id = %s", (produto_id, conta_id_logada))
            conn.commit()
            # Verificamos se alguma linha foi realmente apagada.
            if cur.rowcount == 0:
                return jsonify({'success': False, 'message': 'Erro: Produto não encontrado ou não pertence à sua conta.'}), 404
            return jsonify({'success': True, 'message': 'Produto excluído com sucesso!'})
    except Exception as e:
        print(f"Erro ao excluir produto {produto_id} da conta {conta_id_logada}: {e}")
        return jsonify({'success': False, 'message': f'Erro ao excluir produto: {e}'})
    finally:
        if conn:
            conn.close()

@ver_produtos_bp.route('/editar_inline', methods=['POST'])
@login_required
def editar_produto_inline():
    """Edita um produto, garantindo que ele pertence à conta logada."""
    conta_id_logada = current_user.conta_id
    conn = None
    try:
        data = request.get_json()
        produto_id = data['id']
        # ... (pega os outros dados do request)
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            # A cláusula WHERE agora verifica tanto o ID do produto quanto o ID da conta.
            cur.execute(
                "UPDATE produtos SET nome = %s, preco = %s, descricao = %s, categoria = %s, ativo = %s WHERE id = %s AND conta_id = %s",
                (data['nome'], data['preco'], data['descricao'], data['categoria'], data['ativo'], produto_id, conta_id_logada)
            )
            conn.commit()
            if cur.rowcount == 0:
                 return jsonify({'success': False, 'message': 'Erro: Produto não encontrado ou não pertence à sua conta.'}), 404
            return jsonify({'success': True, 'message': 'Produto atualizado com sucesso!'})
    except Exception as e:
        print(f"Erro ao editar produto inline {data.get('id')} da conta {conta_id_logada}: {e}")
        return jsonify({'success': False, 'message': f'Erro ao atualizar produto: {e}'})
    finally:
        if conn:
            conn.close()

@ver_produtos_bp.route('/imagem/<int:produto_id>')
@login_required
def imagem_produto(produto_id):
    """Serve a imagem de um produto, garantindo que pertence à conta logada."""
    conta_id_logada = current_user.conta_id
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Adicionamos a verificação do conta_id para a segurança dos dados.
            cur.execute("SELECT imagem FROM produtos WHERE id = %s AND conta_id = %s", (produto_id, conta_id_logada))
            result = cur.fetchone()
            if result and result[0]:
                return Response(result[0], mimetype='image/jpeg')
            else:
                return "Imagem não encontrada", 404
    except Exception as e:
        print(f"Erro ao buscar imagem {produto_id} da conta {conta_id_logada}: {e}")
        return "Erro ao buscar imagem", 500
    finally:
        if conn:
            conn.close()

