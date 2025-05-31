# routes/upload_csv.py
import os
import pandas as pd
import psycopg2
from flask import Blueprint, request, flash, redirect, url_for, render_template

upload_csv_bp = Blueprint('upload_csv', __name__, template_folder='../templates')

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

@upload_csv_bp.route('/', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        if file:
            try:
                df = pd.read_csv(file)
                conn = get_db_connection()
                cur = conn.cursor()
                for _, row in df.iterrows():
                    cur.execute(
                        "INSERT INTO produtos (nome, descricao, preco, categoria, ativo) VALUES (%s, %s, %s, %s, %s)",
                        (row['nome'], row['descricao'], row['preco'], row['categoria'], row['ativo'])
                    )
                conn.commit()
                cur.close()
                conn.close()
                flash('CSV carregado com sucesso!', 'success')
                return redirect(url_for('ver_produtos.ver_produtos'))
            except Exception as e:
                flash(f"Erro ao processar CSV: {e}", 'danger')
                return redirect(request.url)
    return render_template('upload_csv.html')
