"""
agents/tasks_agent.py
----------------------
Agente especialista em gerenciamento de tarefas.

Cria, lista, atualiza tarefas e gera relatórios de produtividade.
"""

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.task_tools import TASK_TOOLS


llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(TASK_TOOLS)

SYSTEM_PROMPT = """Você é um assistente especialista em produtividade e gerenciamento de tarefas.

Ferramentas disponíveis:
- criar_tarefa: registra uma nova tarefa
- listar_tarefas: mostra tarefas com filtro por status
- atualizar_status_tarefa: muda status de uma tarefa
- gerar_relatorio_tarefas: gera resumo de todas as tarefas

Diretrizes:
1. Ao criar tarefas, extraia título claro e defina prioridade com base no contexto
2. Confirme sempre antes de marcar tarefas como concluídas
3. Ofereça relatórios quando o usuário quiser ver o progresso geral
4. Seja proativo: se o usuário mencionar algo a fazer, sugira criar uma tarefa
5. Responda em português brasileiro
"""


def tasks_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do agente de backend (geração de reports/tasks pesadas)."""

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    updated_messages = [response]
    current_messages = messages + [response]

    while hasattr(response, "tool_calls") and response.tool_calls:
        tool_results = ToolNode(TASK_TOOLS).invoke({"messages": current_messages})
        tool_messages = tool_results["messages"]
        updated_messages.extend(tool_messages)
        current_messages.extend(tool_messages)
        response = llm_with_tools.invoke(current_messages)
        updated_messages.append(response)
        current_messages.append(response)

    response.name = "tasks"
    response.additional_kwargs["agent_name"] = "tasks"
    return {"messages": updated_messages}
