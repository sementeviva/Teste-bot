# routes/__init__.py
from .upload_csv import upload_csv_bp
from .ver_produtos import ver_produtos_bp
from .edit_produtos import edit_produtos_bp

def register_blueprints(app):
    app.register_blueprint(upload_csv_bp, url_prefix='/upload')
    app.register_blueprint(ver_produtos_bp, url_prefix='/ver_produtos')
    app.register_blueprint(edit_produtos_bp, url_prefix='/edit_produtos')
