# utils/fluxo_vendas.py
from utils.db_utils import get_db_connection
from datetime import datetime

# Função auxiliar (opcional, mas boa para clareza)
def _get_product_info(cur, prod_id):
    """Busca nome e preço de um produto pelo ID."""
    cur.execute("SELECT nome, preco FROM produtos WHERE id = %s", (prod_id,))
    produto = cur.fetchone()
    if produto:
        return produto[0], float(produto[1]) # Converte preco para float
    return None, None # Retorna None para ambos se não encontrar o produto

def listar_categorias():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT categoria FROM produtos WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
        categorias = [row[0] for row in cur.fetchall()]
        if categorias:
            response_text = "Temos produtos nas seguintes categorias:\n"
            for i, cat in enumerate(categorias):
                response_text += f"{i+1}. {cat.capitalize()}\n" # Adiciona número para facilitar a escolha
            response_text += "\nPara ver os produtos de uma categoria, digite o número correspondente."
            return response_text
        else:
            return "No momento, não temos categorias de produtos cadastradas."
    except Exception as e:
        print(f"Erro ao listar categorias: {e}")
        return "Ocorreu um erro ao listar categorias. Tente novamente mais tarde."
    finally:
        if conn:
            conn.close()

def listar_produtos_categoria(categoria):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, preco FROM produtos WHERE LOWER(categoria) = LOWER(%s) AND ativo = TRUE ORDER BY nome ASC", (categoria,))
        produtos = cur.fetchall()
        if produtos:
            response_text = f"Produtos na categoria '{categoria.capitalize()}':\n"
            for produto in produtos:
                response_text += f"- {produto[0]}: {produto[1]} - R${float(produto[2]):.2f}\n" # Formata o preço
            response_text += "\nPara adicionar, digite 'add <ID do produto> <quantidade>'. Ex: 'add 1 2'"
            return response_text
        else:
            return f"Não encontramos produtos ativos na categoria '{categoria.capitalize()}'."
    except Exception as e:
        print(f"Erro ao listar produtos por categoria: {e}")
        return "Ocorreu um erro ao listar produtos por categoria. Tente novamente mais tarde."
    finally:
        if conn:
            conn.close()

def adicionar_ao_carrinho(sender_number, prod_id, quantidade):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if quantidade <= 0:
            return "A quantidade deve ser um número positivo para adicionar ao carrinho."
        prod_nome, prod_preco = _get_product_info(cur, prod_id)
        if not prod_nome or not prod_preco: # Verifica ambos nome e preço
            return "Produto não encontrado ou indisponível. Verifique o ID e tente novamente."
        cur.execute("SELECT id, produtos_vendidos, valor_total FROM vendas WHERE cliente_id = %s AND status = 'aberto'", (sender_number,))
        venda_ativa = cur.fetchone()
        if not venda_ativa:
            # Cria um novo carrinho se não houver um 'aberto'
            produtos_no_carrinho_str = f"{prod_id}x{quantidade}" # Inicializa com o primeiro item
            valor_total = prod_preco * quantidade
            cur.execute("INSERT INTO vendas (cliente_id, produtos_vendidos, valor_total, status) VALUES (%s, %s, %s, %s) RETURNING id", (sender_number, produtos_no_carrinho_str, valor_total, 'aberto'))
            conn.commit()
            return f"{quantidade}x {prod_nome} adicionado(s) ao seu carrinho."
        else:
            # Atualiza o carrinho existente
            venda_id, produtos_vendidos_str, valor_total_atual = venda_ativa
            produtos_no_carrinho_dict = {}
            if produtos_vendidos_str:
                for item in produtos_vendidos_str.split(','):
                    if not item.strip(): # Pula itens vazios após o split
                        continue
                    try:
                        p_id, p_qty = map(int, item.split('x'))
                        produtos_no_carrinho_dict[p_id] = produtos_no_carrinho_dict.get(p_id, 0) + p_qty
                    except ValueError:
                        print(f"Erro de formato de item no carrinho para {sender_number}: {item}")
                        continue
            produtos_no_carrinho_dict[prod_id] = produtos_no_carrinho_dict.get(prod_id, 0) + quantidade
            produtos_vendidos_atualizado_list = [f"{p_id}x{p_qty}" for p_id, p_qty in produtos_no_carrinho_dict.items() if p_qty > 0]
            produtos_vendidos_atualizado_str = ','.join(produtos_vendidos_atualizado_list)
            valor_total_novo = valor_total_atual + (prod_preco * quantidade) # Calcula valor do item
            cur.execute("UPDATE vendas SET produtos_vendidos = %s, valor_total = %s WHERE id = %s", (produtos_vendidos_atualizado_str, valor_total_novo, venda_id))
            conn.commit()
            return f"{quantidade}x {prod_nome} adicionado(s) ao seu carrinho."
    except Exception as e:
        print(f"Erro ao adicionar ao carrinho para {sender_number}: {e}")
        return "Ocorreu um erro ao adicionar o produto ao carrinho. Tente novamente mais tarde."
    finally:
        if conn:
            conn.close()

def ver_carrinho(sender_number):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT produtos_vendidos, valor_total FROM vendas WHERE cliente_id = %s AND status = 'aberto'", (sender_number,))
        venda_ativa = cur.fetchone()
        if not venda_ativa:
            return "Seu carrinho está vazio."
        produtos_vendidos_str, valor_total_carrinho = venda_ativa
        response_text = "Seu carrinho atual:\n"
        itens_para_exibir = []
        if produtos_vendidos_str:
            for item_str in produtos_vendidos_str.split(','):
                if not item_str.strip(): # Pula itens vazios após o split
                    continue
                try:
                    prod_id, quantidade = map(int, item_str.split('x'))
                    if quantidade <= 0: # Pula itens com quantidade zero ou negativa
                        continue
                    nome_produto, preco_produto = _get_product_info(cur, prod_id)
                    if nome_produto and preco_produto: # Verifica ambos nome e preço
                        itens_para_exibir.append(f"- {quantidade}x {nome_produto} (R${(preco_produto * quantidade):.2f})")
                    else:
                        itens_para_exibir.append(f"- {quantidade}x Produto ID {prod_id} (não encontrado ou indisponível)")
                except ValueError:
                    itens_para_exibir.append(f"- Item inválido na lista do carrinho: {item_str}")
        if itens_para_exibir:
            response_text += "\n".join(itens_para_exibir)
        else:
            response_text += "Seu carrinho está vazio. (Parece que houve um problema com os itens adicionados anteriormente. Por favor, adicione os produtos novamente.)"
        response_text += f"\n\nTotal: R${float(valor_total_carrinho):.2f}\n\nDigite 'finalizar' para concluir seu pedido."
        return response_text
    except Exception as e:
        print(f"Erro ao verificar carrinho para {sender_number}: {e}")
        return "Ocorreu um erro ao verificar seu carrinho. Tente novamente mais tarde."
    finally:
        if conn:
            conn.close()

def finalizar_compra(sender_number):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM vendas WHERE cliente_id = %s AND status = 'aberto'", (sender_number,))
        venda_ativa = cur.fetchone()

        if not venda_ativa:
            return "Seu carrinho está vazio. Adicione produtos antes de finalizar o pedido."
        
        venda_id = venda_ativa[0]
        cur.execute("UPDATE vendas SET status = 'finalizado' WHERE id = %s", (venda_id,))
        conn.commit()
        return "Pedido finalizado com sucesso! Em breve entraremos em contato para confirmar os detalhes do seu pedido."
    except Exception as e:
        print(f"Erro ao finalizar compra para {sender_number}: {e}")
        return "Ocorreu um erro ao finalizar seu pedido. Tente novamente mais tarde."
    finally:
        if conn:
            conn.close()
