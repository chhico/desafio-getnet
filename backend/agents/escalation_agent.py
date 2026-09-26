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
from backend.agents.tools.escalation_tools import transferir_atendimento_humano, ESCALATION_TOOLS
from backend.agents.tools.support_tools import _CLIENT_DATABASE, buscar_cliente_por_documento
from backend.core.config import settings
from backend.core.llm_factory import get_agent_llm

logger = logging.getLogger(__name__)

llm = get_agent_llm(temperature=0, model=settings.get_escalation_model())

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


CRITICAL_KEYWORDS = [
    # Dano físico / Sinistro térmico / Hardware irrecuperável
    "queimou", "queimada", "queimado", "fritadeira", "óleo", "fogo", "fumaça",
    "derreteu", "derretida", "curto-circuito", "sinistro", "caiu no chão",
    "quebrou a tela", "tela de vidro inteira", "arrombamento", "assaltada",
    "assalto", "ped tampered", "tamper detected", "lacre de segurança",
    "lacre rompido", "lacre traseiro", "lacre plástico", "lacre perfurado",
    "chupa-cabra", "security breach", "leitor físico de chip da maquininha quebrou",
    "substituição física", "técnico de campo para substituir",
    # Fraude ativa / Desvio financeiro / Golpe
    "fraude", "golpe", "invasão", "invadido", "invadiram", "senha vazada",
    "desvio", "desviar", "chave pix desconhecida", "conta bancária desconhecida",
    "conta desconhecida", "não autorizada", "antecipação ilícita", "antecipação não autorizada",
    "transferência não autorizada", "clonaram", "clonagem",
    # Jurídico / Regulatório
    "bloqueio judicial", "liminar", "tutela de urgência", "ordem judicial",
    "juiz", "vara cível", "penhora", "multa diária", "intimação", "ministério público",
    "procon", "bacen", "banco central", "notificação extrajudicial", "ofício formal",
    "ofício do ministério", "processo administrativo",
    # Grandes Contas / TEF / Black Friday
    "rede varejista", "black friday", "tef dedicado", "servidor tef",
    "concentradores getnet", "pontos de venda paralisados", "checkouts travados",
    "gateway corporativo", "perda de vendas", "50 pedidos por minuto",
    "key accounts", "sla dedicado",
    # Churn agressivo / Cancelamento por concorrente
    "cancelar imediatamente", "cancelar minhas", "rescindir o contrato",
    "devolver minhas", "devolver as 10", "proposta da concorrência",
    "stone me ofereceu", "cielo me ofereceu", "cobrir a oferta", "cobrir a proposta",
    # Mesa de Negócios e Tarifas / Renegociação comercial
    "renegociar formalmente", "renegociar o pacote", "renegociar nosso plano de taxas",
    "renegociar taxas", "renegociar tarifas", "isenção de aluguel", "isenção de mensalidade",
    "pacote de taxas mdr", "taxas mdr",
    # Supervisão Humana de Atendimento / Escalação por Erro Grave
    "supervisora da equipe", "supervisão humana", "orientação completamente errada",
    "falar urgente com a supervisão", "supervisão de atendimento", "supervisora de atendimento",
    # Exaustão severa comprovada de troubleshooting
    "já liguei 4 vezes", "já reiniciei 10 vezes", "já abri 5 protocolos",
    "5 protocolos sem retorno", "4 protocolos abertos", "há mais de 3 semanas"
]

INSISTENCE_KEYWORDS = [
    "não quero robô", "nao quero robo", "não quero falar com robô", "nao quero falar com robo",
    "não vou falar com robô", "transfere logo", "transfira logo", "quero humano",
    "quero falar com humano", "quero atendente", "quero pessoa", "me passa logo",
    "me passa pro atendente", "apenas transfira", "só transfere", "so transfere",
    "humano agora", "pessoa de verdade", "não me interessa", "fale com humano",
    "supervisor", "supervisora", "atendente de verdade",
    "falar com atendente", "falar com humano", "prefiro humano", "com um humano",
    "falar com uma pessoa", "me atenda um humano", "passa para humano"
]


def is_critical_incident(message: str, messages: list) -> bool:
    """Verifica se a mensagem atual ou turnos recentes contêm evidência de incidente crítico (Fast-Track)."""
    text_to_check = message.lower()
    for m in messages[-4:]:
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            text_to_check += " " + (m.content or "").lower()
            
    return any(kw in text_to_check for kw in CRITICAL_KEYWORDS)


def is_human_insistence(message: str) -> bool:
    """Verifica se a mensagem é uma insistência ou recusa em explicar o assunto."""
    msg_low = message.lower()
    return any(kw in msg_low for kw in INSISTENCE_KEYWORDS)


def escalation_node(state: SupportState) -> dict:
    """
    Nó do Agente de Escalonamento para Humanos.
    Implementa:
    1. Fast-Track Imediato para Incidentes Críticos Objetivos (Fraude, PED Tamper, Sinistro, Bloqueio Judicial).
    2. Triagem de 2 Níveis para Pedidos Genéricos de Atendimento Humano:
       - Nível 1: Acolhimento e solicitação do assunto para tentar agilizar/direcionar.
       - Nível 2: Insistência educada informando a rapidez do autoatendimento vs fila de espera.
       - Nível 3: Handoff formal, exigindo identificação por documento (CPF/CNPJ).
    """
    messages = state.get("messages", [])
    last_user_message = get_last_human_message(messages)
    authenticated_user = state.get("authenticated_user_id")
    awaiting_id = state.get("awaiting_identification", False)
    pending_escalation = state.get("pending_escalation", False)
    retries = state.get("escalation_intent_retries", 0) or 0
    awaiting_subject = state.get("awaiting_escalation_subject", False)
    had_self_service = state.get("had_self_service_attempt", False)

    # -----------------------------------------------------------------------
    # 1. Verificação de Incidente Crítico (Fast-Track)
    # -----------------------------------------------------------------------
    is_critical = is_critical_incident(last_user_message, messages)
    has_doc = buscar_cliente_por_documento(last_user_message) is not None

    # Se NÃO for incidente crítico e NÃO estiver aguardando documento pós-confirmação:
    if not is_critical and not pending_escalation:
        # Nível 1 de Triagem: primeiro pedido de humano
        if retries == 0 and not had_self_service:
            msg_triagem_1 = AIMessage(
                content=(
                    "Com certeza posso transferir você para um especialista humano! 😊\n\n"
                    "Mas para que eu possa direcionar seu atendimento para a fila certa (e verificar se consigo agilizar sua solução imediatamente sem tempo de espera na fila), "
                    "você poderia me contar resumidamente **sobre qual assunto ou problema você precisa de ajuda**?"
                ),
                name="escalation",
            )
            return {
                "messages": [msg_triagem_1],
                "next_agent": "escalation",
                "category": "Human Handoff / Triagem",
                "routing_reason": "Triagem de Intenção Nível 1: Solicitação de assunto prévio antes do handoff",
                "escalation_intent_retries": 1,
                "awaiting_escalation_subject": True,
                "originated_from_human_intent": True,
            }

        # Nível 2 de Triagem: cliente insiste no humano sem informar assunto e sem ter tentado autoatendimento
        elif retries == 1 and not has_doc and is_human_insistence(last_user_message) and awaiting_subject and not had_self_service:
            msg_triagem_2 = AIMessage(
                content=(
                    "Entendo perfeitamente sua preferência! Mas vale lembrar que por aqui eu consigo consultar seus dados cadastrais, extratos, transações e tirar dúvidas técnicas instantaneamente, sem nenhum tempo de espera em fila de atendimento.\n\n"
                    "Gostaria de me adiantar sua dúvida para tentarmos resolver agora ou realmente prefere aguardar na fila de transferência para a nossa equipe humana?"
                ),
                name="escalation",
            )
            return {
                "messages": [msg_triagem_2],
                "next_agent": "escalation",
                "category": "Human Handoff / Triagem",
                "routing_reason": "Triagem de Intenção Nível 2: Insistência educada sobre agilidade do autoatendimento",
                "escalation_intent_retries": 2,
                "awaiting_escalation_subject": True,
                "originated_from_human_intent": True,
            }

        # Nível 3: Cliente reiterou a insistência ou enviou documento -> Aceita o handoff!

    # -----------------------------------------------------------------------
    # 2. Verificação de Identificação do Cliente (CPF/CNPJ Obrigatório)
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
                        f"Por favor, verifique os dados e informe novamente seu **documento (CPF, CNPJ ou código de cliente como 'cliente2024')** para podermos transferir seu atendimento com segurança."
                    ),
                    name="escalation",
                )
                return {
                    "messages": [msg_erro],
                    "next_agent": "escalation",
                    "category": "Human Handoff / Escalonamento",
                    "awaiting_identification": True,
                    "pending_escalation": True,
                    "escalation_intent_retries": retries,
                }

            msg_solicitacao = AIMessage(
                content=(
                    "Compreendo a necessidade de atendimento especializado. Para transferir você para o "
                    "especialista adequado e vincular o protocolo oficial ao seu cadastro com total segurança, "
                    "por favor confirme seu **documento (CPF, CNPJ ou código de cliente)**:"
                ),
                name="escalation",
            )
            return {
                "messages": [msg_solicitacao],
                "next_agent": "escalation",
                "category": "Human Handoff / Escalonamento",
                "routing_reason": "Solicitação de identificação prévia para abertura de chamado nominal",
                "awaiting_identification": True,
                "pending_escalation": True,
                "escalation_intent_retries": retries,
            }

    # -----------------------------------------------------------------------
    # 3. Cliente devidamente identificado! Recupera os dados cadastrais
    # -----------------------------------------------------------------------
    client_data = _CLIENT_DATABASE[authenticated_user]
    nome_cliente = client_data.get("nome", authenticated_user)
    cnpj_cpf = client_data.get("cnpj") or client_data.get("cpf", "N/A")

    # 4. Geração de Protocolo Oficial Getnet
    protocol = f"GET-2026-{random.randint(1000, 9999)}"

    # 5. Consolidação do histórico textual da conversa
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

    # 6. Invocação mandatória da ferramenta transferir_atendimento_humano nominal
    tool_args = {
        "user_id": authenticated_user,
        "motivo": summary_text,
        "protocolo": protocol,
        "fila": queue_target,
    }
    tool_result = transferir_atendimento_humano.invoke(tool_args)
    operador_conectado = tool_result.get("operador", "Especialista Getnet")
    tempo_estimado = tool_result.get("tempo_estimado", "< 1 minuto")

    call_id = f"call_handoff_{random.randint(1000, 9999)}"
    ai_tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "transferir_atendimento_humano",
            "args": tool_args,
            "id": call_id,
        }],
    )
    tool_msg = ToolMessage(
        content=str(tool_result),
        name="transferir_atendimento_humano",
        tool_call_id=call_id,
    )

    # 7. Mensagem amigável e nominal para o cliente em tempo real
    msg_cliente = AIMessage(
        content=(
            f"🤝 **Conectando com Atendimento Humano em Tempo Real**\n\n"
            f"Compreendo a urgência e a importância da sua solicitação. O transbordo imediato para um especialista humano foi iniciado agora!\n\n"
            f"👨‍💼 **Atendente Designado:** {operador_conectado}\n"
            f"🏢 **Fila Especializada:** {queue_target}\n"
            f"⏱️ **Status da Conexão:** Em atendimento imediato ({tempo_estimado})\n"
            f"📋 **Protocolo Oficial:** `{protocol}`\n"
            f"👤 **Cliente Identificado:** {nome_cliente} (`{cnpj_cpf}`)\n\n"
            f"📋 **Contexto Transmitido ao Atendente:**\n"
            f"> *\"{summary_text}\"*\n\n"
            f"O operador **{operador_conectado}** já está com todo o seu histórico e dados na tela. "
            f"Você **não precisará repetir nenhuma informação**. Ele assumirá o diálogo aqui no chat a qualquer instante!"
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
        "tools_used": ["transferir_atendimento_humano"],
        "authenticated_user_id": authenticated_user,
        "awaiting_identification": False,
        "pending_escalation": False,
        "awaiting_escalation_subject": False,
        "escalation_intent_retries": 0,
    }
