# utils/fluxo_vendas.py
from database import get_connection

def listar_categorias():
    return "Escolha uma categoria:\n1. Chás\n2. Suplementos\n3. Óleos\n4. Veganos"

def listar_produtos_categoria(categoria):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nome, preco FROM produtos
        WHERE LOWER(nome) LIKE %s
    """, (f"%{categoria.lower()}%",))
    produtos = cur.fetchall()
    conn.close()

    if not produtos:
        return "Nenhum produto encontrado nessa categoria."

    resposta = "Produtos encontrados:\n"
    for p in produtos:
        resposta += f"{p[0]}. {p[1].capitalize()} - R$ {p[2]:.2f}\n"
    resposta += "\nDigite o número do produto para adicionar ao carrinho."
    return resposta

def adicionar_ao_carrinho(telefone, id_produto):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO carrinho (telefone, id_produto, quantidade)
        VALUES (%s, %s, 1)
        ON CONFLICT (telefone, id_produto)
        DO UPDATE SET quantidade = carrinho.quantidade + 1
    """, (telefone, id_produto))
    conn.commit()
    conn.close()
    return "Produto adicionado ao carrinho!"

def ver_carrinho(telefone):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.nome, p.preco, c.quantidade
        FROM carrinho c
        JOIN produtos p ON p.id = c.id_produto
        WHERE c.telefone = %s
    """, (telefone,))
    itens = cur.fetchall()
    conn.close()

    if not itens:
        return "Seu carrinho está vazio."

    resposta = "Seu carrinho:\n"
    total = 0
    for nome, preco, quantidade in itens:
        subtotal = preco * quantidade
        total += subtotal
        resposta += f"- {nome.capitalize()} x{quantidade} - R$ {subtotal:.2f}\n"
    resposta += f"\nTotal: R$ {total:.2f}\nDeseja finalizar o pedido? (Sim/Não)"
    return resposta
