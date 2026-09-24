"""
infrastructure/rag/crawler.py
-----------------------------
Mecanismo de Web Scraping e Crawler Recursivo para o RAG da Getnet.
Varre as URLs parametrizadas e todas as suas subpáginas respeitando profundidade,
extrai o texto limpo, calcula hash MD5 e atualiza o ChromaDB incrementalmente.
"""

import os
import re
import base64
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

DB_PATH = getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")


def init_rag_db(db_path: Optional[str] = None):
    """Garante a existência das tabelas url_sync_hashes e simple_sync_hashes no SQLite."""
    target_path = db_path or getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")
    folder = os.path.dirname(target_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(target_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS url_sync_hashes (
            url TEXT PRIMARY KEY,
            content_hash TEXT,
            last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simple_sync_hashes (
            filename TEXT PRIMARY KEY,
            hash TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _init_sqlite_db():
    init_rag_db()


def check_all_urls_have_records(urls: Optional[List[str]] = None, db_path: Optional[str] = None) -> tuple[bool, list[str]]:
    """
    Verifica se cada uma das URLs raiz configuradas possui pelo menos um registro em url_sync_hashes.
    Retorna uma tupla (all_present, missing_urls).
    """
    target_path = db_path or getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")
    init_rag_db(target_path)

    if urls is None:
        raw_urls = settings.RAG_ASYNC_URLS
        if isinstance(raw_urls, str):
            urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
        else:
            urls = list(raw_urls)

    conn = sqlite3.connect(target_path)
    cursor = conn.cursor()
    missing_urls = []

    for root_url in urls:
        norm = root_url.strip().rstrip("/")
        # Checa se a URL exata ou alguma subpágina (por barra ou hífen) foi indexada
        cursor.execute(
            "SELECT 1 FROM url_sync_hashes WHERE url = ? OR url = ? OR url LIKE ? OR url LIKE ? LIMIT 1",
            (norm, norm + "/", norm + "/%", norm + "-%")
        )
        if cursor.fetchone() is None:
            missing_urls.append(root_url)

    conn.close()
    return (len(missing_urls) == 0, missing_urls)


def clean_html(html_content: str) -> str:
    """Extrai texto legível de HTML, eliminando scripts, estilos e tags."""
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


IGNORED_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".css", ".js", ".json", ".xml",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3"
)


def extract_links_from_html(html_content: str, base_path: str = "") -> Set[str]:
    """
    Extrai links de:
    1. Tags <a> estáticas tradicionais (SSR / HTML clássico).
    2. Scripts dinâmicos com Data URI em Base64 (usados em portais como o Getnet /get-ajuda).
    3. Scripts inline contendo URLs ou definições de rotas em JSON.
    """
    found_links: Set[str] = set()

    # 1. Tags <a> tradicionais (HTML estático)
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    found_links.add(href)
        except Exception:
            pass

    if not found_links:
        for m in re.findall(r'href=[\'"]?([^\'" >]+)', html_content):
            if not m.startswith(("javascript:", "mailto:", "tel:", "#")):
                found_links.add(m)

    # 2. Scripts com Data URI em Base64 (ex: data:text/javascript;base64,...)
    b64_scripts = re.findall(
        r'src=["\']data:(?:text|application)/(?:javascript|x-javascript);base64,([^"\']+)["\']',
        html_content,
        re.IGNORECASE
    )
    for b64 in b64_scripts:
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
            # Extrai URLs de propriedades comuns (ex: link: "...", btnLink: "...", href: "...")
            for link in re.findall(r'(?:link|btnLink|href|url)\s*:\s*["\']([^"\']+)["\']', decoded):
                if link and not link.startswith(("javascript:", "mailto:", "tel:", "#")):
                    found_links.add(link)

            # Extrai caminhos que correspondam ao base_path (ou padrão /get-ajuda)
            clean_bp = base_path.strip("/") if base_path else "get-ajuda"
            for p in re.findall(rf'["\'](/(?:{re.escape(clean_bp)}[^\s"\'#]*))["\']', decoded):
                found_links.add(p)
        except Exception:
            pass

    # 3. Scripts inline normais (<script>...</script>)
    inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_content, flags=re.DOTALL | re.IGNORECASE)
    for script_body in inline_scripts:
        if "link" in script_body or (base_path and base_path in script_body):
            for link in re.findall(r'(?:link|btnLink|href|url)\s*:\s*["\']([^"\']+)["\']', script_body):
                if link and not link.startswith(("javascript:", "mailto:", "tel:", "#")):
                    found_links.add(link)
            clean_bp = base_path.strip("/") if base_path else "get-ajuda"
            for p in re.findall(rf'["\'](/(?:{re.escape(clean_bp)}[^\s"\'#]*))["\']', script_body):
                found_links.add(p)

    return found_links


def is_url_in_scope(target_url: str, root_domain: str, base_path: str) -> bool:
    """
    Verifica se a URL pertence ao mesmo domínio e está dentro do escopo da URL raiz.
    Aceita:
    - Mesma rota exata (ex: /get-ajuda)
    - Subpastas convencionais (ex: /pt/suporte/faq)
    - Rotas hifenizadas no padrão Getnet (ex: /get-ajuda-receba-ja/artigo)
    """
    parsed = urlparse(target_url)
    if parsed.netloc != root_domain:
        return False

    if not base_path:
        return True

    clean_path = parsed.path.rstrip("/")
    clean_base = base_path.rstrip("/")

    # 1. Correspondência exata
    if clean_path == clean_base:
        return True
    # 2. Subpasta hierárquica (ex: base=/pt/suporte -> /pt/suporte/artigo)
    if clean_path.startswith(clean_base + "/"):
        return True
    # 3. Prefixo hifenizado (ex: base=/get-ajuda -> /get-ajuda-receba-ja)
    if clean_path.startswith(clean_base + "-"):
        return True

    return False


def crawl_recursive(
    base_urls: List[str], 
    max_depth: int = 2, 
    max_pages_per_domain: Optional[int] = None
) -> List[Document]:
    """
    Rastreia recursivamente as URLs base e suas subpáginas filhas.
    Suporta tanto hierarquia de diretórios clássica quanto rotas dinâmicas/hifenizadas.
    """
    if max_pages_per_domain is None:
        max_pages_per_domain = getattr(settings, "RAG_CRAWLER_MAX_PAGES", 50)

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

        logger.info(
            f"[Crawler] Iniciando varredura a partir de: {root_url} "
            f"(Profundidade max: {max_depth}, Limite de páginas: {max_pages_per_domain})"
        )

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
                    found_links = extract_links_from_html(resp.text, base_path=base_path)

                    for raw_link in found_links:
                        link = urljoin(current_url, raw_link).split("#")[0].rstrip("/")
                        if not link or link in visited:
                            continue

                        parsed_link = urlparse(link)
                        
                        # Garante que pertence ao mesmo domínio e escopo (subpasta ou prefixo com hífen)
                        if is_url_in_scope(link, domain, base_path):
                            if not any(parsed_link.path.lower().endswith(ext) for ext in IGNORED_EXTENSIONS):
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
    max_pages = getattr(settings, "RAG_CRAWLER_MAX_PAGES", 50)

    all_present, missing_urls = check_all_urls_have_records(urls)
    effective_force = force_refresh
    if not all_present:
        logger.info(
            f"[Crawler Sync] URLs sem registro detectadas em RAG_ASYNC_URLS: {missing_urls}. "
            f"Reprocessando todas as URLs e subpáginas..."
        )
        effective_force = True
    elif force_refresh:
        logger.info("[Crawler Sync] Sincronização forçada (force=True). Reprocessando todas as URLs e subpáginas...")

    logger.info(f"[Crawler Sync] Rastreando {len(urls)} URLs configuradas (max_depth={max_depth}, max_pages={max_pages})...")
    docs = crawl_recursive(urls, max_depth=max_depth, max_pages_per_domain=max_pages)

    if not docs:
        logger.info("[Crawler Sync] Nenhuma página encontrada ou rede inacessível.")
        return 0

    target_path = getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")
    conn = sqlite3.connect(target_path)
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

        if effective_force or row is None or row[0] != content_hash:
            logger.info(f"[Crawler Sync] URL para indexação (force={effective_force}): {url}")
            
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
