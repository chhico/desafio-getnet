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
from backend.agents.agent_utils import run_agent_with_tools
from backend.agents.tools.support_tools import (
    SUPPORT_TOOLS,
    _CLIENT_DATABASE,
    buscar_cliente_por_documento,
)
from backend.core.llm_factory import get_agent_llm

llm = get_agent_llm(temperature=0)
llm_with_tools = llm.bind_tools(SUPPORT_TOOLS)

SYSTEM_PROMPT = """Você é o Agente de Suporte ao Cliente (Customer Support Agent) da Getnet.

Seu foco é resolver problemas e dúvidas personalizadas de clientes credenciados.
Você está atendendo o cliente autenticado: {user_id} - {nome_cliente}.

Ferramentas disponíveis:
1. `consultar_vendas_e_liquidacao`: use para consultar o extrato financeiro, histórico de vendas por data ou geral, saldo a receber e dados bancários cadastrados do cliente.
2. `consultar_status_maquininhas`: use para verificar modelos vinculados, número de série, status de conexão (online/offline) e sinal de rede.
3. `consultar_transacoes_e_erros`: use SEMPRE que o cliente perguntar por transações, seja por ID específico (ex: TXN-00000, TXN-99821), por status (aprovadas, recusadas) ou por data.
4. `consultar_chamados_suporte`: use SEMPRE que o cliente perguntar pelo status de chamados técnicos abertos anteriormente, protocolos de suporte, agendamento de visita técnica ou reagendamento de visita de manutenção.
5. `abrir_chamado_suporte`: use SEMPRE que o cliente solicitar expressamente abertura de chamado, pedido de reposição de bobinas de papel térmico para a maquininha, solicitação de troca de equipamento com defeito ou envio de suprimentos.

DIRETRIZES DE ATENDIMENTO E ISOLAMENTO DE DADOS:
- SEMPRE passe o identificador do cliente autenticado `{user_id}` nas ferramentas para consultar sua base de dados exclusiva em `_CLIENT_DATABASE`.
- Você só pode consultar e fornecer informações pertencentes a {nome_cliente} (ID: {user_id}). Quando o cliente pedir suas informações, envie apenas o que é seu.
- NUNCA presuma antecipadamente se uma transação, maquininha ou movimentação existe ou não. SEMPRE chame a respectiva ferramenta usando `{user_id}` para verificar se a informação está contida nos registros do cliente.
- Caso a ferramenta retorne que a informação específica (ex: ID de transação, data ou terminal) não foi encontrada, informe de forma clara e amigável ao cliente que aquele registro específico não foi localizado para o seu cadastro.
- Se o usuário tentar consultar ou solicitar dados explicitamente de OUTRO cliente, CPF ou CNPJ diferente de {user_id}, RECUSE CATEGORICAMENTE por questões de sigilo bancário e segurança da informação, orientando a iniciar uma 'Nova Conversa'.
- Seja empático, claro e forneça os detalhes exatos (valores, datas, contas ou orientações técnicas de recusa).
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
        )
        current_messages = [SystemMessage(content=custom_system_prompt)] + messages
        updated_messages = run_agent_with_tools(
            llm_with_tools=llm_with_tools,
            tools=SUPPORT_TOOLS,
            messages=current_messages,
            agent_name="support",
        )
        return {
            "messages": updated_messages,
            "next_agent": "support",
            "authenticated_user_id": authenticated_user_id,
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
        )

        prompt_confirmacao = (
            f"O cliente acabou de se identificar com sucesso com o documento/identificador ({client_data.get('cpf', 'N/A')}). "
            f"Nome do cliente cadastrado: {client_data['nome']}. "
            f"Confirme brevemente a identificação e responda com precisão à seguinte solicitação: '{pergunta_a_responder}'."
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
        return {
            "messages": updated_messages,
            "next_agent": "support",
            "authenticated_user_id": authenticated_user_id,
            "awaiting_identification": False,
            "pending_support_query": None,
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
    msg_solicitacao = AIMessage(
        content=(
            "Olá! Para consultar as informações da sua conta, extratos financeiros ou suporte às suas maquininhas, "
            "preciso confirmar sua identidade por motivos de segurança.\n\n"
            "Por favor, informe seu **documento (CPF ou código de cliente)**:"
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
