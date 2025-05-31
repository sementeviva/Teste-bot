@@ -0,0 +1,12 @@
from sqlalchemy import Column, Integer, String, Float, Boolean
from database import Base

class Produto(Base):
    __tablename__ = 'produtos'

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    descricao = Column(String)
    preco = Column(Float, nullable=False)
    foto = Column(String)  # caminho ou URL da foto
    ativo = Column(Boolean, default=True)  # produto visível ou não
