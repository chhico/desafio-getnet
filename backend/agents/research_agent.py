"""
agents/research_agent.py
-------------------------
Agente especialista em pesquisa na internet.

Capaz de buscar informações atualizadas via DuckDuckGo,
algo que o LLM por si só não consegue após seu corte de treinamento.
"""

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.research_tools import RESEARCH_TOOLS


llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)

SYSTEM_PROMPT = """Você é um pesquisador especialista em encontrar informações na internet.

Ferramentas disponíveis:
- pesquisar_web: busca geral na internet
- pesquisar_noticias: busca notícias recentes sobre um tópico

Diretrizes:
1. SEMPRE pesquise antes de responder — não use apenas seu conhecimento interno
2. Para notícias e eventos recentes, prefira pesquisar_noticias
3. Sintetize os resultados de forma clara, não apenas liste links
4. Indique a fonte das informações
5. Se os resultados forem insuficientes, faça uma segunda busca com termos diferentes
6. Responda em português brasileiro
"""


def research_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do agente de pesquisa web."""

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    updated_messages = [response]
    current_messages = messages + [response]

    while hasattr(response, "tool_calls") and response.tool_calls:
        tool_results = ToolNode(RESEARCH_TOOLS).invoke({"messages": current_messages})
        tool_messages = tool_results["messages"]
        updated_messages.extend(tool_messages)
        current_messages.extend(tool_messages)
        response = llm_with_tools.invoke(current_messages)
        updated_messages.append(response)
        current_messages.append(response)

    response.name = "research"
    response.additional_kwargs["agent_name"] = "research"
    return {"messages": updated_messages}
