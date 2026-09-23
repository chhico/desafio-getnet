"""
infrastructure/rag/enrichment_service.py
-----------------------------------------
Serviço centralizado de enriquecimento e sincronização da base vetorial (ChromaDB).
Orquestra:
1. Verificação e criação das tabelas 'simple_sync_hashes' e 'url_sync_hashes'.
2. Processamento e deleção automática de arquivos da pasta 'fonte_de_dados'.
3. Verificação item a item das URLs de 'RAG_ASYNC_URLS' em 'url_sync_hashes'.
4. Execução condicional do crawler (se faltar registro para qualquer URL ou se force=True).
5. Controle de concorrência com Lock para evitar conflitos com /sync-web.
"""

import os
import asyncio
import logging
import threading
from typing import Dict, Any, List

from backend.core.config import settings
from backend.agents.tools.rag_tools import _get_vectorstore, sync_local_files_to_vectorstore
from backend.infrastructure.rag.crawler import (
    init_rag_db,
    check_all_urls_have_records,
    sync_urls_to_vectorstore
)

logger = logging.getLogger(__name__)

_sync_lock = threading.Lock()
_is_syncing: bool = False


def is_sync_in_progress() -> bool:
    """Informa se há uma sincronização em andamento."""
    return _is_syncing


def init_and_check_rag_tables():
    """Garante que as tabelas necessárias existam no SQLite."""
    db_path = getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")
    logger.info(f"[Enrichment Service] Verificando tabelas SQLite em: {db_path}")
    init_rag_db(db_path)
    logger.info("[Enrichment Service] Tabelas 'simple_sync_hashes' e 'url_sync_hashes' verificadas com sucesso.")


def run_enrichment(force: bool = False, target: str = "all") -> Dict[str, Any]:
    """
    Executa o enriquecimento da base vetorial conforme regras de negócio.
    Usa lock para garantir que apenas uma sincronização execute por vez.
    """
    global _is_syncing

    acquired = _sync_lock.acquire(blocking=False)
    if not acquired:
        logger.warning("[Enrichment Service] Sincronização já em andamento. Chamada rejeitada.")
        return {
            "status": "already_running",
            "message": "Uma sincronização da base de conhecimento já está em andamento.",
            "files_processed": 0,
            "urls_processed": 0
        }

    _is_syncing = True
    try:
        logger.info(f"=== [Enrichment Service] Iniciando sincronização (target={target}, force={force}) ===")
        init_and_check_rag_tables()

        vs = _get_vectorstore()
        target_lower = target.lower().strip()
        files_count = 0
        urls_count = 0

        # 1. Processa Arquivos Locais (fonte_de_dados/)
        if target_lower in ["files", "arquivos", "local", "all", "ambos", "both"]:
            logger.info("[Enrichment Service] Verificando arquivos na pasta 'fonte_de_dados'...")
            files_count = sync_local_files_to_vectorstore(vs, force=force, data_dir="fonte_de_dados")
            logger.info(f"[Enrichment Service] Arquivos processados/importados: {files_count}")

        # 2. Processa URLs Web (RAG_ASYNC_URLS)
        if target_lower in ["urls", "web", "all", "ambos", "both"]:
            raw_urls = settings.RAG_ASYNC_URLS
            if isinstance(raw_urls, str):
                urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
            else:
                urls = list(raw_urls)

            all_present, missing = check_all_urls_have_records(urls)

            # Se for chamada explícita de URLs ou se force=True ou se faltar registro para algum item:
            should_crawl = force or (not all_present) or (target_lower in ["urls", "web"])

            if should_crawl:
                if not all_present:
                    logger.info(
                        f"[Enrichment Service] URLs de RAG_ASYNC_URLS sem registro: {missing}. "
                        f"Disparando reprocessamento completo do crawler..."
                    )
                elif force:
                    logger.info("[Enrichment Service] Flag force=True detectada. Forçando crawler para todas as URLs.")
                else:
                    logger.info("[Enrichment Service] Executando crawler para as URLs configuradas...")

                urls_count = sync_urls_to_vectorstore(vs, force_refresh=(force or not all_present))
                logger.info(f"[Enrichment Service] URLs processadas/atualizadas: {urls_count}")
            else:
                logger.info(
                    "[Enrichment Service] Todas as URLs de RAG_ASYNC_URLS já possuem registros na tabela "
                    "'url_sync_hashes' e force=False. Crawler ignorado para otimização de startup."
                )

        logger.info(
            f"=== [Enrichment Service] Sincronização finalizada com sucesso! "
            f"({files_count} arquivo(s), {urls_count} URL(s)) ==="
        )

        return {
            "status": "success",
            "message": "Sincronização concluída com sucesso.",
            "target": target,
            "force": force,
            "files_processed": files_count,
            "urls_processed": urls_count,
            "details": f"{files_count} arquivo(s) e {urls_count} URL(s) processados/sincronizados."
        }

    except Exception as e:
        logger.error(f"[Enrichment Service] Erro inesperado durante sincronização: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Erro durante sincronização: {str(e)}",
            "files_processed": 0,
            "urls_processed": 0
        }
    finally:
        _is_syncing = False
        _sync_lock.release()


async def run_startup_enrichment():
    """
    Rotina assíncrona executada em background na subida da aplicação (lifespan).
    Não bloqueia o boot da API.
    """
    logger.info("[Startup] Tarefa em background de enriquecimento vetorial disparada.")
    try:
        # Executa em thread separada para não bloquear o loop assíncrono do FastAPI
        result = await asyncio.to_thread(run_enrichment, force=False, target="all")
        logger.info(f"[Startup] Resultado do enriquecimento inicial: {result.get('details', result)}")
    except Exception as e:
        logger.error(f"[Startup] Falha na rotina de enriquecimento inicial: {e}")
