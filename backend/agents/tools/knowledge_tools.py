"""
tools/knowledge_tools.py
------------------------
Ferramentas unificadas do Agente 2 (Knowledge Agent):
1. consultar_base_getnet: RAG no ChromaDB (catálogo oficial Getnet, manuais e URLs)
2. pesquisar_web: Busca na internet via DuckDuckGo para perguntas de uso geral (tempo, cotações, mercado)
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
def consultar_base_getnet(query: str, num_resultados: int = 4) -> str:
    """
    Busca informações oficiais sobre produtos, serviços, maquininhas, taxas,
    antecipação de recebíveis, crediário, Pix e procedimentos da Getnet na base de conhecimento (RAG).
    
    Args:
        query: Pergunta ou termos de busca sobre a Getnet
        num_resultados: Quantidade de trechos a recuperar (padrão: 4)
    """
    import os
    try:
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
                source_label = f"🌐 URL: {raw_source}{title_suffix}"
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
                results.append(f"🌐 URL: {r['href']}\n   Título: {r['title']}\n   Conteúdo: {r['body']}")
        
        if not results:
            return f"Nenhum resultado recente encontrado na web para '{query}'."
        
        return f"Resultados da pesquisa na web para '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Erro na pesquisa web: {str(e)}"


KNOWLEDGE_TOOLS = [consultar_base_getnet, pesquisar_web]
