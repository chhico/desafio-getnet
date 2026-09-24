"""
agents/agent_utils.py
---------------------
Utilitários compartilhados para execução do ciclo de agentes e ferramentas (ReAct loop).
Evita duplicação de lógica de invocação de ToolNode e chamada sucessiva ao LLM.
"""

from typing import List, Optional
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import ToolNode


def run_agent_with_tools(
    llm_with_tools,
    tools: list,
    messages: list,
    agent_name: Optional[str] = None,
    max_iterations: int = 5,
) -> List[BaseMessage]:
    """
    Executa o ciclo de raciocínio e execução de ferramentas (ReAct loop) para um agente.

    Args:
        llm_with_tools: Instância do LLM vinculada às ferramentas (bind_tools).
        tools: Lista de ferramentas disponíveis para o ToolNode.
        messages: Mensagens de entrada para o LLM (incluindo SystemMessage).
        agent_name: Nome opcional do agente para assinar a mensagem final (ex: 'knowledge', 'support').
        max_iterations: Limite máximo de chamadas a ferramentas para evitar loops infinitos.

    Returns:
        Lista com as novas mensagens geradas no turno (AIMessages e ToolMessages).
    """
    tool_node = ToolNode(tools)
    current_messages = list(messages)

    response = llm_with_tools.invoke(current_messages)
    updated_messages = [response]
    current_messages.append(response)

    iterations = 0
    while hasattr(response, "tool_calls") and response.tool_calls and iterations < max_iterations:
        iterations += 1
        tool_results = tool_node.invoke({"messages": current_messages})
        tool_messages = tool_results["messages"]
        updated_messages.extend(tool_messages)
        current_messages.extend(tool_messages)

        response = llm_with_tools.invoke(current_messages)
        updated_messages.append(response)
        current_messages.append(response)

    if agent_name:
        response.name = agent_name

    return updated_messages
