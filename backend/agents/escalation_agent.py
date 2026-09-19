"""
agents/escalation_agent.py
--------------------------
Agente 4 — Agente de Escalonamento para Humanos (Human Escalation Agent / Human Handoff).
Responsável por orquestrar a transferência assistida de chamados para operadores humanos:
- Detecta necessidade de intervenção humana (solicitações explícitas, falha física ou exaustão).
- Gera protocolo oficial auditável (GET-2026-XXXX).
- Realiza sumarização do histórico de atendimento via LLM para o operador.
- Define a fila de atendimento especializada (ex: Suporte N2, Comercial, Ouvidoria).
"""

import random
import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import SupportState
from backend.core.config import settings

logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)

ESCALATION_SUMMARY_PROMPT = """Você é o Assistente de Triagem Técnica e Human Handoff da Getnet.
Sua missão é analisar o histórico da conversa entre o cliente e os agentes automatizados e gerar uma síntese executiva para o operador humano que assumirá o atendimento.

Instruções:
1. Resuma com precisão o problema relatado pelo cliente em até 3 frases.
2. Indique a fila técnica ideal:
   - "Suporte Técnico N2 - Terminais" (para falhas de sinal, bobinas, maquininha com erro, defeito físico, tamper de segurança).
   - "Segurança da Informação e Prevenção a Fraudes" (para suspeita de golpe na conta, alteração de domicílio bancário, fraude em andamento).
   - "Jurídico, Compliance e Regulatório" (para notificações Procon, intimações judiciais, bloqueios cominatórios, falecimento/espólio).
   - "Mesa de Grandes Contas e Key Accounts" (para projetos corporativos de grande porte, implantação de redes e TEF dedicado).
   - "Mesa de Negócios e Tarifas" (para dúvidas contratuais, negociação de taxas, cancelamento, credenciamento).
   - "Ouvidoria e Atendimento Geral" (para reclamações gerais, solicitações de atendente humano, dúvidas diversas).

Responda em formato estrito:
FILA: <nome da fila>
RESUMO: <resumo objetivo do caso>
"""


def escalation_node(state: SupportState) -> dict:
    """
    Nó do Agente de Escalonamento para Humanos.
    Gera o protocolo, sintetiza o caso e formaliza o Human Handoff.
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "cliente1988")
    authenticated_user = state.get("authenticated_user_id")

    # 1. Geração de Protocolo Oficial Getnet
    protocol = f"GET-2026-{random.randint(1000, 9999)}"

    # 2. Consolidação do histórico textual da conversa
    history_lines = []
    for m in messages:
        sender = "Usuário" if (isinstance(m, HumanMessage) or getattr(m, "type", "") == "human") else "Assistente"
        content = m.content if hasattr(m, "content") else str(m)
        history_lines.append(f"{sender}: {content}")
    history_text = "\n".join(history_lines[-8:])  # últimos turnos relevantes

    # 3. Sumarização via LLM para a equipe humana
    queue_target = "Suporte Técnico N2 - Terminais"
    summary_text = "Solicitação de atendimento transferida para especialista humano."
    try:
        response = llm.invoke([
            SystemMessage(content=ESCALATION_SUMMARY_PROMPT),
            HumanMessage(content=f"Cliente ID: {authenticated_user or user_id}\nHistórico Recente:\n{history_text}"),
        ])
        content_res = response.content.strip()
        for line in content_res.split("\n"):
            if line.startswith("FILA:"):
                queue_target = line.replace("FILA:", "").strip()
            elif line.startswith("RESUMO:"):
                summary_text = line.replace("RESUMO:", "").strip()
    except Exception as e:
        logger.warning(f"Falha na sumarização automática do handoff: {e}")

    logger.info(f"🤝 Human Handoff acionado! Protocolo: {protocol} | Fila: {queue_target}")

    # 4. Mensagem amigável e segura para o cliente
    msg_cliente = AIMessage(
        content=(
            f"🤝 **Transferência para Atendimento Humano Realizada**\n\n"
            f"Compreendo perfeitamente. Estou transferindo o seu atendimento para a nossa equipe especializada da Getnet.\n\n"
            f"📋 **Protocolo de Atendimento:** `{protocol}`\n"
            f"🏢 **Fila Direcionada:** {queue_target}\n"
            f"⏱️ **Tempo Estimado de Espera:** ~2 minutos\n\n"
            f"Já repassei ao especialista o resumo da sua solicitação e o histórico da nossa conversa "
            f"para que você **não precise repetir nenhuma informação**.\n\n"
            f"Um de nossos operadores humanos responderá nesta mesma tela a qualquer instante."
        ),
        name="escalation",
    )

    return {
        "messages": [msg_cliente],
        "next_agent": "escalation",
        "category": "Human Handoff / Escalonamento",
        "routing_reason": "Transferência assistida para operador humano com consolidação de contexto",
        "human_handoff_requested": True,
        "ticket_protocol": protocol,
        "summary_for_human": summary_text,
        "queue_target": queue_target,
    }
