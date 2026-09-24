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
from backend.core.llm_factory import get_agent_llm

logger = logging.getLogger(__name__)

llm = get_agent_llm(temperature=0)

ORCHESTRATOR_PROMPT = """Você é o Agente Roteador (Router Agent) do ecossistema de suporte da Getnet.

Sua responsabilidade é analisar a mensagem recebida e decidir qual agente especialista deve atendê-la.

Especialistas disponíveis:
1. `knowledge` (Agente de Conhecimento):
   - Perguntas conceituais, comparativos de produtos e serviços da Getnet (ex: Get Clássica vs Get Smart, Get Mini, taxas padrão, antecipação de recebíveis, crediário, Link de Pagamento, Pix, manuais gerais).
   - Perguntas de uso geral fora do catálogo da Getnet que demandam busca web (ex: previsão do tempo, cotação de moedas como euro/dólar, notícias).
   
2. `support` (Agente de Suporte ao Cliente):
   - Perguntas que envolvam dados específicos, histórico financeiro ou terminais do cliente (ex: quando o dinheiro das vendas de ontem será depositado, maquininha sem sinal, erro 51/05, chamados).
   - Dúvidas operacionais sobre como proceder diante de erros em transações na maquininha (ex: o que orientar ao portador do cartão quando der erro de saldo insuficiente/erro 51). NUNCA trate dúvidas operacionais de atendimento/venda na maquininha como fora de escopo!
   - Respostas a solicitações de identificação/documento do cliente (ex: códigos, números, CPF, identificadores de cadastro).

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
     i) Suspeita de fraude ativa na conta do cliente, invasão ou desvio não autorizado de domicílio bancário (ex: conta alterada sem consentimento com valores a receber).
     j) Negociação comercial estratégica de grandes contas corporativas (Key Accounts) ou implantação de rede com TEF dedicado e alto volume transacional.

DIRETRIZ DE CONTEXTO:
- Perguntas conceituais sobre recursos e telas do aplicativo Getnet ou portal web (ex: 'o app permite ver lançamentos futuros?', 'como exportar relatório?') devem ser direcionadas para `knowledge`.
- Se o status indicar que o atendimento está em processo de escalonamento humano aguardando documento/CPF:
  - Se a mensagem do usuário for uma resposta fornecendo documento, CPF, CNPJ ou código, escolha 'escalation' com categoria 'Human Handoff'.
  - Se o usuário insistir ou reiterar o pedido de atendente, escolha 'escalation'.
- Se o status indicar que o suporte estava aguardando identificação do cliente:
  - Se a mensagem do usuário for uma resposta tentando fornecer código, documento, número ou dados de identificação (ex: '123', 'fgh', '111.222.333-44', 'meu cpf é tal'), escolha 'support' com categoria 'Autenticação'.
  - Se o usuário solicitar falar com atendente humano, escolha 'escalation'.
  - Se o usuário mudou de assunto e fez uma nova pergunta conceitual/geral (ex: 'Qual é a diferença entre a Get Clássica e a Get Smart?', 'Como funciona o Pix?'), escolha 'knowledge'.

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

    # Monta breve histórico das últimas interações para evitar desvios semânticos fora de contexto
    recent_history = []
    for m in messages[-4:-1]:
        role = "Usuário" if (isinstance(m, HumanMessage) or getattr(m, "type", "") == "human") else "Assistente"
        text_snip = (m.content or "")[:120].replace("\n", " ")
        recent_history.append(f"{role}: {text_snip}")

    context_info = f"Cliente ID: {user_id}\n"
    if recent_history:
        context_info += f"Histórico recente:\n" + "\n".join(recent_history) + "\n"
    if pending_escalation:
        context_info += "STATUS: O atendimento está em processo de escalonamento humano aguardando o documento/CPF do cliente.\n"
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
