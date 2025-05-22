import os
import csv
import psycopg2
import pandas as pd
from flask import Blueprint, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename

upload_csv_bp = Blueprint('upload_csv', __name__)

DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_PORT = os.environ.get('DB_PORT', 5432)

@upload_csv_bp.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        arquivo = request.files.get('csv_file')
        if not arquivo:
            flash('Nenhum arquivo enviado.')
            return redirect(request.url)

        filename = secure_filename(arquivo.filename)
        extensao = filename.rsplit('.', 1)[1].lower()

        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
            cur = conn.cursor()

            if extensao == 'csv':
                csvfile = arquivo.stream.read().decode('utf-8').splitlines()
                leitor = csv.DictReader(csvfile)
                for linha in leitor:
                    cur.execute("""
                        INSERT INTO produtos (nome, descricao, preco)
                        VALUES (%s, %s, %s)
                    """, (linha['nome'], linha['descricao'], linha['preco']))
            elif extensao == 'xlsx':
                df = pd.read_excel(arquivo)
                df.fillna('', inplace=True)
                for _, row in df.iterrows():
                    cur.execute("""
                        INSERT INTO produtos (nome, descricao, preco)
                        VALUES (%s, %s, %s)
                    """, (row['nome'], row['descricao'], row['preco']))
            else:
                flash('Tipo de arquivo não suportado.')
                return redirect(request.url)

            conn.commit()
            cur.close()
            conn.close()
            flash('Importação concluída com sucesso!')
        except Exception as e:
            flash(f'Erro na importação: {str(e)}')

        return redirect(url_for('upload_csv.upload_csv'))

    return render_template('upload.html')
