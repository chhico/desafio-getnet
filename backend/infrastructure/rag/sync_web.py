"""
infrastructure/rag/sync_web.py
------------------------------
Script executável e rotina de sincronização de base RAG (Arquivos locais e/ou URLs Web).
Uso manual via terminal:
  python -m backend.infrastructure.rag.sync_web [--force] [--target files|urls|all]
"""

import sys
import logging
import argparse
from typing import Dict, Any

from backend.agents.tools.rag_tools import _get_vectorstore, sync_local_files_to_vectorstore
from backend.infrastructure.rag.crawler import sync_urls_to_vectorstore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_sync(force: bool = False, target: str = "all") -> Dict[str, Any]:
    """
    Executa a sincronização e vetorização dos alvos selecionados:
    - target="files": Apenas arquivos da pasta fonte_de_dados
    - target="urls": Apenas páginas web (crawler)
    - target="all": Ambos (arquivos locais e URLs web)

    Se force=True: Sobrescreve no ChromaDB os dados existentes.
    Se force=False: Apenas vetoriza os que ainda não existirem (ou alterados via hash MD5).
    """
    logger.info(f"=== Iniciando Sincronização (target={target}, force={force}) ===")
    vs = _get_vectorstore()

    files_count = 0
    urls_count = 0
    target_lower = target.lower().strip()

    # 1. Processa Arquivos Locais da pasta fonte_de_dados
    if target_lower in ["files", "arquivos", "local", "all", "ambos", "both"]:
        logger.info(f"[Sync] Processando arquivos locais de fonte_de_dados (force={force})...")
        files_count = sync_local_files_to_vectorstore(vs, force=force)
        logger.info(f"[Sync] Arquivos processados/atualizados: {files_count}")

    # 2. Processa URLs Web configuradas
    if target_lower in ["urls", "web", "all", "ambos", "both"]:
        logger.info(f"[Sync] Processando URLs web via crawler (force={force})...")
        urls_count = sync_urls_to_vectorstore(vs, force_refresh=force)
        logger.info(f"[Sync] URLs processadas/atualizadas: {urls_count}")

    logger.info(f"=== Sincronização finalizada. {files_count} arquivo(s), {urls_count} URL(s) processada(s) ===")

    return {
        "files_processed": files_count,
        "urls_processed": urls_count,
        "details": f"{files_count} arquivo(s) e {urls_count} URL(s) processados/sincronizados no ChromaDB."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincronizador RAG Getnet (Arquivos locais e/ou URLs)")
    parser.add_argument("--force", action="store_true", help="Força a sobrescrita e re-vetorização dos itens existentes")
    parser.add_argument("--target", choices=["all", "files", "urls"], default="all", help="Alvo da sincronização (padrão: all)")
    args = parser.parse_args()

    run_sync(force=args.force, target=args.target)
