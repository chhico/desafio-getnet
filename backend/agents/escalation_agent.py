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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from backend.agents.state import SupportState, get_last_human_message
from backend.agents.tools.escalation_tools import abrir_chamado_servicenow, ESCALATION_TOOLS
from backend.agents.tools.support_tools import _CLIENT_DATABASE, buscar_cliente_por_documento
from backend.core.llm_factory import get_agent_llm

logger = logging.getLogger(__name__)

llm = get_agent_llm(temperature=0)

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
    Garante que o cliente seja identificado por documento (CPF/CNPJ) antes de abrir o chamado no ServiceNow.
    Após a identificação, sintetiza o caso, gera protocolo oficial nominal e formaliza o Human Handoff.
    """
    messages = state.get("messages", [])
    last_user_message = get_last_human_message(messages)
    authenticated_user = state.get("authenticated_user_id")
    awaiting_id = state.get("awaiting_identification", False)

    # -----------------------------------------------------------------------
    # 1. Verificação de Identificação do Cliente (CPF/CNPJ Obrigatório)
    # -----------------------------------------------------------------------
    if not authenticated_user or authenticated_user not in _CLIENT_DATABASE:
        # Tenta identificar o cliente pelo documento informado na mensagem atual
        busca = buscar_cliente_por_documento(last_user_message)
        if busca:
            authenticated_user, client_data = busca
        else:
            # Cliente ainda não informou documento válido
            if awaiting_id:
                msg_erro = AIMessage(
                    content=(
                        f"❌ **Documento não localizado:**\n\n"
                        f"Não encontramos nenhum cadastro ativo com o documento/identificador informado (`{last_user_message}`).\n\n"
                        f"Por favor, verifique os dados e informe novamente seu **documento (CPF/CNPJ)** para podermos transferir seu atendimento com segurança."
                    ),
                    name="escalation",
                )
                return {
                    "messages": [msg_erro],
                    "next_agent": "escalation",
                    "category": "Human Handoff / Escalonamento",
                    "awaiting_identification": True,
                    "pending_escalation": True,
                }

            msg_solicitacao = AIMessage(
                content=(
                    "Compreendo a necessidade de atendimento especializado. Para transferir você para o "
                    "especialista adequado e vincular o protocolo oficial ao seu cadastro com total segurança, "
                    "por favor confirme seu **documento (CPF ou CNPJ)**:"
                ),
                name="escalation",
            )
            return {
                "messages": [msg_solicitacao],
                "next_agent": "escalation",
                "category": "Human Handoff / Escalonamento",
                "routing_reason": "Solicitação de identificação prévia para abertura de chamado nominal no ServiceNow",
                "awaiting_identification": True,
                "pending_escalation": True,
            }

    # -----------------------------------------------------------------------
    # 2. Cliente devidamente identificado! Recupera os dados cadastrais
    # -----------------------------------------------------------------------
    client_data = _CLIENT_DATABASE[authenticated_user]
    nome_cliente = client_data.get("nome", authenticated_user)
    cnpj_cpf = client_data.get("cnpj") or client_data.get("cpf", "N/A")

    # 3. Geração de Protocolo Oficial Getnet
    protocol = f"GET-2026-{random.randint(1000, 9999)}"

    # 4. Consolidação do histórico textual da conversa
    history_lines = []
    for m in messages:
        sender = "Usuário" if (isinstance(m, HumanMessage) or getattr(m, "type", "") == "human") else "Assistente"
        content = m.content if hasattr(m, "content") else str(m)
        history_lines.append(f"{sender}: {content}")
    history_text = "\n".join(history_lines[-8:])  # últimos turnos relevantes

    # 5. Sumarização via LLM para a equipe humana
    queue_target = "Suporte Técnico N2 - Terminais"
    summary_text = "Solicitação de atendimento transferida para especialista humano."
    try:
        response = llm.invoke([
            SystemMessage(content=ESCALATION_SUMMARY_PROMPT),
            HumanMessage(content=f"Cliente: {nome_cliente} (ID: {authenticated_user})\nHistórico Recente:\n{history_text}"),
        ])
        content_res = response.content.strip()
        for line in content_res.split("\n"):
            if line.startswith("FILA:"):
                queue_target = line.replace("FILA:", "").strip()
            elif line.startswith("RESUMO:"):
                summary_text = line.replace("RESUMO:", "").strip()
    except Exception as e:
        logger.warning(f"Falha na sumarização automática do handoff: {e}")

    logger.info(f"🤝 Human Handoff acionado! Cliente: {nome_cliente} | Protocolo: {protocol} | Fila: {queue_target}")

    # 6. Invocação mandatória da ferramenta abrir_chamado_servicenow nominal
    tool_args = {
        "user_id": authenticated_user,
        "motivo": summary_text,
        "protocolo": protocol,
        "fila": queue_target,
    }
    abrir_chamado_servicenow.invoke(tool_args)

    call_id = f"call_sn_{random.randint(1000, 9999)}"
    ai_tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "abrir_chamado_servicenow",
            "args": tool_args,
            "id": call_id,
        }],
    )
    tool_msg = ToolMessage(
        content="None",
        name="abrir_chamado_servicenow",
        tool_call_id=call_id,
    )

    # 7. Mensagem amigável e nominal para o cliente
    msg_cliente = AIMessage(
        content=(
            f"🤝 **Transferência para Atendimento Humano Realizada**\n\n"
            f"Compreendo perfeitamente. Estou transferindo o seu atendimento para a nossa equipe especializada da Getnet.\n\n"
            f"👤 **Cliente:** {nome_cliente} (`{cnpj_cpf}`)\n"
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
        "messages": [ai_tool_call, tool_msg, msg_cliente],
        "next_agent": "escalation",
        "category": "Human Handoff / Escalonamento",
        "routing_reason": "Transferência assistida para operador humano com consolidação de contexto e identificação nominal",
        "human_handoff_requested": True,
        "ticket_protocol": protocol,
        "summary_for_human": summary_text,
        "queue_target": queue_target,
        "tools_used": ["abrir_chamado_servicenow"],
        "authenticated_user_id": authenticated_user,
        "awaiting_identification": False,
        "pending_escalation": False,
    }
