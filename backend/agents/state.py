"""
agent/state.py
--------------
Estado compartilhado (SupportState) utilizado pelo grafo LangGraph.
"""

from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

# Tipos de agentes especialistas suportados (4 Agentes + Guardrail)
AgentType = Literal["knowledge", "support", "guardrail_block", "escalation"]


def get_last_human_message(messages: list) -> str:
    """
    Recupera o conteúdo textual da última mensagem enviada pelo usuário no histórico.
    """
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
            return (m.content or "").strip()
    return ""


class SupportState(TypedDict):
    """
    Estado compartilhado por todos os agentes da plataforma.
    """
    # Identificador do cliente (atende aos requisitos de autenticação e contexto do desafio)
    user_id: str

    # Histórico acumulado da conversa
    messages: Annotated[list, add_messages]
    
    # Contador utilitário de turnos
    turn_count: int

    # Controle de Roteamento (definido pelo Orchestrator)
    next_agent: AgentType | None
    routing_reason: str | None

    # Metadados da Sessão (Classificação / Dashboard)
    category: str | None

    # Autenticação e Isolamento de Sessão por Documento
    authenticated_user_id: str | None
    awaiting_identification: bool | None
    pending_support_query: str | None

    # Guardrails de Segurança e Integridade
    is_safe: bool | None
    guardrail_reason: str | None

    # Human Handoff / Agente de Escalonamento
    human_handoff_requested: bool | None
    ticket_protocol: str | None
    summary_for_human: str | None
    queue_target: str | None
    pending_escalation: bool | None
    escalation_intent_retries: int | None
    awaiting_escalation_subject: bool | None
    originated_from_human_intent: bool | None
    had_self_service_attempt: bool | None

    # Observabilidade / Rastreabilidade de Ferramentas
    tools_used: list[str] | None

    # Tier 1 Fast-Path
    fast_path_response: str | None

