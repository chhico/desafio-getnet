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

from backend.infrastructure.rag.enrichment_service import run_enrichment


def run_sync(force: bool = False, target: str = "all") -> Dict[str, Any]:
    """
    Executa a sincronização e vetorização dos alvos selecionados delegando para o enrichment_service.
    """
    return run_enrichment(force=force, target=target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincronizador RAG Getnet (Arquivos locais e/ou URLs)")
    parser.add_argument("--force", action="store_true", help="Força a sobrescrita e re-vetorização dos itens existentes")
    parser.add_argument("--target", choices=["all", "files", "urls"], default="all", help="Alvo da sincronização (padrão: all)")
    args = parser.parse_args()

    run_sync(force=args.force, target=args.target)
