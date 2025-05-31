from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Body
from sqlalchemy.orm import Session
from models.produto import Produto
from database import get_db
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    return db.query(Produto).all()

@router.get("/api/products/ativos")
def get_ativos(db: Session = Depends(get_db)):
    return db.query(Produto).filter(Produto.ativo == True).all()

@router.post("/api/products")
def create_product(
    nome: str = Form(...),
    descricao: str = Form(""),
    preco: float = Form(...),
    ativo: bool = Form(True),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    produto = Produto(nome=nome, descricao=descricao, preco=preco, ativo=ativo)
    if foto:
        filepath = f"{UPLOAD_DIR}/{foto.filename}"
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        produto.foto = "/" + filepath
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto

@router.put("/api/products/{id}")
def edit_product(
    id: int,
    nome: str = Form(...),
    descricao: str = Form(""),
    preco: float = Form(...),
    ativo: bool = Form(True),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    produto = db.query(Produto).get(id)
    if not produto:
        raise HTTPException(404, detail="Produto não encontrado")
    produto.nome = nome
    produto.descricao = descricao
    produto.preco = preco
    produto.ativo = ativo
    if foto:
        filepath = f"{UPLOAD_DIR}/{foto.filename}"
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        produto.foto = "/" + filepath
    db.commit()
    db.refresh(produto)
    return produto

@router.patch("/api/products/{id}/ativo")
def toggle_ativo(
    id: int,
    ativo: bool = Body(...),
    db: Session = Depends(get_db)
):
    produto = db.query(Produto).get(id)
    if not produto:
        raise HTTPException(404, detail="Produto não encontrado")
    produto.ativo = ativo
    db.commit()
    db.refresh(produto)
    return produto

@router.post("/api/products/upload")
def upload_foto(file: UploadFile = File(...)):
    filepath = f"{UPLOAD_DIR}/{file.filename}"
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": "/" + filepath}