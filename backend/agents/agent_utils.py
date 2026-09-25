"""
agents/agent_utils.py
---------------------
Utilitários compartilhados para execução do ciclo de agentes e ferramentas (ReAct loop).
Evita duplicação de lógica de invocação de ToolNode e chamada sucessiva ao LLM.
"""

from typing import List, Optional
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.prebuilt import ToolNode


def sanitize_messages_for_llm(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Higieniza a lista de mensagens para garantir conformidade estrita com a API do OpenAI:
    1. Garante que qualquer AIMessage com tool_calls seja imediatamente seguida por ToolMessages
       correspondentes a CADA tool_call_id.
    2. Se houver tool_calls órfãos (sem ToolMessage de retorno), remove os tool_calls não respondidos
       para não quebrar a chamada à API (erro 400).
    3. Garante que AIMessages sem tool_calls e com conteúdo vazio tenham texto válido.
    4. Remove ToolMessages soltas que não correspondam a nenhum tool_call_id do AIMessage anterior.
    """
    if not messages:
        return []

    sanitized: List[BaseMessage] = []
    i = 0
    n = len(messages)

    while i < n:
        msg = messages[i]

        has_tool_calls = hasattr(msg, "tool_calls") and bool(msg.tool_calls)

        if has_tool_calls:
            expected_ids = set()
            for tc in msg.tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id:
                    expected_ids.add(tc_id)

            tool_msgs = []
            j = i + 1
            while j < n:
                next_msg = messages[j]
                is_tool = (
                    isinstance(next_msg, ToolMessage)
                    or getattr(next_msg, "type", "") == "tool"
                    or hasattr(next_msg, "tool_call_id")
                )
                if is_tool:
                    t_id = getattr(next_msg, "tool_call_id", None)
                    if t_id in expected_ids:
                        tool_msgs.append(next_msg)
                    j += 1
                else:
                    break

            answered_ids = {getattr(tm, "tool_call_id", None) for tm in tool_msgs}

            if expected_ids and expected_ids == answered_ids:
                sanitized.append(msg)
                sanitized.extend(tool_msgs)
            elif answered_ids:
                new_tool_calls = [
                    tc for tc in msg.tool_calls
                    if (tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)) in answered_ids
                ]
                msg_copy = msg.model_copy(update={"tool_calls": new_tool_calls}) if hasattr(msg, "model_copy") else msg
                sanitized.append(msg_copy)
                sanitized.extend(tool_msgs)
            else:
                content = msg.content if (msg.content and str(msg.content).strip()) else "Processando informações da consulta..."
                if hasattr(msg, "model_copy"):
                    msg_copy = msg.model_copy(update={"tool_calls": [], "content": content})
                else:
                    msg_copy = AIMessage(content=content)
                sanitized.append(msg_copy)

            i = j
        else:
            is_orphan_tool = (
                isinstance(msg, ToolMessage)
                or getattr(msg, "type", "") == "tool"
                or hasattr(msg, "tool_call_id")
            )
            if is_orphan_tool:
                i += 1
                continue

            if (isinstance(msg, AIMessage) or getattr(msg, "type", "") == "ai") and (not msg.content or not str(msg.content).strip()):
                if hasattr(msg, "model_copy"):
                    sanitized.append(msg.model_copy(update={"content": "Atendimento processado."}))
                else:
                    sanitized.append(AIMessage(content="Atendimento processado."))
                i += 1
                continue

            sanitized.append(msg)
            i += 1

    return sanitized


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
    current_messages = sanitize_messages_for_llm(list(messages))

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

    # Se saiu do loop com tool_calls ainda pendentes (atingiu max_iterations):
    if hasattr(response, "tool_calls") and response.tool_calls:
        try:
            tool_results = tool_node.invoke({"messages": current_messages})
            tool_messages = tool_results["messages"]
            updated_messages.extend(tool_messages)
            current_messages.extend(tool_messages)
        except Exception:
            pass

        try:
            base_llm = getattr(llm_with_tools, "bound", llm_with_tools)
            final_prompt = current_messages + [
                SystemMessage(
                    content=(
                        "Forneça a resposta final e completa ao usuário com base nas informações "
                        "e ferramentas consultadas até o momento. Não faça novas chamadas a ferramentas."
                    )
                )
            ]
            final_response = base_llm.invoke(final_prompt)
            updated_messages.append(final_response)
            response = final_response
        except Exception:
            if hasattr(response, "model_copy"):
                response = response.model_copy(update={"tool_calls": []})
            else:
                response.tool_calls = []
            if not response.content or not str(response.content).strip():
                response.content = "Consultei os registros oficiais da Getnet para sua dúvida. Caso precise de mais detalhes, estou à disposição."

    if agent_name:
        response.name = agent_name

    return sanitize_messages_for_llm(updated_messages)
