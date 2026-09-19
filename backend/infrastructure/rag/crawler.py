"""
infrastructure/rag/crawler.py
-----------------------------
Mecanismo de Web Scraping e Crawler Recursivo para o RAG da Getnet.
Varre as URLs parametrizadas e todas as suas subpáginas respeitando profundidade,
extrai o texto limpo, calcula hash MD5 e atualiza o ChromaDB incrementalmente.
"""

import os
import hashlib
import logging
import sqlite3
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.core.config import settings

logger = logging.getLogger(__name__)

DB_PATH = "bds/rag_sync.sqlite"


def _init_sqlite_db():
    os.makedirs("bds", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS url_sync_hashes (
            url TEXT PRIMARY KEY,
            content_hash TEXT,
            last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def clean_html(html_content: str) -> str:
    """Extrai texto legível de HTML, eliminando scripts, estilos e tags."""
    import re
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            lines = (line.strip() for line in soup.get_text().splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return "\n".join(chunk for chunk in chunks if chunk)
        except Exception:
            pass

    # Fallback puro Python via Regex (caso bs4 falhe ou não esteja disponível)
    clean_text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text


def crawl_recursive(
    base_urls: List[str], 
    max_depth: int = 2, 
    max_pages_per_domain: int = 20
) -> List[Document]:
    """
    Rastreia recursivamente as URLs base e suas subpáginas filhas.
    """
    documents: List[Document] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for root_url in base_urls:
        root_url = root_url.strip()
        if not root_url:
            continue

        parsed_root = urlparse(root_url)
        domain = parsed_root.netloc
        base_path = parsed_root.path.rstrip("/")

        visited: Set[str] = set()
        queue: List[tuple[str, int]] = [(root_url, 0)]

        logger.info(f"[Crawler] Iniciando varredura a partir de: {root_url} (Profundidade max: {max_depth})")

        while queue and len(visited) < max_pages_per_domain:
            current_url, depth = queue.pop(0)
            
            # Normalizar URL (sem hash de fragmento)
            current_url = current_url.split("#")[0].rstrip("/")
            if current_url in visited:
                continue

            visited.add(current_url)

            try:
                resp = requests.get(current_url, headers=headers, timeout=10)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                    continue

                text = clean_html(resp.text)
                if len(text) > 100:  # Ignora páginas sem conteúdo relevante
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": current_url,
                                "domain": domain,
                                "type": "web_page"
                            }
                        )
                    )

                # Se não atingiu profundidade máxima, descobre links filhos do mesmo domínio e subcaminho
                if depth < max_depth:
                    found_links = []
                    if BeautifulSoup is not None:
                        try:
                            soup = BeautifulSoup(resp.text, "html.parser")
                            found_links = [a["href"] for a in soup.find_all("a", href=True)]
                        except Exception:
                            pass
                    
                    if not found_links:
                        import re
                        found_links = re.findall(r'href=[\'"]?([^\'" >]+)', resp.text)

                    for raw_link in found_links:
                        link = urljoin(current_url, raw_link).split("#")[0].rstrip("/")
                        parsed_link = urlparse(link)
                        
                        # Garante que pertence ao mesmo domínio e começa no mesmo caminho
                        if parsed_link.netloc == domain and (parsed_link.path.startswith(base_path) or not base_path):
                            if link not in visited and not any(ext in link.lower() for ext in [".png", ".jpg", ".pdf", ".zip", ".css", ".js"]):
                                queue.append((link, depth + 1))

            except Exception as e:
                logger.warning(f"[Crawler] Erro ao acessar {current_url}: {e}")

    return documents


def sync_urls_to_vectorstore(vectorstore, force_refresh: bool = False) -> int:
    """
    Varre as URLs configuradas em RAG_ASYNC_URLS, detecta mudanças por Hash MD5,
    invalida vetores antigos no ChromaDB e indexa o conteúdo novo.
    """
    _init_sqlite_db()

    raw_urls = settings.RAG_ASYNC_URLS
    if isinstance(raw_urls, str):
        urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
    else:
        urls = list(raw_urls)

    max_depth = getattr(settings, "RAG_CRAWLER_MAX_DEPTH", 2)

    logger.info(f"[Crawler Sync] Rastreando {len(urls)} URLs configuradas...")
    docs = crawl_recursive(urls, max_depth=max_depth)

    if not docs:
        logger.info("[Crawler Sync] Nenhuma página encontrada ou rede inacessível.")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated_docs = []
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)

    for doc in docs:
        url = doc.metadata.get("source", "")
        hasher = hashlib.md5()
        hasher.update(doc.page_content.encode("utf-8"))
        content_hash = hasher.hexdigest()

        cursor.execute("SELECT content_hash FROM url_sync_hashes WHERE url = ?", (url,))
        row = cursor.fetchone()

        if force_refresh or row is None or row[0] != content_hash:
            logger.info(f"[Crawler Sync] URL nova ou modificada: {url}")
            
            # 1. Se já existia no banco vetorial, remove chunks antigos dessa URL específica
            try:
                vectorstore.delete(where={"source": url})
            except Exception:
                pass  # Coleção pode não suportar delete condicional ou estar vazia

            # 2. Adiciona para indexação
            updated_docs.append(doc)

            # 3. Atualiza SQLite
            cursor.execute(
                "INSERT OR REPLACE INTO url_sync_hashes (url, content_hash) VALUES (?, ?)", 
                (url, content_hash)
            )

    conn.commit()
    conn.close()

    if updated_docs:
        chunks = splitter.split_documents(updated_docs)
        if chunks:
            vectorstore.add_documents(chunks)
            logger.info(f"[Crawler Sync] {len(chunks)} novos chunks vetorizados com sucesso!")
        return len(updated_docs)

    logger.info("[Crawler Sync] Todas as páginas web já estavam atualizadas no ChromaDB.")
    return 0
