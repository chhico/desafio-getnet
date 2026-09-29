import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from enum import Enum
from fastapi import APIRouter, Query, UploadFile, File, HTTPException, status
from backend.infrastructure.rag.sync_web import run_sync

router = APIRouter()

# Formatos de arquivo compatíveis com a biblioteca de ingestão do RAG
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".log"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB por arquivo
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "fonte_de_dados"


class SyncTarget(str, Enum):
    all = "all"
    files = "files"
    urls = "urls"


@router.post("/upload-files-rag", tags=["Admin"])
async def upload_files_rag(
    files: List[UploadFile] = File(
        ...,
        description="Selecione um ou múltiplos arquivos compatíveis (.pdf, .docx, .txt, .md, .csv, .json, .log) para enviar à pasta fonte_de_dados."
    ),
    overwrite: bool = Query(
        True,
        description="Se True, substitui arquivos existentes com o mesmo nome. Se False, pula arquivos que já existam."
    )
) -> Dict[str, Any]:
    """
    Realiza o upload de um ou mais arquivos diretamente para a pasta **`fonte_de_dados/`**.

    ### Regras de Operação:
    - **Formatos permitidos**: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.log`
    - **Tamanho máximo**: 50 MB por arquivo
    - **Tolerância parcial**: Arquivos válidos são gravados na pasta, enquanto arquivos não suportados ou que excedam o limite são listados em `ignored_files`.
    - **Vetorização**: Este endpoint apenas persiste os arquivos no disco. Para indexá-los no ChromaDB, execute a rota `POST /api/v1/admin/sync-web?target=files`.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum arquivo foi enviado."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    saved_files: List[Dict[str, Any]] = []
    ignored_files: List[Dict[str, Any]] = []

    for file in files:
        raw_name = file.filename or ""
        # Sanitizar nome do arquivo para prevenir directory traversal
        filename = os.path.basename(raw_name).strip()

        if not filename:
            ignored_files.append({
                "filename": raw_name,
                "reason": "Nome de arquivo inválido ou vazio."
            })
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            ignored_files.append({
                "filename": filename,
                "reason": f"Formato '{ext}' não suportado. Permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            })
            continue

        destination_path = DATA_DIR / filename

        if destination_path.exists() and not overwrite:
            ignored_files.append({
                "filename": filename,
                "reason": "Arquivo já existe na pasta 'fonte_de_dados' e overwrite=False."
            })
            continue

        # Gravação em streaming com verificação do limite de 50MB
        total_bytes = 0
        size_exceeded = False

        try:
            with destination_path.open("wb") as buffer:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_FILE_SIZE_BYTES:
                        size_exceeded = True
                        break
                    buffer.write(chunk)

            if size_exceeded:
                # Remove arquivo parcial que estourou o limite
                if destination_path.exists():
                    destination_path.unlink()
                ignored_files.append({
                    "filename": filename,
                    "reason": f"Arquivo excede o limite máximo permitido de 50 MB ({total_bytes / (1024 * 1024):.2f} MB)."
                })
                continue

            saved_files.append({
                "filename": filename,
                "size_bytes": total_bytes,
                "size_human": f"{total_bytes / 1024:.1f} KB" if total_bytes < 1024 * 1024 else f"{total_bytes / (1024 * 1024):.2f} MB"
            })

        except Exception as exc:
            if destination_path.exists():
                try:
                    destination_path.unlink()
                except Exception:
                    pass
            ignored_files.append({
                "filename": filename,
                "reason": f"Erro interno ao gravar arquivo: {str(exc)}"
            })
        finally:
            await file.close()

    total_saved = len(saved_files)
    total_ignored = len(ignored_files)

    return {
        "status": "success" if total_saved > 0 else ("warning" if total_ignored > 0 else "empty"),
        "message": f"{total_saved} arquivo(s) salvo(s) com sucesso na pasta 'fonte_de_dados'." if total_saved > 0 else "Nenhum arquivo pôde ser salvo.",
        "total_uploaded": len(files),
        "total_saved": total_saved,
        "total_ignored": total_ignored,
        "saved_files": saved_files,
        "ignored_files": ignored_files,
        "next_step": "Para vetorizar os novos arquivos no ChromaDB, execute: POST /api/v1/admin/sync-web?target=files"
    }


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
    result = await asyncio.to_thread(run_sync, force=force, target=target.value)
    return {
        "target": target.value,
        "force": force,
        **result
    }


from backend.infrastructure.telemetry import telemetry_collector

@router.get("/dashboard-stats", tags=["Admin"])
async def get_dashboard_stats(
    mode: str = Query(
        "production",
        description="Modo dos dados: 'production' para dados 100% reais ou 'development' para baseline simulado"
    )
):
    """
    Retorna métricas em tempo real e KPIs para o Dashboard de Observabilidade do Getnet Multi-Agent.
    """
    return telemetry_collector.get_stats(mode=mode)



