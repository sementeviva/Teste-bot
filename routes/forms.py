from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from wtforms.validators import DataRequired

class UploadForm(FlaskForm):
    csv_file = FileField('Arquivo CSV ou Excel', validators=[DataRequired()])
    submit = SubmitField('Enviar')
