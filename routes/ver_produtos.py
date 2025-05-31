from flask import Blueprint, render_template, request, redirect, url_for, flash
import psycopg2
import os
from werkzeug.utils import secure_filename

ver_produtos_bp = Blueprint("ver_produtos_bp", __name__)

UPLOAD_FOLDER = "static/produtos_imgs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        port=os.environ.get("DB_PORT", 5432)
    )

@ver_produtos_bp.route("/ver_produtos", methods=["GET", "POST"])
def ver_produtos():
    # Filtros  
    nome_filtro = request.args.get("nome", "")
    categoria_filtro = request.args.get("categoria", "")
    ativo_filtro = request.args.get("ativo", "")

    produtos = []
    categorias = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Listar categorias para filtro
        cur.execute("SELECT DISTINCT categoria FROM produtos")
        categorias = [linha[0] for linha in cur.fetchall()]

        # Montar query de busca
        busca = "SELECT id, nome, preco, categoria, descricao, ativo, imagem FROM produtos WHERE 1=1"
        params = []
        if nome_filtro:
            busca += " AND nome ILIKE %s"
            params.append(f"%{nome_filtro}%")
        if categoria_filtro:
            busca += " AND categoria = %s"
            params.append(categoria_filtro)
        if ativo_filtro:
            busca += " AND ativo = %s"
            params.append(ativo_filtro == "True")
        busca += " ORDER BY nome"

        cur.execute(busca, params)
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
        flash(f"Erro ao buscar produtos: {e}", "danger")
    return render_template("ver_produtos.html", produtos=produtos, categorias=categorias,
                           nome_filtro=nome_filtro, categoria_filtro=categoria_filtro, ativo_filtro=ativo_filtro)

@ver_produtos_bp.route("/editar_produto/<int:id>", methods=["GET", "POST"])
def editar_produto(id):
    if request.method == "POST":
        nome = request.form["nome"]
        preco = request.form["preco"]
        categoria = request.form["categoria"]
        descricao = request.form["descricao"]

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE produtos SET nome=%s, preco=%s, categoria=%s, descricao=%s WHERE id=%s
            """, (nome, preco, categoria, descricao, id))
            conn.commit()
            cur.close()
            conn.close()
            flash("Produto atualizado com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao atualizar produto: {e}", "danger")
        return redirect(url_for("ver_produtos_bp.ver_produtos"))

    # GET
    produto = {}
    categorias = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, preco, categoria, descricao, ativo, imagem FROM produtos WHERE id=%s", (id,))
        row = cur.fetchone()
        if row:
            produto = {
                "id": row[0],
                "nome": row[1],
                "preco": row[2],
                "categoria": row[3],
                "descricao": row[4],
                "ativo": row[5],
                "imagem": row[6]
            }
        cur.execute("SELECT DISTINCT categoria FROM produtos")
        categorias = [linha[0] for linha in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Erro ao buscar produto: {e}", "danger")
    return render_template("editar_produto.html", produto=produto, categorias=categorias)

@ver_produtos_bp.route("/ativar_produto/<int:id>")
def ativar_produto(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Alterna campo ativo para o contrário
        cur.execute("UPDATE produtos SET ativo = NOT ativo WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        flash("Produto ativado/desativado!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar produto: {e}", "danger")
    return redirect(url_for("ver_produtos_bp.ver_produtos"))

@ver_produtos_bp.route("/upload_imagem/<int:id>", methods=["POST"])
def upload_imagem(id):
    if "imagem" not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(url_for("ver_produtos_bp.ver_produtos"))
    file = request.files["imagem"]
    if file and allowed_file(file.filename):
        filename = f"produto_{id}_" + secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        # Salva caminho da imagem no banco
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE produtos SET imagem=%s WHERE id=%s", (filepath, id))
            conn.commit()
            cur.close()
            conn.close()
            flash("Imagem enviada!", "success")
        except Exception as e:
            flash(f"Erro ao atualizar a imagem: {e}", "danger")
    else:
        flash("Arquivo inválido!", "danger")
    return redirect(url_for("ver_produtos_bp.ver_produtos"))