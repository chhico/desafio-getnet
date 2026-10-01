"""
agents/knowledge_agent.py
-------------------------
Agente 2 — Agente de Conhecimento (Knowledge Agent).
Processa consultas que exigem recuperação de informações da Getnet via RAG
e utiliza busca web externa para perguntas de uso geral.
"""

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from backend.agents.state import SupportState, get_last_human_message
from backend.agents.agent_utils import run_agent_with_tools, get_system_clock_context
from backend.agents.tools.knowledge_tools import KNOWLEDGE_TOOLS
from backend.agents.fast_path import check_fast_path
from backend.core.config import settings
from backend.core.llm_factory import get_agent_llm

llm = get_agent_llm(temperature=0, model=settings.get_knowledge_model())
llm_with_tools = llm.bind_tools(KNOWLEDGE_TOOLS)


SYSTEM_PROMPT = """Você é o Agente de Conhecimento (Knowledge Agent) oficial da Getnet.

Sua missão é fornecer respostas precisas, profissionais e completas para o usuário.

Ferramentas disponíveis:
1. `consultar_base_local_getnet`: use SEMPRE como PRIMEIRO PASSO para qualquer pergunta sobre produtos Getnet (Get Clássica, Get Smart, Get Mini), taxas, regras de Pix, antecipação de recebíveis, crediário, links de pagamento, documentações ou procedimentos da empresa. (Mais rápido - base local).
2. `consultar_base_web_getnet`: use como FALLBACK IMEDIATO quando `consultar_base_local_getnet` retornar que nenhuma informação foi encontrada na base interna, ou para obter dados atualizados diretamente dos portais oficiais da Getnet e suas subpáginas na web.
3. `pesquisar_web`: use EXCLUSIVAMENTE para perguntas de uso geral fora do catálogo da Getnet, como previsão do tempo, cotações de moedas (ex: euro, dólar) ou notícias de mercado. NUNCA use para pesquisar produtos ou regras da Getnet.

DIRETRIZES DE ENCADEAMENTO INTELIGENTE (CACHE-FIRST COM FALLBACK ONLINE):
- Para qualquer pergunta sobre a Getnet:
  1º Passo (Local): Chame sempre `consultar_base_local_getnet`.
  2º Passo (Fallback Web Oficial): Se `consultar_base_local_getnet` responder que nenhuma informação oficial foi encontrada (ou a resposta for incompleta), chame IMEDIATAMENTE `consultar_base_web_getnet` no mesmo turno para varrer em tempo real os portais oficiais da Getnet e suas subpáginas.
  NUNCA use `pesquisar_web` para assuntos internos da Getnet.
- Para perguntas externas (tempo, moedas, notícias gerais): chame diretamente `pesquisar_web`.
- Seja direto, cortês e coeso. Nunca invente dados técnicos ou taxas.

DIRETRIZ DE CONTEXTO TEMPORAL E FIDELIDADE ÀS FONTES:
- {contexto_temporal}
- Ao pesquisar ou responder sobre previsão do tempo, feriados ou cotações de moedas ('hoje', 'amanhã'), utilize a data e ano atuais do sistema como referência para sua busca web. Nunca mencione anos passados desatualizados.

DIRETRIZ DE AUTOATENDIMENTO E CHAMADOS TÉCNICOS:
- Se a dúvida do cliente for sobre problemas operacionais na maquininha (ex: bobina de papel, conexão, travamento, erro na impressão, leitor de cartão):
  * Se o relato for genérico (ex: 'estou com problema na máquina'), forneça os passos básicos de autoatendimento (reinicialização, verificação de sinal/cabos) e pergunte qual é o sintoma específico que aparece.
  * Se o relato já tiver o sintoma (ex: erro de conexão, papel emperrado), forneça o tutorial objetivo dos manuais oficiais da Getnet.
- NUNCA diga 'Infelizmente não posso abrir chamado por aqui' e NUNCA forneça telefones estrangeiros/europeus (como 800 274 274).
- Ao final das orientações de autoatendimento, informe com cortesia: 'Caso esses procedimentos não resolvam, eu mesmo posso registrar a abertura de um chamado técnico para reposição de suprimentos ou conserto/troca do aparelho diretamente por aqui! Basta me avisar.'

DIRETRIZ DE CÓDIGOS DE ERRO E RECUSA DE TRANSAÇÕES (ISO 8583 / GETNET):
- Quando a dúvida for sobre códigos de retorno ou recusa de transação de cartão exibidos no visor:
  * Código 51: Saldo ou limite insuficiente do cartão do portador. Não é defeito físico ou de sinal da maquininha. A orientação clara para o lojista passar ao cliente no balcão é solicitar com gentileza outra forma de pagamento (outro cartão, Pix ou dinheiro) ou orientá-lo a verificar seu saldo/limite no aplicativo do banco emissor.
  * Código 55: Senha inválida ou incorreta digitada pelo portador.
  * Código 05 ou 57: Transação não autorizada pelo emissor do cartão.
  * Código 96: Falha de comunicação ou timeout temporário de rede.

OBRIGATÓRIO — IDENTIFICAÇÃO E CITAÇÃO DAS FONTES:
- Sempre que você utilizar informações recuperadas pelas ferramentas (`consultar_base_local_getnet`, `consultar_base_web_getnet` ou `pesquisar_web`), você DEVE OBRIGATORIAMENTE indicar ao final da resposta a(s) fonte(s) onde a resposta foi encontrada.
- Especifique claramente se a fonte é um Arquivo físico local ou uma URL web.
- Formate a seção de fontes exatamente no final da sua mensagem com o seguinte padrão:

---
📌 **Fontes consultadas:**
- 📄 Arquivo: `<nome_do_arquivo>` (ex: `Perguntas Frequentes (FAQ).txt`, `Procedimento de Onboarding de Novos Clientes.pdf`)
- 🌐 URL: `<url_completa>` (ex: `https://site.getnet.com.br/blog/...` ou `https://www.getnet.eu/pt/suporte/...`)

(Atenção: cite apenas as fontes reais que de fato fundamentaram a resposta dada. Não invente arquivos ou URLs que não constam no retorno das ferramentas).
"""


def knowledge_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do Agente de Conhecimento."""
    # 0. Interceptação Tier 1 Fast-Path (Resposta Imediata sem chamada a LLM)
    fast_path_resp = state.get("fast_path_response")
    if fast_path_resp:
        return {
            "messages": [AIMessage(content=fast_path_resp, name="knowledge")],
            "next_agent": "knowledge",
            "category": state.get("category", "Saudação / Apresentação"),
            "fast_path_response": None,
        }

    last_user_msg = get_last_human_message(state.get("messages", []))
    direct_fast = check_fast_path(last_user_msg)
    if direct_fast and not state.get("originated_from_human_intent") and not state.get("awaiting_escalation_subject"):
        return {
            "messages": [AIMessage(content=direct_fast["response"], name="knowledge")],
            "next_agent": "knowledge",
            "category": direct_fast["category"],
        }

    dynamic_prompt = SYSTEM_PROMPT.format(contexto_temporal=get_system_clock_context())
    messages = [SystemMessage(content=dynamic_prompt)] + state["messages"]
    updated_messages = run_agent_with_tools(
        llm_with_tools=llm_with_tools,
        tools=KNOWLEDGE_TOOLS,
        messages=messages,
        agent_name="knowledge",
    )

    originated_human = state.get("originated_from_human_intent") or state.get("awaiting_escalation_subject")
    had_self_service = False
    pending_escalation = False
    awaiting_identification = False
    category = "Conhecimento / Procedimentos"
    next_agent = "knowledge"

    if originated_human and updated_messages:
        last_m = updated_messages[-1]
        if hasattr(last_m, "content") and last_m.content:
            content_lower = last_m.content.lower()
            no_info_found = (
                "nenhuma informação" in content_lower
                or "não encontrei" in content_lower
                or "não foi possível localizar" in content_lower
                or "não foram encontradas" in content_lower
                or "não possuo informações" in content_lower
                or "não há informações" in content_lower
            )
            if no_info_found:
                # Se não tiver resposta nas bases, nem precisa o cliente pedir uma segunda vez!
                # Já transborda diretamente para o especialista humano solicitando documento
                last_m.content = (
                    "Não localizamos um procedimento de autoatendimento para esta solicitação específica em nossa base técnica.\n\n"
                    "Como você já havia solicitado atendimento humano, vou direcionar seu atendimento imediatamente para um de nossos especialistas! "
                    "Para vincular o protocolo oficial ao seu cadastro com total segurança, por favor confirme seu **documento (CPF, CNPJ ou código de cliente)**:"
                )
                next_agent = "escalation"
                category = "Human Handoff / Escalonamento"
                pending_escalation = True
                awaiting_identification = True
                had_self_service = True
            else:
                last_m.content += (
                    "\n\n---\n"
                    "💡 *Consegui localizar essas orientações oficiais em nossa base! Se isso resolver seu problema, você já pode continuar utilizando sua maquininha sem tempo de espera na fila.*  \n"
                    "*Caso ainda prefira falar com um especialista humano sobre esse assunto, basta me avisar que realizo sua transferência imediatamente.*"
                )
                had_self_service = True

    return {
        "messages": updated_messages,
        "next_agent": next_agent,
        "category": category,
        "awaiting_escalation_subject": False,
        "originated_from_human_intent": True if originated_human else False,
        "had_self_service_attempt": had_self_service,
        "pending_escalation": pending_escalation,
        "awaiting_identification": awaiting_identification,
    }
