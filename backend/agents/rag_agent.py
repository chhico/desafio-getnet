"""
agents/rag_agent.py
--------------------
Agente especialista em consultar documentos internos (RAG).

RAG = Retrieval Augmented Generation
O agente busca trechos relevantes dos documentos e usa como contexto
para gerar uma resposta precisa e fundamentada.
"""

from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.rag_tools import RAG_TOOLS


llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(RAG_TOOLS)

SYSTEM_PROMPT = """Você é um especialista em consultar a base de conhecimento interna da empresa.

Sua missão é fornecer respostas ÚNICAS, COESAS e DIRETAS.

Ferramentas disponíveis:
- buscar_documentos: busca trechos relevantes nos documentos internos
- listar_topicos_disponiveis: mostra quais assuntos estão documentados

Diretrizes Críticas:
1. SEMPRE use buscar_documentos antes de responder.
2. Seja CONCISO: Não repita trechos técnicos na sua resposta final. Use-os para fundamentar sua explicação e responda de forma natural.
3. FOCO: Responda estritamente o que foi perguntado. Se o usuário perguntou sobre "onboarding", ignore trechos de "preços" a menos que sejam vitais para o processo.
4. UNIFICAÇÃO: Gere uma única resposta final completa. Nunca envie mensagens picotadas ou vazias.
5. Se não encontrar nada, sugira o suporte humano.
"""


def rag_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do agente de RAG."""

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    updated_messages = [response]
    current_messages = messages + [response]

    while hasattr(response, "tool_calls") and response.tool_calls:
        tool_results = ToolNode(RAG_TOOLS).invoke({"messages": current_messages})
        tool_messages = tool_results["messages"]
        updated_messages.extend(tool_messages)
        current_messages.extend(tool_messages)
        response = llm_with_tools.invoke(current_messages)
        updated_messages.append(response)
        current_messages.append(response)

    response.name = "rag"
    response.additional_kwargs["agent_name"] = "rag"
    return {"messages": updated_messages}
