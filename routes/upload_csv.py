import os
import pandas as pd
import psycopg2
from flask import Blueprint, request, flash, redirect, url_for, render_template
from werkzeug.utils import secure_filename

upload_csv_bp = Blueprint('upload_csv', __name__, template_folder='../templates')

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx'}

@upload_csv_bp.route('/', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        # Ajuste para nome do campo no form: name="csv_file"
        if 'csv_file' not in request.files:
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)

        file = request.files['csv_file']

        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join('/tmp', filename)
            file.save(filepath)
            try:
                # Suporte a CSV e Excel
                if filename.lower().endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)

                conn = get_db_connection()
                cur = conn.cursor()
                for _, row in df.iterrows():
                    cur.execute(
                        "INSERT INTO produtos (nome, descricao, preco, categoria) VALUES (%s, %s, %s, %s)",
                        (
                            row.get('nome', ''),
                            row.get('descricao', ''),
                            float(row.get('preco', 0)),
                            row.get('categoria', '')
                        )
                    )
                conn.commit()
                cur.close()
                conn.close()
                flash('Arquivo carregado com sucesso!', 'success')
                return redirect(url_for('ver_produtos.ver_produtos'))
            except Exception as e:
                flash(f"Erro ao processar o arquivo: {e}", 'danger')
                return redirect(request.url)
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Tipo de arquivo não suportado! Apenas .csv ou .xlsx.', 'danger')
            return redirect(request.url)
    return render_template('upload_csv.html')
