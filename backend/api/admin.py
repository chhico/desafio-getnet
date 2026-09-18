from fastapi import APIRouter
from backend.infrastructure.rag.sync_web import run_sync

router = APIRouter()

@router.post("/sync-web", tags=["Admin"])
async def trigger_web_sync(force: bool = False):
    """Dispara a sincronização recursiva das URLs parametrizadas para o RAG."""
    run_sync(force=force)
    return {"message": "Sincronização web concluída com sucesso."}
