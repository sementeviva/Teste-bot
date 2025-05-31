from flask import Blueprint, render_template
import psycopg2
import os

ver_produtos_bp = Blueprint('ver_produtos_bp', __name__)

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

@ver_produtos_bp.route("/ver_produtos", methods=["GET"])
def ver_produtos():
    produtos = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, preco, categoria, descricao, ativo, imagem FROM produtos")
        rows = cur.fetchall()
        for row in rows:
            produtos.append({
                "id": row[0],
                "nome": row[1],
                "preco": row[2],
                "categoria": row[3],
                "descricao": row[4],
                "ativo": row[5],
                "imagem": row[6]
            })
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
    return render_template('ver_produtos.html', produtos=produtos)
