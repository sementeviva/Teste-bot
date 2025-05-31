from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from .forms import UploadCSVForm   # Importa o formulário
import os
import pandas as pd

upload_csv_bp = Blueprint('upload_csv', __name__, template_folder='../templates')

@upload_csv_bp.route('/upload/', methods=['GET', 'POST'])
def upload_csv():
    form = UploadCSVForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        filepath = os.path.join('/tmp', filename)
        file.save(filepath)
        try:
            df = pd.read_csv(filepath)
            # Seu processamento aqui
            flash('Arquivo enviado com sucesso!', 'success')
        except Exception as e:
            flash(f"Erro ao processar arquivo: {e}", "danger")
        finally:
            os.remove(filepath)
        return redirect(url_for('upload_csv.upload_csv'))
        
    return render_template('upload_csv.html', form=form)
