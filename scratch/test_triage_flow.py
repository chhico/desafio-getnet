"""
scratch/test_triage_flow.py
Verifica o fluxo completo de triagem em 3 níveis para solicitações genéricas de humano.
"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.agents.graph import support_graph
from langchain_core.messages import HumanMessage

def test_generic_escalation_3_levels():
    config = {"configurable": {"thread_id": "test_triage_3_levels_001"}}

    # Turno 1: Pedido genérico de humano
    print("--- TURNO 1: Pedido genérico ---")
    state_t1 = support_graph.invoke(
        {"messages": [HumanMessage(content="quero falar com atendente humano")]},
        config=config,
    )
    resp_t1 = state_t1["messages"][-1].content
    print(f"Agente: {state_t1.get('next_agent')}")
    print(f"Awaiting Subject: {state_t1.get('awaiting_escalation_subject')}")
    print(f"Retries: {state_t1.get('escalation_intent_retries')}")
    print(f"Resposta:\n{resp_t1}\n")
    assert state_t1.get("next_agent") == "escalation"
    assert state_t1.get("awaiting_escalation_subject") is True
    assert state_t1.get("escalation_intent_retries") == 1
    assert "sobre qual assunto ou problema você precisa de ajuda" in resp_t1

    # Turno 2: Insistência sem assunto e sem documento
    print("--- TURNO 2: Insistência Nível 2 ---")
    state_t2 = support_graph.invoke(
        {"messages": [HumanMessage(content="não quero robô, transfere logo")]},
        config=config,
    )
    resp_t2 = state_t2["messages"][-1].content
    print(f"Agente: {state_t2.get('next_agent')}")
    print(f"Retries: {state_t2.get('escalation_intent_retries')}")
    print(f"Resposta:\n{resp_t2}\n")
    assert state_t2.get("next_agent") == "escalation"
    assert state_t2.get("escalation_intent_retries") == 2
    assert "fila de atendimento" in resp_t2

    # Turno 3: Insistência com CPF para concluir handoff
    print("--- TURNO 3: Handoff concluído com CPF ---")
    state_t3 = support_graph.invoke(
        {"messages": [HumanMessage(content="prefiro o humano mesmo, meu CPF é 111.222.333-44")]},
        config=config,
    )
    resp_t3 = state_t3["messages"][-1].content
    tools_used = state_t3.get("tools_used", [])
    print(f"Agente: {state_t3.get('next_agent')}")
    print(f"Tools Used: {tools_used}")
    print(f"Protocolo: {state_t3.get('ticket_protocol')}")
    print(f"Resposta:\n{resp_t3}\n")
    assert state_t3.get("next_agent") == "escalation"
    assert "transferir_atendimento_humano" in tools_used
    assert state_t3.get("ticket_protocol") is not None
    assert "Conectando com Atendimento Humano" in resp_t3

    print("🎉 SUCESSO! Todos os 3 níveis de triagem validados com perfeição!")


if __name__ == "__main__":
    test_generic_escalation_3_levels()
