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

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Garante que o Swagger UI exiba o botão "Choose Files" para arrays de arquivos
    for schema in openapi_schema.get("components", {}).get("schemas", {}).values():
        if "properties" in schema:
            for prop in schema["properties"].values():
                if prop.get("type") == "array" and "items" in prop:
                    items = prop["items"]
                    if items.get("contentMediaType") == "application/octet-stream":
                        items["format"] = "binary"
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


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

from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/chat/", status_code=307)
    return {
        "message": "Getnet Multi-Agent API está online!",
        "chat": "/chat/",
        "dashboard": "/dashboard/",
        "observabilidade": "/dashboard/",
        "docs": "/docs",
        "health": "/health",
        "frontend": "http://localhost:3001"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

# Inclusão de Rotas (Routers)
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# Suporte ao Frontend no Backend (permite rodar em porta única e túneis Cloudflare)
from pathlib import Path
from fastapi.staticfiles import StaticFiles

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    dashboard_dir = frontend_dir / "dashboard"
    if dashboard_dir.exists():
        logging.info(f"Dashboard de Observabilidade montado com sucesso em /dashboard a partir de: {dashboard_dir}")
        app.mount("/dashboard", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")

    logging.info(f"Interface Web montada com sucesso em /chat a partir de: {frontend_dir}")
    app.mount("/chat", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    @app.get("/observabilidade", include_in_schema=False)
    async def redirect_observabilidade():
        return RedirectResponse(url="/dashboard/", status_code=307)
else:
    logging.warning(f"Diretório frontend não encontrado em: {frontend_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=settings.PORT, reload=True)
