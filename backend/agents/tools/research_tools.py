"""
tools/research_tools.py
-----------------------
Ferramentas do Research Agent.

Permite ao agente buscar informações atualizadas na internet,
algo que o LLM por si só não consegue (dados após o treinamento).

Usa DuckDuckGo como motor de busca (gratuito, sem API key).
Em produção, considere: Tavily, Serper, Bing Search API.
"""

from langchain_core.tools import tool

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


@tool
def pesquisar_web(query: str, max_resultados: int = 5) -> str:
    """
    Pesquisa informações atualizadas na internet via DuckDuckGo.
    Use para buscar notícias, dados recentes, fatos verificáveis,
    informações sobre empresas, tecnologias ou qualquer assunto externo.

    Args:
        query: Termos de busca (em português ou inglês)
        max_resultados: Número máximo de resultados (padrão: 5)
    """
    if DDGS is None:
        return "Erro: Módulo de pesquisa na web (ddgs / duckduckgo-search) não instalado."

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_resultados):
                results.append(
                    f"🔗 {r['title']}\n   {r['href']}\n   {r['body']}"
                )
        if not results:
            return "Nenhum resultado encontrado para esta pesquisa."
        return f"Resultados para '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Erro na pesquisa: {str(e)}"


@tool
def pesquisar_noticias(topico: str, max_resultados: int = 5) -> str:
    """
    Busca notícias recentes sobre um tópico específico.
    Use quando o usuário quiser saber novidades, tendências ou eventos recentes.

    Args:
        topico: Assunto das notícias
        max_resultados: Número máximo de notícias (padrão: 5)
    """
    if DDGS is None:
        return "Erro: Módulo de pesquisa na web (ddgs / duckduckgo-search) não instalado."

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(topico, max_results=max_resultados):
                results.append(
                    f"📰 {r['title']}\n   Fonte: {r.get('source', 'N/A')} | {r.get('date', '')}\n   {r['url']}"
                )
        if not results:
            return f"Nenhuma notícia encontrada sobre '{topico}'."
        return f"Notícias sobre '{topico}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Erro ao buscar notícias: {str(e)}"


RESEARCH_TOOLS = [pesquisar_web, pesquisar_noticias]
