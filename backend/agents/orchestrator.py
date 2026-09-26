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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.agents.state import SupportState, get_last_human_message
from backend.agents.escalation_agent import is_human_insistence
from backend.core.config import settings
from backend.core.llm_factory import get_agent_llm

logger = logging.getLogger(__name__)

llm = get_agent_llm(temperature=0, model=settings.get_router_model())

ORCHESTRATOR_PROMPT = """Você é o Agente Roteador (Router Agent) do ecossistema de suporte da Getnet.

Sua responsabilidade é analisar a mensagem recebida e decidir qual agente especialista deve atendê-la.

Especialistas disponíveis:
1. `knowledge` (Agente de Conhecimento — PRIORIDADE PARA MANUAIS E PROCEDIMENTOS):
   - Perguntas conceituais, comparativos de produtos e serviços da Getnet (ex: Get Clássica vs Get Smart, Get Mini, taxas padrão, antecipação de recebíveis, crediário, Link de Pagamento, Pix, manuais gerais).
   - Regras comerciais e contratuais gerais: políticas de isenção de aluguel por faturamento, regras de meta de vendas, compra vs aluguel de terminal e tarifas de inatividade (ex: 'Se em um mês meu faturamento cair abaixo da meta, o que acontece?', 'Qual o faturamento mínimo para aluguel zero?', 'Existe taxa de inatividade?').
   - Dúvidas sobre recursos, funcionalidades e telas do aplicativo Getnet ou portal web (ex: 'O que consigo fazer no app?', 'O aplicativo permite visualizar lançamentos futuros ou depósitos?', 'Como acompanho vendas pelo app?', relatórios disponíveis no app).
   - Procedimentos operacionais de tela, tutoriais de uso e manuais da maquininha:
     * Como configurar, alterar ou trocar a rede Wi-Fi no terminal.
     * Procedimento passo a passo para cancelamento ou estorno de venda direto na maquininha.
     * Como efetuar fechamento de lote ou fechar o caixa na maquininha.
     * Procedimentos de troca de bobina de papel, reinicialização ou menus operacionais.
     * Como habilitar vouchers, recursos de acessibilidade e funcionalidades do aplicativo.
   - Perguntas de uso geral fora do catálogo da Getnet que demandam busca web (ex: previsão do tempo, cotação de moedas como euro/dólar, notícias, feriados).
   - REGRA DE PRIORIDADE MÁXIMA: Dúvidas conceituais, cenários hipotéticos de regras ou dúvidas que começam com "Como faço para...", "Qual o procedimento para...", "Onde configuro...", "O aplicativo permite...", "Se o faturamento cair..." sobre o manuseio das maquininhas ou serviços da Getnet são consultas públicas a manuais e documentação técnica. Devem SEMPRE ser direcionadas para `knowledge`, pois não exigem identificação nem CPF/CNPJ do lojista!
   
2. `support` (Agente de Suporte ao Cliente):
   - Demandas que envolvam registros específicos, dados privados da conta ou histórico transacional do cliente:
     * Consultas ativas aos dados REAIS e privados da conta do lojista (ex: extratos financeiros da minha loja, valores de vendas que eu realizei, previsão de depósitos/liquidação da sua conta bancária). NÃO confunda com perguntas conceituais ou regras hipotéticas de contrato ('se meu faturamento cair o que acontece?'), que são de `knowledge`.
     * Consulta ao status de conexão e inventário das maquininhas vinculadas ao cadastro do cliente (ex: se as maquininhas da minha loja estão online).
     * Consulta de transações específicas do cliente por ID (ex: TXN-00000), status (recusadas, canceladas, pendentes) ou data.
     * Histórico de chamados técnicos abertos do lojista.
   - Respostas a solicitações anteriores de documento ou identificação do cliente (ex: envio de CPF, CNPJ, código).
   - IMPORTANTE: Se o usuário estiver perguntando instruções de como mexer na maquininha ou procedimentos genéricos (como trocar Wi-Fi ou fazer estorno na máquina), direcione para `knowledge`. Direcione para `support` apenas quando a solicitação exigir consultar dados privados do cadastro/conta do cliente.

3. `guardrail_block` (Bloqueio de Segurança ou Delimitação de Escopo):
   - Solicitações maliciosas, ilegais, tentativas de engenharia social, fraudes ou manipulação de regras (Categoria: 'Segurança / Guardrail').
   - Solicitações manifestamente fora de escopo, irrelevantes ou não suportadas pelo ecossistema Getnet (ex: pedidos de compra de itens de varejo/vestuário como pijamas ou roupas, receitas culinárias, assuntos totalmente desconexos de pagamentos e comércio) (Categoria: 'Fora de Escopo').
   - ATENÇÃO: Dúvidas sobre o que falar para o cliente/portador do cartão que teve compra recusada NÃO são fora de escopo, são atendimento operacional de pagamentos!

4. `escalation` (Agente de Escalonamento para Humanos / Human Handoff):
   - Solicitações explícitas de atendimento humano (ex: 'quero falar com atendente', 'me passe para uma pessoa', 'falar com humano').
   - Casos em que o sistema identifica necessidade crítica de intervenção humana (Escalonamento Implícito):
     a) Dano físico ou acidente no terminal que exige substituição de equipamento ou visita técnica (ex: caiu na água, tela trincada, fumaça, queimou).
     b) Bloqueios judiciais de valores, contestações jurídicas ou chargebacks de alto valor.
     c) Paralisia operacional crítica no estabelecimento com perda de vendas em tempo real (ex: loja/restaurante lotado com maquininhas inoperantes).
     d) Exaustão evidente de autoatendimento (cliente relata que já tentou repetidas vezes reinicialização, troca de chip e procedimentos sem sucesso).
     e) Risco de cancelamento massivo de contratos/terminais por propostas agressivas de concorrentes (Mesa de Retenção).
     f) Violação física de segurança do hardware / Alerta de tamper / suspeita de clonagem ou adulteração de terminal (ex: alerta PED Tampered, trava de segurança ativada).
     g) Notificações formais de órgãos reguladores/fiscalizadores com prazo cominatório fatal (ex: intimação formal do PROCON, Bacen, notificação judicial).
     h) Falecimento de titular da conta, inventário, espólio ou sucessão societária de titularidade com necessidade de análise documental.
     i) Suspeita de fraude ativa na conta do cliente, invasão, comunicação de transferências bancárias suspeitas/não autorizadas (ex: SMS de TED de alto valor não solicitada pelo lojista), acesso clonado ou desvio não autorizado de domicílio bancário (Direcione IMEDIATAMENTE para `escalation`).
     j) Negociação comercial estratégica de grandes contas corporativas (Key Accounts) ou implantação de rede com TEF dedicado e alto volume transacional.

DIRETRIZ DE CONTEXTO:
- PRIORIZE KNOWLEDGE: Perguntas conceituais sobre recursos, menus da maquininha (como Wi-Fi, bobina, cancelamento de venda) ou telas do aplicativo Getnet e portal web devem ser direcionadas para `knowledge`.
- Se a sessão já estiver autenticada com um cliente e o diálogo for um acompanhamento de transação, erro de cartão ou orientação de suporte, pode manter em 'support'.
- Se o status indicar que o atendimento está em processo de escalonamento humano aguardando documento/CPF:
  - Se a mensagem do usuário for uma resposta fornecendo documento, CPF, CNPJ ou código, escolha 'escalation' com categoria 'Human Handoff'.
  - Se o usuário insistir ou reiterar o pedido de atendente, escolha 'escalation'.
- Se o status indicar que o suporte estava aguardando identificação do cliente:
  - Se a mensagem do usuário for uma resposta tentando fornecer código, documento, número ou dados de identificação (ex: '123', 'fgh', '111.222.333-44', 'meu cpf é tal'), escolha 'support' com categoria 'Autenticação'.
  - Se o usuário solicitar falar com atendente humano, escolha 'escalation'.
  - Se o usuário mudou de assunto e fez uma nova pergunta conceitual/geral (ex: 'Qual é a diferença entre a Get Clássica e a Get Smart?', 'Como funciona o Pix?', 'Como trocar o Wi-Fi?'), escolha 'knowledge'.

Responda APENAS com um JSON rigorosamente válido:
{
  "next_agent": "<knowledge|support|guardrail_block|escalation>",
  "category": "<ex: Comparativo Produtos, Financeiro/Extrato, Clima/Geral, Conectividade POS, Transações, Autenticação, Segurança / Guardrail, Human Handoff>",
  "reason": "<breve justificativa>"
}
"""


def orchestrator_node(state: SupportState) -> dict:
    """Nó do Roteador (Router Agent)."""
    messages = state.get("messages", [])
    last_message = get_last_human_message(messages)
    user_id = state.get("user_id", "cliente1988")
    awaiting_id = state.get("awaiting_identification", False)
    pending_escalation = state.get("pending_escalation", False)
    authenticated_id = state.get("authenticated_user_id")
    awaiting_subject = state.get("awaiting_escalation_subject", False)

    # 1. Se estiver em processo de escalonamento humano aguardando documento do cliente
    if pending_escalation:
        cancela_keywords = ["cancela", "cancelar", "não precisa mais", "nao precisa mais", "desisti", "deixa pra lá", "deixa pra la", "esquece"]
        if not any(kw in (last_message or "").lower() for kw in cancela_keywords):
            logger.info("Roteamento determinístico: pending_escalation ativo -> escalation")
            return {
                "next_agent": "escalation",
                "category": "Human Handoff",
                "routing_reason": "Escalonamento humano em andamento: identificação ou confirmação para transferência",
            }
        else:
            state["pending_escalation"] = False
            pending_escalation = False

    # 2. Se o atendimento estiver aguardando o assunto da triagem de escalonamento humano (Nível 1)
    if awaiting_subject:
        from backend.agents.escalation_agent import is_critical_incident
        if is_human_insistence(last_message or ""):
            logger.info("Roteamento determinístico: insistência em humano durante triagem de assunto -> escalation")
            return {
                "next_agent": "escalation",
                "category": "Human Handoff",
                "routing_reason": "Insistência em atendimento humano durante triagem de assunto",
                "awaiting_escalation_subject": True,
            }
        elif is_critical_incident(last_message or "", messages):
            logger.info("Roteamento determinístico: incidente crítico relatado durante triagem -> escalation")
            return {
                "next_agent": "escalation",
                "category": "Human Handoff",
                "routing_reason": "Incidente crítico relatado durante triagem de assunto",
                "awaiting_escalation_subject": False,
            }
        else:
            # Usuário informou o assunto/problema. Limpa a espera de assunto para que o roteador avalie o tema livremente
            awaiting_subject = False

    # Monta breve histórico das últimas interações para evitar desvios semânticos fora de contexto
    recent_history = []
    for m in messages[-4:-1]:
        role = "Usuário" if (isinstance(m, HumanMessage) or getattr(m, "type", "") == "human") else "Assistente"
        text_snip = (m.content or "")[:120].replace("\n", " ")
        recent_history.append(f"{role}: {text_snip}")

    context_info = f"Cliente ID: {user_id}\n"
    if authenticated_id:
        context_info += f"STATUS: Cliente já autenticado na sessão ({authenticated_id}). Dúvidas de acompanhamento de atendimento técnico/suporte podem permanecer em 'support'.\n"
    if recent_history:
        context_info += f"Histórico recente:\n" + "\n".join(recent_history) + "\n"
    if state.get("awaiting_escalation_subject"):
        context_info += (
            "STATUS: O cliente havia solicitado atendente humano e agora respondeu qual é o seu assunto ou problema.\n"
            "DIRETRIZ OBRIGATÓRIA DE AUTOATENDIMENTO INTELIGENTE (SMART DEFLECTION):\n"
            "  - O objetivo é tentar resolver o problema do cliente consultando a base oficial da Getnet antes de fazer o transbordo!\n"
            "  - Para procedimentos técnicos de maquininha (como bobina entupida, troca de bobina, Wi-Fi, travamento, menus operacionais, estorno) ou manuais de produtos Getnet: direcione OBRIGATORIAMENTE para 'knowledge'.\n"
            "  - Para consultas a dados privados, transações ou extratos da conta do cliente: direcione para 'support'.\n"
            "  - NUNCA escolha 'escalation' aqui para procedimentos e dúvidas que possam ser respondidos por 'knowledge' ou 'support'!\n"
        )
    elif awaiting_id:
        context_info += "STATUS: O suporte solicitou anteriormente a identificação (documento/CPF) do cliente.\n"
    context_info += f"Mensagem atual do usuário: {last_message}"

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

    result = {
        "next_agent": next_agent,
        "category": category,
        "routing_reason": reason,
    }

    # Se o usuário informou o assunto durante a triagem, limpa o estado de espera
    if not awaiting_subject and state.get("awaiting_escalation_subject"):
        result["awaiting_escalation_subject"] = False

    # Se o usuário estava aguardando identificação mas decidiu mudar de assunto para o conhecimento geral,
    # limpamos o estado de espera para liberar a conversa
    if awaiting_id and next_agent != "support":
        result["awaiting_identification"] = False
        result["pending_support_query"] = None

    # Se o roteador semântico identificar violação ou assunto fora de escopo
    if next_agent == "guardrail_block":
        cat_lower = (category or "").lower()
        reason_lower = (reason or "").lower()
        msg_lower = (last_message or "").lower()

        is_out_of_scope = (
            "fora de escopo" in cat_lower
            or "escopo" in cat_lower
            or "não relacionada" in reason_lower
            or "não relacionado" in reason_lower
            or "fora de escopo" in reason_lower
        )

        if is_out_of_scope:
            msg_bloqueio = AIMessage(
                content=(
                    "🧭 **Solicitação fora do escopo de atendimento**\n\n"
                    "Sou o assistente virtual da Getnet, especializado em soluções de pagamento, "
                    "maquininhas, taxas e serviços financeiros para o seu negócio.\n\n"
                    "Não comercializamos produtos de varejo (como roupas, calçados ou alimentos) "
                    "e este canal não atende a solicitações desse tipo.\n\n"
                    "Como posso ajudar você com os serviços, maquininhas ou soluções de pagamento da Getnet?"
                ),
                name="guardrail_block",
            )
        else:
            msg_bloqueio = AIMessage(
                content=(
                    "🛡️ **Solicitação bloqueada pelas políticas de segurança e uso**\n\n"
                    "Identificamos que sua mensagem não está em conformidade com as diretrizes de "
                    "segurança da informação e uso operacional do canal de atendimento da Getnet.\n\n"
                    "Por motivos de conformidade e segurança, o acesso ou operação solicitada não é permitido nesta sessão.\n\n"
                    "Por favor, reformule sua solicitação com foco em suporte técnico, soluções comerciais "
                    "ou serviços oficiais da Getnet."
                ),
                name="guardrail_block",
            )
        result["messages"] = [msg_bloqueio]

    return result


def route_after_orchestrator(state: SupportState) -> str:
    """Aresta condicional para transição a partir do Router."""
    return state.get("next_agent", "knowledge")
