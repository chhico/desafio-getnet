import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.exceptions import DomainException
from backend.api import conversations, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executado na inicialização.
    print("=" * 54)
    print("  [API] Getnet Multi-Agent Customer Support API")
    print("=" * 54)

    import asyncio
    from backend.infrastructure.rag.enrichment_service import (
        init_and_check_rag_tables,
        run_startup_enrichment
    )

    # 1. Verifica e cria tabelas simple_sync_hashes e url_sync_hashes na subida
    init_and_check_rag_tables()

    # 2. Inicia o enriquecimento em background (não-bloqueante)
    asyncio.create_task(run_startup_enrichment())

    yield
    print("Desligando Servidor de API...")

app = FastAPI(
    title="Getnet Multi-Agent Customer Support API",
    version=settings.VERSION,
    description="API de Suporte Multiagente com LangGraph para a Getnet",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Erro Inesperado: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error. Please contact support."},
    )

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Getnet Multi-Agent API está online!",
        "docs": "http://localhost:8001/docs",
        "health": "http://localhost:8001/health",
        "frontend": "http://localhost:3001"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

# Inclusão de Rotas (Routers)
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=True)
