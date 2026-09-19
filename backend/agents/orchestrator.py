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

Sua responsabilidade é analisar a mensagem recebida e decidir qual agente especialista deve atendê-la.

Especialistas disponíveis:
1. `knowledge` (Agente de Conhecimento):
   - Perguntas conceituais, comparativos de produtos e serviços da Getnet (ex: Get Clássica vs Get Smart, Get Mini, taxas padrão, antecipação de recebíveis, crediário, Link de Pagamento, Pix, manuais gerais).
   - Perguntas de uso geral fora do catálogo da Getnet que demandam busca web (ex: previsão do tempo, cotação de moedas como euro/dólar, notícias).
   
2. `support` (Agente de Suporte ao Cliente):
   - Perguntas que envolvam dados específicos, histórico financeiro ou terminais do cliente (ex: quando o dinheiro das vendas de ontem será depositado, maquininha sem sinal, erro 51/05, chamados).
   - Respostas a solicitações de identificação/documento do cliente (ex: códigos, números, CPF, identificadores de cadastro).

DIRETRIZ DE CONTEXTO:
Se o status indicar que o suporte estava aguardando identificação do cliente:
- Se a mensagem do usuário for uma resposta tentando fornecer código, documento, número ou dados de identificação (ex: '123', 'fgh', '111.222.333-44', 'meu cpf é tal'), escolha 'support' com categoria 'Autenticação'.
- Se o usuário mudou de assunto e fez uma nova pergunta conceitual/geral (ex: 'Qual é a diferença entre a Get Clássica e a Get Smart?', 'Como funciona o Pix?'), escolha 'knowledge'.

Responda APENAS com um JSON rigorosamente válido:
{
  "next_agent": "<knowledge|support>",
  "category": "<ex: Comparativo Produtos, Financeiro/Extrato, Clima/Geral, Conectividade POS, Transações, Autenticação>",
  "reason": "<breve justificativa>"
}
"""


def orchestrator_node(state: SupportState) -> dict:
    """Nó do Roteador (Router Agent)."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    user_id = state.get("user_id", "cliente1988")
    awaiting_id = state.get("awaiting_identification", False)

    context_info = f"Cliente ID: {user_id}\n"
    if awaiting_id:
        context_info += "STATUS: O suporte solicitou anteriormente a identificação (documento/CPF) do cliente.\n"
    context_info += f"Mensagem do usuário: {last_message}"

    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_PROMPT),
        HumanMessage(content=context_info),
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

    result = {
        "next_agent": next_agent,
        "category": category,
        "routing_reason": reason,
    }

    # Se o usuário estava aguardando identificação mas decidiu mudar de assunto para o conhecimento geral,
    # limpamos o estado de espera para liberar a conversa
    if awaiting_id and next_agent != "support":
        result["awaiting_identification"] = False
        result["pending_support_query"] = None

    return result


def route_after_orchestrator(state: SupportState) -> str:
    """Aresta condicional para transição a partir do Router."""
    return state.get("next_agent", "knowledge")
