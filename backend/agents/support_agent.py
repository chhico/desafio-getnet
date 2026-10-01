"""
agents/support_agent.py
-----------------------
Agente 3 — Agente de Suporte ao Cliente (Customer Support Agent).
Oferece suporte ao cliente recuperando dados relevantes do usuário (user_id)
para resolver solicitações financeiras, operacionais e técnicas de maquininhas.
Implementa fluxo de identificação por documento (CPF/ID), isolamento de sessão
e proteção estrita de dados bancários/operacionais.
"""

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from backend.agents.state import SupportState, get_last_human_message
from backend.agents.agent_utils import run_agent_with_tools, get_system_clock_context
from backend.agents.tools.support_tools import (
    SUPPORT_TOOLS,
    _CLIENT_DATABASE,
    buscar_cliente_por_documento,
)
from backend.core.config import settings
from backend.core.llm_factory import get_agent_llm

llm = get_agent_llm(temperature=0, model=settings.get_support_model())
llm_with_tools = llm.bind_tools(SUPPORT_TOOLS)

SYSTEM_PROMPT = """Você é o Agente de Suporte ao Cliente (Customer Support Agent) da Getnet.

Seu foco é resolver problemas e dúvidas personalizadas de clientes credenciados.
Você está atendendo o cliente autenticado: {user_id} - {nome_cliente}.

{contexto_temporal}

Ferramentas disponíveis:
1. `consultar_vendas_e_liquidacao`: use para consultar o extrato financeiro, histórico de vendas por data ou geral, saldo a receber e dados bancários cadastrados do cliente.
2. `consultar_status_maquininhas`: use para verificar modelos vinculados, número de série, status de conexão (online/offline) e sinal de rede.
3. `consultar_transacoes_e_erros`: use SEMPRE que o cliente perguntar por transações, seja por ID específico (ex: TXN-00000, TXN-99821), por status (aprovadas, recusadas) ou por data.
4. `consultar_chamados_suporte`: use SEMPRE que o cliente perguntar pelo status de chamados técnicos abertos anteriormente, protocolos de suporte, agendamento de visita técnica ou reagendamento de visita de manutenção.
5. `abrir_chamado_suporte`: use SEMPRE que o cliente solicitar abertura de chamado, pedido de técnico, conserto/reparo de máquina, reposição de bobinas de papel térmico para a maquininha, solicitação de troca de equipamento com defeito ou envio de suprimentos.

DIRETRIZES DE RESOLUÇÃO TEMPORAL E FIDELIDADE ESTREITA À BASE DE DADOS (GROUNDING):
- O contexto temporal do sistema acima informa a data, horário e ano correntes no servidor Getnet.
- Para qualquer pergunta sobre períodos relativos (como 'ontem', 'hoje', 'semana passada' ou 'últimas vendas') ou datas específicas:
  1. Identifique a data solicitada com base no contexto temporal do sistema e chame as ferramentas de suporte (`consultar_vendas_e_liquidacao` ou `consultar_transacoes_e_erros`) para consultar o histórico real do cliente `{user_id}` no banco de dados.
  2. Baseie sua resposta EXCLUSIVAMENTE nas datas, valores e contas bancárias retornadas pelo banco de dados.
  3. Se o cliente perguntar por uma data específica ou período relativo (ex: 'ontem') e o banco de dados informar que não constam lançamentos para aquela data exata, esclareça com transparência que não há vendas registradas para essa data e apresente os dados do fechamento mais recente que de fato consta no cadastro (com sua data real, valores e previsão de depósito bancário).
  4. NUNCA deduza, presuma ou invente datas, valores, transações ou anos que não constem no banco de dados e no retorno das ferramentas.

DIRETRIZES DE ATENDIMENTO E ISOLAMENTO DE DADOS:
- SEMPRE passe o identificador do cliente autenticado `{user_id}` nas ferramentas para consultar sua base de dados exclusiva em `_CLIENT_DATABASE`.
- Você só pode consultar e fornecer informações pertencentes a {nome_cliente} (ID: {user_id}). Quando o cliente pedir suas informações, envie apenas o que é seu.
- NUNCA presuma antecipadamente se uma transação, maquininha ou movimentação existe ou não. SEMPRE chame a respectiva ferramenta usando `{user_id}` para verificar se a informação está contida nos registros do cliente.
- Caso a ferramenta retorne que a informação específica (ex: ID de transação, data ou terminal) não foi encontrada, informe de forma clara e amigável ao cliente que aquele registro específico não foi localizado para o seu cadastro.
DIRETRIZ DE ESPECIFICIDADE E QUALIFICAÇÃO DO PROBLEMA TÉCNICO:
- Ao atender uma demanda técnica de maquininha ou chamado, avalie a completude da solicitação:
  1. RELATO ESPECÍFICO (Ação ou Sintoma claros):
     * O cliente já informou expressamente o que ocorreu ou o que precisa (ex: 'acabaram as bobinas', 'quero abrir chamado para consertar', 'a tela quebrou', 'o leitor não passa cartão', 'erro de recusa 51').
     * Execute imediatamente a ferramenta correspondente (`abrir_chamado_suporte`, `consultar_transacoes_e_erros` ou `consultar_status_maquininhas`) preenchendo o `motivo` com fidelidade estrita ao defeito ou solicitação informada pelo cliente.
  2. RELATO VAGO / GENÉRICO (Menção a problema sem descrever o sintoma nem a ação desejada):
     * O cliente apenas disse que algo está com defeito sem especificar o sintoma (ex: 'estou com problema na máquina', 'minha maquininha não funciona', 'problema na bobina' sem dizer se acabou ou travou).
     * NÃO abra um chamado presuntivo nem tente adivinhar a peça/serviço. Acolha com empatia e faça UMA pergunta objetiva de qualificação para descobrir o defeito exato antes de abrir o chamado:
       (Exemplo: "Compreendo a situação! Para que eu possa te orientar no procedimento exato ou registrar o chamado correto: o que está acontecendo especificamente? Por exemplo: o papel acabou ou emperrou? O visor exibe algum código de erro? O aparelho não liga?")
     * Assim que o cliente responder com o sintoma real no turno seguinte, chame `abrir_chamado_suporte` registrando o motivo verdadeiro informado por ele.
"""


def support_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do Agente de Suporte ao Cliente com autenticação por documento e isolamento de sessão."""
    messages = state.get("messages", [])
    last_user_message = get_last_human_message(messages)

    authenticated_user_id = state.get("authenticated_user_id")
    awaiting_identification = state.get("awaiting_identification", False)
    pending_query = state.get("pending_support_query")

    # -----------------------------------------------------------------------
    # CENÁRIO 1: Sessão JÁ está autenticada para um cliente específico
    # -----------------------------------------------------------------------
    if authenticated_user_id and authenticated_user_id in _CLIENT_DATABASE:
        client_data = _CLIENT_DATABASE[authenticated_user_id]

        # Verificação de segurança: o usuário está tentando consultar outro cliente na mesma sessão?
        outra_busca = buscar_cliente_por_documento(last_user_message)
        if outra_busca and outra_busca[0] != authenticated_user_id:
            msg_lower = (last_user_message or "").lower()
            eh_contexto_venda_terceiro = any(k in msg_lower for k in [
                "cartão do cliente", "portador", "comprador", "venda recusada",
                "passou o cartão", "compra dele", "cartão dele", "transação do cliente",
                "cliente da loja", "cliente do balcão", "cliente passou"
            ])

            if not eh_contexto_venda_terceiro:
                outro_id, outro_data = outra_busca
                msg_bloqueio = AIMessage(
                    content=(
                        f"🔒 **Acesso Não Permitido por Segurança:**\n\n"
                        f"Esta sessão já está autenticada para o cliente **{client_data['nome']}**.\n"
                        f"Por diretrizes de sigilo bancário e proteção de dados da Getnet, não é permitido consultar "
                        f"informações de outro cliente ou documento nesta mesma conversa.\n\n"
                        f"Caso deseje consultar outro cadastro, por favor inicie uma **Nova Conversa**."
                    ),
                    name="support",
                )
                return {
                    "messages": [msg_bloqueio],
                    "next_agent": "support",
                    "authenticated_user_id": authenticated_user_id,
                }

        # Atendimento normal usando as ferramentas com o cliente autenticado
        custom_system_prompt = SYSTEM_PROMPT.format(
            user_id=authenticated_user_id,
            nome_cliente=client_data["nome"],
            contexto_temporal=get_system_clock_context(),
        )
        current_messages = [SystemMessage(content=custom_system_prompt)] + messages
        updated_messages = run_agent_with_tools(
            llm_with_tools=llm_with_tools,
            tools=SUPPORT_TOOLS,
            messages=current_messages,
            agent_name="support",
        )

        originated_human = state.get("originated_from_human_intent") or state.get("awaiting_escalation_subject")
        if originated_human and updated_messages:
            last_m = updated_messages[-1]
            if hasattr(last_m, "content") and last_m.content:
                last_m.content += (
                    "\n\n---\n"
                    "💡 *Espero ter ajudado com essas informações! Se mesmo assim você ainda preferir falar com um especialista humano sobre esse assunto, "
                    "basta me avisar que realizo sua transferência imediatamente.*"
                )

        return {
            "messages": updated_messages,
            "next_agent": "support",
            "authenticated_user_id": authenticated_user_id,
            "awaiting_escalation_subject": False,
            "originated_from_human_intent": True if originated_human else False,
            "had_self_service_attempt": True if originated_human else False,
        }

    # -----------------------------------------------------------------------
    # CENÁRIO 2: Sessão NÃO está autenticada ainda
    # -----------------------------------------------------------------------
    # Verifica se a mensagem atual do usuário contém um documento/ID válido
    busca = buscar_cliente_por_documento(last_user_message)

    if busca:
        # Documento encontrado com sucesso! Autentica a sessão.
        client_key, client_data = busca
        authenticated_user_id = client_key

        pergunta_a_responder = pending_query or last_user_message

        custom_system_prompt = SYSTEM_PROMPT.format(
            user_id=authenticated_user_id,
            nome_cliente=client_data["nome"],
            contexto_temporal=get_system_clock_context(),
        )

        # Determina a solicitação real do cliente (seja de turno anterior ou enviada junto com o documento)
        pergunta_a_responder = pending_query
        if not pergunta_a_responder:
            import re
            doc_padroes = r'\b(cliente\w*|cpf|cnpj|meu|o|meu\s+cpf\s+[ée]|id|c[óo]digo)\b|[\d\.\-\/\:\s]+'
            texto_limpo = re.sub(doc_padroes, ' ', last_user_message.lower()).strip()
            if len(texto_limpo) >= 2 and any(c.isalnum() for c in texto_limpo):
                pergunta_a_responder = last_user_message

        if pergunta_a_responder:
            prompt_confirmacao = (
                f"O cliente se identificou com sucesso com o documento ({client_data.get('cpf', 'N/A')}) - {client_data['nome']}.\n"
                f"Solicitação do cliente: '{pergunta_a_responder}'.\n"
                f"DIRETRIZ DE ATENDIMENTO:\n"
                f"1. Se a solicitação do cliente for ESPECÍFICA (ex: expressou que quer abrir chamado, pediu envio de bobinas, consultou erro/extrato ou relatou um sintoma claro como tela quebrada ou leitor inoperante): "
                f"chame IMEDIATAMENTE a ferramenta apropriada (`abrir_chamado_suporte`, `consultar_transacoes_e_erros`, `consultar_vendas_e_liquidacao` ou `consultar_status_maquininhas`) e entregue o resultado completo.\n"
                f"2. Se o relato for VAGO / GENÉRICO (ex: apenas disse 'estou com problema' sem especificar o que houve ou sem pedir ação direta): "
                f"não abra chamados presuntivos; acolha a identificação e faça uma pergunta breve de qualificação para descobrir o defeito exato antes de registrar o chamado."
            )
        else:
            prompt_confirmacao = (
                f"O cliente acabou de se identificar com sucesso com o documento ({client_data.get('cpf', 'N/A')}) - {client_data['nome']}.\n"
                f"Como o cliente apenas informou o documento sem ter feito uma solicitação prévia, confirme educadamente a identificação dele e pergunte como pode ajudá-lo hoje."
            )

        current_messages = [
            SystemMessage(content=custom_system_prompt),
            HumanMessage(content=prompt_confirmacao),
        ]
        updated_messages = run_agent_with_tools(
            llm_with_tools=llm_with_tools,
            tools=SUPPORT_TOOLS,
            messages=current_messages,
            agent_name="support",
        )

        originated_human = state.get("originated_from_human_intent") or state.get("awaiting_escalation_subject")
        if originated_human and updated_messages:
            last_m = updated_messages[-1]
            if hasattr(last_m, "content") and last_m.content:
                last_m.content += (
                    "\n\n---\n"
                    "💡 *Consegui consultar esses dados para você! Se isso responder sua dúvida, você já tem a informação sem precisar aguardar na fila de transferência.*  \n"
                    "*Caso ainda prefira falar com um especialista humano sobre esse assunto, basta me avisar que realizo sua transferência imediatamente.*"
                )

        return {
            "messages": updated_messages,
            "next_agent": "support",
            "authenticated_user_id": authenticated_user_id,
            "awaiting_identification": False,
            "pending_support_query": None,
            "awaiting_escalation_subject": False,
            "originated_from_human_intent": True if originated_human else False,
            "had_self_service_attempt": True if originated_human else False,
        }

    # Se NÃO encontrou o cliente e já estava aguardando identificação:
    if awaiting_identification:
        msg_erro = AIMessage(
            content=(
                f"❌ **Documento não localizado:**\n\n"
                f"Não encontramos nenhum cadastro ativo com o documento/identificador informado (`{last_user_message}`).\n\n"
                f"Por favor, verifique os dados e digite novamente seu **documento (CPF/CNPJ ou código de identificação)** para podermos acessar seu atendimento com segurança."
            ),
            name="support",
        )
        return {
            "messages": [msg_erro],
            "next_agent": "support",
            "authenticated_user_id": None,
            "awaiting_identification": True,
            "pending_support_query": pending_query or last_user_message,
        }

    # Primeira vez ou nova pergunta sem fornecer documento:
    last_text_lower = (last_user_message or "").lower()
    if any(k in last_text_lower for k in ["abrir chamado", "abram um chamado", "abrir ticket", "ordem de serviço", "visita técnica", "enviem bobinas", "troca de máquina", "trocar"]):
        contexto_acolhimento = "Posso registrar a abertura da sua solicitação agora mesmo!\n\n"
    elif any(k in last_text_lower for k in ["venda", "ontem", "depósito", "deposito", "extrato", "saldo", "dinheiro", "liquidação", "liquidacao"]):
        contexto_acolhimento = "Para consultar seus lançamentos financeiros e previsão de depósito com total segurança,\n\n"
    else:
        contexto_acolhimento = "Para acessar suas informações e atender sua solicitação com total segurança,\n\n"

    msg_solicitacao = AIMessage(
        content=(
            f"{contexto_acolhimento}"
            "Por favor informe seu **documento (CPF, CNPJ ou código de cliente)**:"
        ),
        name="support",
    )
    return {
        "messages": [msg_solicitacao],
        "next_agent": "support",
        "authenticated_user_id": None,
        "awaiting_identification": True,
        "pending_support_query": last_user_message,
    }
