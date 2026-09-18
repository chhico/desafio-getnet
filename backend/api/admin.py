from enum import Enum
from fastapi import APIRouter, Query
from backend.infrastructure.rag.sync_web import run_sync

router = APIRouter()


class SyncTarget(str, Enum):
    all = "all"
    files = "files"
    urls = "urls"


@router.post("/sync-web", tags=["Admin"])
async def trigger_web_sync(
    force: bool = Query(
        False, 
        description="Se True, sobrescreve e re-vetoriza os itens existentes. Se False, vetoriza apenas arquivos e URLs que ainda não existam no banco vetor."
    ),
    target: SyncTarget = Query(
        SyncTarget.all, 
        description="Alvo da sincronização: 'files' (arquivos da pasta fonte_de_dados), 'urls' (páginas web) ou 'all' (ambos)"
    )
):
    """
    Dispara a sincronização e vetorização da base de conhecimento (RAG).

    - **force**:
      - `true`: Sobrescreve os arquivos existentes na pasta e as URLs existentes (invalida e reindexa tudo).
      - `false`: Vetoriza apenas os arquivos e URLs que ainda não existam no banco vetor (detectado via hash MD5).
    - **target**:
      - `'files'`: Apenas os arquivos da pasta `fonte_de_dados/`.
      - `'urls'`: Apenas as URLs web configuradas via crawler.
      - `'all'`: Ambos (arquivos físicos locais e URLs web).
    """
    result = run_sync(force=force, target=target.value)
    return {
        "message": "Sincronização concluída com sucesso.",
        "target": target.value,
        "force": force,
        **result
    }
