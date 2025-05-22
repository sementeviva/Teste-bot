from flask import Blueprint, render_template
from database import get_connection

ver_produtos_bp = Blueprint("ver_produtos", __name__)

@ver_produtos_bp.route("/ver-produtos")
def ver_produtos():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nome, descricao, preco, categoria FROM produtos")
    produtos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("ver_produtos.html", produtos=produtos)
