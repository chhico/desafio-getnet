"""
agent/graph.py
--------------
Grafo de Orquestração Multiagente com LangGraph.
Implementa a colaboração entre os três tipos de agentes exigidos no desafio:
1. Agente Roteador (orchestrator_node)
2. Agente de Conhecimento (knowledge_node)
3. Agente de Suporte ao Cliente (support_node)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.state import SupportState
from backend.agents.guardrails import guardrail_node, route_after_guardrail
from backend.agents.orchestrator import orchestrator_node, route_after_orchestrator
from backend.agents.knowledge_agent import knowledge_node
from backend.agents.support_agent import support_node
from backend.agents.escalation_agent import escalation_node


def build_graph(use_checkpointer: bool = True) -> StateGraph:
    """
    Constrói e compila o grafo multiagente com camada de Guardrails de entrada
    e 4 Agentes Especialistas (Router, Knowledge, Support, Escalation/Human Handoff).
    Fluxo:
      START -> guardrail:
        - seguro   -> orchestrator -> [knowledge | support | escalation | guardrail_block] -> END
        - bloqueio -> END
    """
    builder = StateGraph(SupportState)

    # 1. Registro dos Nós (Guardrail + 4 Agentes)
    builder.add_node("guardrail",    guardrail_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("knowledge",    knowledge_node)
    builder.add_node("support",      support_node)
    builder.add_node("escalation",   escalation_node)

    # 2. Ponto de Entrada: Toda mensagem passa primeiro pelo Guardrail de Segurança
    builder.add_edge(START, "guardrail")

    # 3. Aresta Condicional pós-Guardrail
    builder.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {
            "orchestrator": "orchestrator",
            "guardrail_block": END,
        },
    )

    # 4. Aresta Condicional de Roteamento Dinâmico (Orchestrator)
    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "knowledge": "knowledge",
            "support":   "support",
            "guardrail_block": END,
            "escalation": "escalation",
        },
    )

    # 5. Finalização
    builder.add_edge("knowledge",  END)
    builder.add_edge("support",    END)
    builder.add_edge("escalation", END)

    # 6. Checkpointer de Memória
    checkpointer = MemorySaver() if use_checkpointer else None

    return builder.compile(checkpointer=checkpointer)


# Instância principal do Grafo para a API
support_graph = build_graph(use_checkpointer=True)

# Instância sem checkpointer (compatível com LangGraph Studio)
support_graph_studio = build_graph(use_checkpointer=False)
