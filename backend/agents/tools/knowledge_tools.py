"""
tools/knowledge_tools.py
------------------------
Ferramentas unificadas do Agente 2 (Knowledge Agent):
1. consultar_base_local_getnet: RAG no ChromaDB (catálogo oficial Getnet, manuais e URLs sincronizadas)
2. consultar_base_web_getnet: Varredura web em tempo real nas páginas e subpáginas oficiais da Getnet (RAG_SYNC_URLS)
3. pesquisar_web: Busca na internet via DuckDuckGo para perguntas de uso geral (tempo, cotações, mercado)
"""

from langchain_core.tools import tool
from backend.agents.tools.rag_tools import _get_vectorstore

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


@tool
def consultar_base_local_getnet(query: str, num_resultados: int = 4) -> str:
    """
    Busca informações oficiais sobre produtos, serviços, maquininhas, taxas,
    antecipação de recebíveis, crediário, Pix e procedimentos da Getnet na base de conhecimento local (RAG).
    
    Args:
        query: Pergunta ou termos de busca sobre a Getnet
        num_resultados: Quantidade de trechos a recuperar (padrão: 4)
    """
    import os
    try:
        from backend.core.config import settings
        raw_async = getattr(settings, "RAG_ASYNC_URLS", "https://www.getnet.eu/pt/suporte, https://site.getnet.com.br/get-ajuda/")
        vs = _get_vectorstore()
        docs = vs.similarity_search(query, k=num_resultados)
        if not docs:
            return "Nenhuma informação oficial encontrada na base Getnet para esta consulta."

        trechos = []
        for i, doc in enumerate(docs, 1):
            raw_source = doc.metadata.get("source", "Base Oficial Getnet")
            if raw_source.startswith("http://") or raw_source.startswith("https://"):
                title = doc.metadata.get("title")
                title_suffix = f" ({title})" if title else ""
                source_label = f"🌐 URL da Base Indexada ({raw_async}): {raw_source}{title_suffix}"
            elif raw_source != "Base Oficial Getnet":
                filename = os.path.basename(raw_source)
                source_label = f"📄 Arquivo: {filename}"
            else:
                source_label = "📄 Arquivo: Base Oficial Getnet"

            trechos.append(f"Fonte [{source_label}] - Trecho {i}:\n{doc.page_content}")

        return "\n\n".join(trechos)
    except Exception as e:
        return f"Erro ao consultar base de conhecimento Getnet: {str(e)}"


@tool
def consultar_base_web_getnet(query: str, max_subpaginas: int = 3) -> str:
    """
    Pesquisa em tempo real diretamente nos portais e páginas oficiais da Getnet na web (e suas subpáginas navegáveis).
    Use EXCLUSIVAMENTE quando 'consultar_base_local_getnet' não encontrar informações suficientes na base interna,
    ou quando for necessária verificação direta no portal web oficial da Getnet.

    Args:
        query: Assunto ou dúvida específica a ser pesquisada nas páginas oficiais da Getnet.
        max_subpaginas: Quantidade máxima de subpáginas filhas a explorar em tempo real (padrão: 3).
    """
    import os
    import re
    import requests
    from urllib.parse import urljoin, urlparse
    from backend.core.config import settings
    from backend.infrastructure.rag.crawler import clean_html

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    raw_urls = getattr(settings, "RAG_SYNC_URLS", "https://site.getnet.com.br/blog/")
    base_urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
    if not base_urls:
        base_urls = ["https://site.getnet.com.br/blog/"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    STOPWORDS = {
        "como", "para", "qual", "quais", "onde", "quando", "quem", "porque", "por",
        "com", "sem", "uma", "uns", "umas", "mais", "menos", "muito", "pouco",
        "seu", "sua", "seus", "suas", "meu", "minha", "nosso", "nossa", "dele", "dela",
        "nas", "nos", "das", "dos", "pela", "pelo", "pelas", "pelos", "sobre", "entre",
        "está", "estao", "estão", "esta", "estas", "este", "estes", "esse", "esses",
        "essa", "essas", "isso", "aquilo", "aquele", "aquela", "aqui", "ali", "la", "lá",
        "funciona", "funcionar", "saber", "quero", "gostaria", "pode", "podem",
        "getnet"  # Termo genérico onipresente em todas as páginas do portal
    }

    all_words = re.findall(r"\w{3,}", query.lower())
    significant_words = set(w for w in all_words if w not in STOPWORDS)
    if not significant_words:
        significant_words = set(all_words)

    min_threshold = min(2, len(significant_words)) if significant_words else 1

    visited_urls = []
    matched_snippets = []

    for root_url in base_urls:
        parsed_root = urlparse(root_url)
        domain = parsed_root.netloc
        base_path = parsed_root.path.rstrip("/")

        urls_to_visit = [root_url]
        visited_in_domain = set()

        # 1. Varre a página principal
        try:
            resp = requests.get(root_url, headers=headers, timeout=8)
            if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                visited_in_domain.add(root_url)
                visited_urls.append(root_url)
                
                # Extrai links de subpáginas relevantes
                found_links = []
                if BeautifulSoup is not None:
                    try:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        found_links = [a["href"] for a in soup.find_all("a", href=True)]
                    except Exception:
                        pass
                if not found_links:
                    found_links = re.findall(r'href=[\'"]?([^\'" >]+)', resp.text)
                
                found_links = list(dict.fromkeys(link for link in found_links if link.startswith('https://site.getnet.com.br/')))

                candidate_sublinks = []
                for raw_link in found_links:
                    link = urljoin(root_url, raw_link).split("#")[0].rstrip("/")
                    parsed = urlparse(link)
                    if parsed.netloc == domain or not base_path:
                        if link not in visited_in_domain and not any(ext in link.lower() for ext in [".png", ".jpg", ".pdf", ".zip", ".css", ".js"]):
                            # Pontua relevância do link com base nos termos significativos
                            score = sum(1 for w in significant_words if w in link.lower())
                            candidate_sublinks.append((score, link))

                # Ordena os links mais promissores e seleciona até max_subpaginas
                candidate_sublinks.sort(key=lambda x: x[0], reverse=True)
                for _, s_link in candidate_sublinks[:max_subpaginas]:
                    if s_link not in urls_to_visit:
                        urls_to_visit.append(s_link)

                # Avalia texto da página raiz
                root_text = clean_html(resp.text)
                for paragraph in root_text.split("\n"):
                    p = paragraph.strip()
                    if len(p) >= 40:
                        matches = sum(1 for w in significant_words if w in p.lower())
                        if matches >= min_threshold:
                            matched_snippets.append({"score": matches, "url": root_url, "text": p[:300]})

        except Exception as e:
            continue

        # 2. Varre subpáginas filhas selecionadas
        for sub_url in urls_to_visit[1:]:
            if sub_url in visited_in_domain:
                continue
            visited_in_domain.add(sub_url)
            visited_urls.append(sub_url)
            try:
                sub_resp = requests.get(sub_url, headers=headers, timeout=8)
                if sub_resp.status_code == 200 and "text/html" in sub_resp.headers.get("Content-Type", ""):
                    sub_text = clean_html(sub_resp.text)
                    for paragraph in sub_text.split("\n"):
                        p = paragraph.strip()
                        if len(p) >= 40:
                            matches = sum(1 for w in significant_words if w in p.lower())
                            if matches >= min_threshold:
                                matched_snippets.append({"score": matches, "url": sub_url, "text": p[:300]})
            except Exception:
                continue

    if not matched_snippets:
        if visited_urls:
            return (
                f"Varredura em tempo real concluída nas páginas oficiais da Getnet ({raw_urls}) "
                f"({len(visited_urls)} URLs e subpáginas verificadas), mas nenhuma informação específica "
                f"para '{query}' foi localizada."
            )
        return f"Não foi possível conectar aos portais oficiais da Getnet ({raw_urls}) para consulta online no momento."

    # Ordena os trechos mais relevantes
    matched_snippets.sort(key=lambda x: x["score"], reverse=True)
    
    # Remove duplicidades de texto mantendo os top 4
    seen_texts = set()
    unique_snippets = []
    for snip in matched_snippets:
        if snip["text"] not in seen_texts:
            seen_texts.add(snip["text"])
            unique_snippets.append(snip)
        if len(unique_snippets) >= 4:
            break

    result_blocks = [f"Resultados da varredura online nos portais oficiais da Getnet ({raw_urls}) para '{query}':\n"]
    for i, snip in enumerate(unique_snippets, 1):
        result_blocks.append(f"Fonte [🌐 URL Online (Varredura em tempo real - {snip['url']}): {snip['url']}] - Trecho {i}:\n{snip['text']}")

    return "\n\n".join(result_blocks)


@tool
def pesquisar_web(query: str, max_resultados: int = 4) -> str:
    """
    Pesquisa informações atualizadas na internet sobre clima, cotações de moedas,
    notícias de mercado, tendências e dados de uso geral fora do catálogo Getnet.
    
    Args:
        query: Termo de pesquisa na internet (ex: 'previsão do tempo Porto Alegre amanhã', 'cotação do euro hoje')
        max_resultados: Quantidade máxima de resultados (padrão: 4)
    """
    if DDGS is None:
        return "Módulo de busca web (DuckDuckGo) não disponível no ambiente."

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_resultados):
                results.append(f"🌐 URL Web Externa: {r['href']}\n   Título: {r['title']}\n   Conteúdo: {r['body']}")
        
        if not results:
            return f"Nenhum resultado recente encontrado na web para '{query}'."
        
        return f"Resultados da pesquisa na web para '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Erro na pesquisa web: {str(e)}"


KNOWLEDGE_TOOLS = [consultar_base_local_getnet, consultar_base_web_getnet, pesquisar_web]
