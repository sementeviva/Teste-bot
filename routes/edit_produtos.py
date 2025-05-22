from flask import Blueprint, render_template, request, redirect, url_for, flash
import pandas as pd
import os

edit_produtos_bp = Blueprint("edit_produtos", __name__)

CSV_PATH = "produtos_semente_viva.csv"

@edit_produtos_bp.route("/produtos")
def listar_produtos():
    if not os.path.exists(CSV_PATH):
        flash("Arquivo CSV não encontrado.")
        return redirect(url_for("upload_csv.upload_csv"))

    df = pd.read_csv(CSV_PATH)
    return render_template("listar_produtos.html", produtos=df.to_dict(orient="records"))

@edit_produtos_bp.route("/produtos/editar/<int:index>", methods=["GET", "POST"])
def editar_produto(index):
    df = pd.read_csv(CSV_PATH)

    if request.method == "POST":
        df.loc[index, "nome"] = request.form["nome"]
        df.loc[index, "preco"] = float(request.form["preco"])
        df.loc[index, "descricao"] = request.form["descricao"]
        df.to_csv(CSV_PATH, index=False)
        flash("Produto atualizado com sucesso!")
        return redirect(url_for("edit_produtos.listar_produtos"))

    produto = df.loc[index].to_dict()
    return render_template("editar_produto.html", index=index, produto=produto)
