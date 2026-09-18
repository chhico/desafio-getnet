"""
agent/state.py
--------------
Estado compartilhado (SupportState) utilizado pelo grafo LangGraph.
"""

from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

# Tipos de agentes especialistas suportados
AgentType = Literal["knowledge", "support", "guardrail_block"]


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
