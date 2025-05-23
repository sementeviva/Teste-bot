from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Conversa(Base):
    __tablename__ = 'conversas'

    id = Column(Integer, primary_key=True)
    usuario = Column(String, nullable=False)
    mensagem = Column(String, nullable=False)
    resposta = Column(String, nullable=True)
    data_hora = Column(DateTime, default=datetime.utcnow)
