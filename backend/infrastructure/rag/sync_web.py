"""
infrastructure/rag/sync_web.py
------------------------------
Script executável e agendador em background (cron) para sincronização da base web Getnet.
Uso manual via terminal:
  python -m backend.infrastructure.rag.sync_web
"""

import sys
import logging
from backend.agents.tools.rag_tools import _get_vectorstore
from backend.infrastructure.rag.crawler import sync_urls_to_vectorstore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_sync(force: bool = False):
    logger.info("=== Iniciando Sincronização Web Getnet ===")
    vs = _get_vectorstore()
    count = sync_urls_to_vectorstore(vs, force_refresh=force)
    logger.info(f"=== Sincronização finalizada. {count} página(s) processada(s) ===")


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    run_sync(force=force_flag)
