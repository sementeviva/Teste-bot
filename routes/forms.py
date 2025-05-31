from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from wtforms.validators import DataRequired

class UploadCSVForm(FlaskForm):
    file = FileField('Arquivo CSV', validators=[DataRequired()])
    submit = SubmitField('Enviar')
