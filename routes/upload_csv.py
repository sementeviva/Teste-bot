from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import pandas as pd

# --- NOVOS IMPORTS ---
from flask_login import login_required, current_user
from utils.db_utils import get_db_connection
from .forms import UploadCSVForm

upload_csv_bp = Blueprint('upload_csv_bp', __name__, template_folder='../templates')

@upload_csv_bp.route('/', methods=['GET', 'POST'])
@login_required # Protege a rota, apenas utilizadores logados podem fazer upload.
def upload_csv():
    """
    Permite o upload de um CSV de produtos, associando todos os novos
    produtos à conta do utilizador atualmente logado.
    """
    form = UploadCSVForm()
    if form.validate_on_submit():
        # Obtém o ID da conta a partir da sessão do utilizador logado.
        conta_id_logada = current_user.conta_id
        
        file = form.file.data
        filename = secure_filename(file.filename)
        filepath = os.path.join('/tmp', filename) # Usa uma pasta temporária segura
        file.save(filepath)
        
        conn = None
        try:
            # Lê o ficheiro CSV com o pandas
            df = pd.read_csv(filepath)
            
            # Conecta-se ao banco de dados para fazer a inserção
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Itera sobre cada linha do ficheiro CSV
                for _, row in df.iterrows():
                    # A query de inserção agora inclui o 'conta_id'
                    cur.execute(
                        """
                        INSERT INTO produtos (conta_id, nome, descricao, preco, categoria, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            conta_id_logada,
                            row.get('nome'),
                            row.get('descricao'),
                            row.get('preco'),
                            row.get('categoria'),
                            True # Define o produto como ativo por padrão
                        )
                    )
            conn.commit() # Salva todas as inserções no banco
            flash(f'{len(df)} produtos importados com sucesso!', 'success')
            
        except Exception as e:
            if conn: conn.rollback() # Desfaz as alterações em caso de erro
            flash(f"Ocorreu um erro ao processar o ficheiro: {e}", "danger")
            print(f"Erro no upload de CSV para conta {conta_id_logada}: {e}")
        finally:
            # Garante que a conexão seja fechada e o ficheiro temporário removido
            if conn:
                conn.close()
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Redireciona de volta para a mesma página de upload
        return redirect(url_for('upload_csv_bp.upload_csv'))
        
    return render_template('upload_csv.html', form=form)


