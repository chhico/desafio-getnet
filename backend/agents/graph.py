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
from backend.agents.orchestrator import orchestrator_node, route_after_orchestrator
from backend.agents.knowledge_agent import knowledge_node
from backend.agents.support_agent import support_node


def build_graph(use_checkpointer: bool = True) -> StateGraph:
    """
    Constrói e compila o grafo multiagente.
    """
    builder = StateGraph(SupportState)

    # 1. Registro dos Nós dos 3 Agentes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("knowledge",    knowledge_node)
    builder.add_node("support",      support_node)

    # 2. Ponto de Entrada: Toda mensagem vai primeiro para o Agente Roteador
    builder.add_edge(START, "orchestrator")

    # 3. Aresta Condicional de Roteamento Dinâmico
    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "knowledge": "knowledge",
            "support":   "support",
        },
    )

    # 4. Finalização
    builder.add_edge("knowledge", END)
    builder.add_edge("support",   END)

    # 5. Checkpointer de Memória
    checkpointer = MemorySaver() if use_checkpointer else None

    return builder.compile(checkpointer=checkpointer)


# Instância principal do Grafo para a API
support_graph = build_graph(use_checkpointer=True)

# Instância sem checkpointer (compatível com LangGraph Studio)
support_graph_studio = build_graph(use_checkpointer=False)
