from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, nome, email, conta_id, is_admin=False):
        self.id = id
        self.nome = nome
        self.email = email
        self.conta_id = conta_id
        self.is_admin = is_admin

    # O Flask-Login usa este método para obter o ID do utilizador
    def get_id(self):
        return str(self.id)
