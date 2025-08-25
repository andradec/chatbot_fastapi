from fastapi import FastAPI
from contextlib import asynccontextmanager
from data_test.valida_dados import validar_dados
from backend.seed import seed_db_from_files
from frontend.api import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Antes de iniciar o servidor, valida e carrega o seed
    if not validar_dados():
        raise Exception("Falha na validação/limpeza de dados.")
    seed_db_from_files()
    print("✅ Dados validados e seed carregado.")
    yield
    # Aqui poderia entrar lógica de "shutdown", se precisar

# FastAPI App
app = FastAPI(
    title="Chatbot Vendas/Produtos/Vendedores",
    lifespan=lifespan
)

# Inclui todas as rotas definidas em frontend/api.py
app.include_router(api_router, prefix="/api")
