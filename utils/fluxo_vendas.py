from .db_utils import get_db_connection
from datetime import datetime
from psycopg2.extras import RealDictCursor

def _get_product_info(cur, conta_id, prod_id):
    """Função auxiliar para buscar informações de um produto específico de uma conta."""
    cur.execute("SELECT nome, preco FROM produtos WHERE id = %s AND conta_id = %s", (prod_id, conta_id))
    produto = cur.fetchone()
    return (produto['nome'], float(produto['preco'])) if produto else (None, None)

def listar_categorias(conta_id):
    """Lista as categorias de produtos de uma conta específica."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT categoria FROM produtos WHERE conta_id = %s AND categoria IS NOT NULL AND categoria != '' AND ativo = TRUE ORDER BY categoria", (conta_id,))
            return [row['categoria'] for row in cur.fetchall()]
    finally:
        if conn: conn.close()

def listar_produtos_categoria(conta_id, categoria):
    """Lista os produtos de uma categoria específica de uma conta."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, preco FROM produtos WHERE conta_id = %s AND LOWER(categoria) = LOWER(%s) AND ativo = TRUE ORDER BY nome ASC", (conta_id, categoria))
            return cur.fetchall()
    finally:
        if conn: conn.close()

def adicionar_ao_carrinho(conta_id, sender_number, prod_id, quantidade):
    """Adiciona um item ao carrinho/venda de uma conta específica."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if quantidade <= 0: return "A quantidade deve ser positiva."
            
            prod_nome, prod_preco = _get_product_info(cur, conta_id, prod_id)
            if not prod_nome: return "Produto não encontrado. Verifique o ID."

            cur.execute("SELECT id, produtos_vendidos, valor_total FROM vendas WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto'", (conta_id, sender_number))
            venda_ativa = cur.fetchone()

            if not venda_ativa:
                produtos_str = f"{prod_id}x{quantidade}"
                valor_total = prod_preco * quantidade
                cur.execute("INSERT INTO vendas (conta_id, cliente_id, produtos_vendidos, valor_total, status) VALUES (%s, %s, %s, %s, 'aberto')",
                            (conta_id, sender_number, produtos_str, valor_total))
            else:
                venda_id, produtos_str, valor_atual = venda_ativa['id'], venda_ativa['produtos_vendidos'] or "", venda_ativa['valor_total'] or 0.0
                carrinho = {int(p.split('x')[0]): int(p.split('x')[1]) for p in produtos_str.split(',') if 'x' in p}
                carrinho[prod_id] = carrinho.get(prod_id, 0) + quantidade
                produtos_atualizado = ','.join([f"{pid}x{qty}" for pid, qty in carrinho.items()])
                valor_novo = float(valor_atual) + (prod_preco * quantidade)
                cur.execute("UPDATE vendas SET produtos_vendidos = %s, valor_total = %s WHERE id = %s", (produtos_atualizado, valor_novo, venda_id))
            
            conn.commit()
            return f"{quantidade}x {prod_nome} adicionado(s) ao seu carrinho."
    finally:
        if conn: conn.close()

def ver_carrinho(conta_id, sender_number):
    """Mostra o carrinho de um cliente para uma conta específica."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT produtos_vendidos, valor_total FROM vendas WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto'", (conta_id, sender_number))
            venda_ativa = cur.fetchone()

            if not venda_ativa or not venda_ativa['produtos_vendidos']:
                return "Seu carrinho está vazio."

            produtos_str, valor_total = venda_ativa['produtos_vendidos'], venda_ativa['valor_total']
            response_text = "Seu carrinho atual:\n"
            itens_carrinho = [item.split('x') for item in produtos_str.split(',') if 'x' in item]
            
            for prod_id_str, quantidade_str in itens_carrinho:
                prod_id, quantidade = int(prod_id_str), int(quantidade_str)
                nome_produto, _ = _get_product_info(cur, conta_id, prod_id)
                if nome_produto:
                    response_text += f"- {quantidade}x {nome_produto}\n"
            
            response_text += f"\nTotal: R${float(valor_total):.2f}"
            return response_text
    finally:
        if conn: conn.close()

def finalizar_compra(conta_id, sender_number):
    """Finaliza a compra de um cliente para uma conta específica."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM vendas WHERE conta_id = %s AND cliente_id = %s AND status = 'aberto'", (conta_id, sender_number))
            venda_ativa = cur.fetchone()

            if not venda_ativa: return "Seu carrinho está vazio."
            
            venda_id = venda_ativa['id']
            cur.execute("UPDATE vendas SET status = 'finalizado', data_venda = %s WHERE id = %s", (datetime.now(), venda_id))
            conn.commit()
            return "Pedido finalizado com sucesso! Entraremos em contato para confirmar os detalhes."
    finally:
        if conn: conn.close()

