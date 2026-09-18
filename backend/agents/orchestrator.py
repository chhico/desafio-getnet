"""
agents/orchestrator.py
-----------------------
Agente 1 — Agente Roteador (Router Agent).
Atua como ponto de entrada principal para as mensagens dos usuários.
Analisa a mensagem recebida e o contexto do cliente (user_id), decidindo
qual agente especializado (Knowledge ou Support) deve processá-la.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import SupportState
from backend.core.config import settings

logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)

ORCHESTRATOR_PROMPT = """Você é o Agente Roteador (Router Agent) do ecossistema de suporte da Getnet.

Sua única responsabilidade é analisar a mensagem recebida do usuário e decidir qual agente especialista deve atendê-la.

Especialistas disponíveis:
1. `knowledge` (Agente de Conhecimento):
   - Perguntas conceituais, comparativos de produtos e serviços da Getnet (ex: Get Clássica vs Get Smart, Get Mini, taxas padrão, antecipação de recebíveis, crediário, Link de Pagamento, Pix, manuais gerais).
   - Perguntas de uso geral fora do catálogo da Getnet que demandam busca web (ex: previsão do tempo, cotação de moedas como euro/dólar, notícias).
   
2. `support` (Agente de Suporte ao Cliente):
   - Perguntas que envolvam dados específicos, histórico financeiro ou terminais do cliente autenticado (user_id).
   - Exemplos: Quando o dinheiro das vendas de ontem será depositado, por que a maquininha do cliente não conecta ou está sem sinal, análise de erros de transação recusada na maquininha (código 51, 05), abertura de chamados técnicos.

Responda APENAS com um JSON rigorosamente válido:
{{
  "next_agent": "<knowledge|support>",
  "category": "<ex: Comparativo Produtos, Financeiro/Extrato, Clima/Geral, Conectividade POS, Transações, Crediário>",
  "reason": "<breve justificativa>"
}}
"""


def orchestrator_node(state: SupportState) -> dict:
    """Nó do Roteador (Router Agent)."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    user_id = state.get("user_id", "cliente1988")

    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_PROMPT),
        HumanMessage(content=f"Cliente ID: {user_id}\nMensagem do usuário: {last_message}"),
    ])

    try:
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw.strip())
        next_agent = data.get("next_agent", "knowledge")
        category = data.get("category", "Geral")
        reason = data.get("reason", "")
    except Exception as e:
        logger.warning(f"Falha ao interpretar JSON do roteador: {e}. Usando fallback 'knowledge'.")
        next_agent = "knowledge"
        category = "Geral"
        reason = "Fallback"

    # Se next_agent vier com nome antigo, mapeia
    if next_agent in ["rag", "research"]:
        next_agent = "knowledge"

    return {
        "next_agent": next_agent,
        "category": category,
        "routing_reason": reason,
    }


def route_after_orchestrator(state: SupportState) -> str:
    """Aresta condicional para transição a partir do Router."""
    return state.get("next_agent", "knowledge")
