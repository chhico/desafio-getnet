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
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.support_tools import (
    SUPPORT_TOOLS,
    _CLIENT_DATABASE,
    buscar_cliente_por_documento,
)

llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(SUPPORT_TOOLS)

SYSTEM_PROMPT = """Você é o Agente de Suporte ao Cliente (Customer Support Agent) da Getnet.

Seu foco é resolver problemas e dúvidas personalizadas de clientes credenciados.
Você está atendendo o cliente autenticado: {user_id} - {nome_cliente}.

Ferramentas disponíveis:
1. `consultar_vendas_e_liquidacao`: use para responder sobre previsão de depósito de vendas de ontem, saldo a receber e dados bancários cadastrados.
2. `consultar_status_maquininhas`: use quando o cliente relatar problemas de conexão na maquininha, verificar modelos vinculados e sinal de rede.
3. `consultar_transacoes_e_erros`: use quando o cliente relatar transação recusada ou erros no terminal (ex: erro 51, erro 05, erro 96).
4. `abrir_chamado_suporte`: use para registrar chamado técnico formal quando necessário.

DIRETRIZES DE SEGURANÇA E ISOLAMENTO DE DADOS:
- SEMPRE passe o identificador do cliente autenticado `{user_id}` nas ferramentas.
- Você só pode consultar e fornecer informações pertencentes a {nome_cliente} (ID: {user_id}).
- Se o usuário tentar consultar ou solicitar dados de OUTRO cliente, CPF ou CNPJ diferente de {user_id}, RECUSE CATEGORICAMENTE por questões de sigilo bancário e segurança da informação.
- Informe ao usuário que a sessão atual está vinculada exclusivamente ao cliente {nome_cliente} e oriente a iniciar uma 'Nova Conversa' caso precise consultar outra conta.
- Seja empático, claro e forneça os detalhes exatos (valores, datas, contas ou orientações técnicas de recusa).
"""


def support_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do Agente de Suporte ao Cliente com autenticação por documento e isolamento de sessão."""
    messages = state.get("messages", [])
    last_user_message = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
            last_user_message = m.content.strip()
            break

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
        response = llm_with_tools.invoke(current_messages)

        updated_messages = [response]
        current_messages.append(response)

        while hasattr(response, "tool_calls") and response.tool_calls:
            tool_results = ToolNode(SUPPORT_TOOLS).invoke({"messages": current_messages})
            tool_messages = tool_results["messages"]
            updated_messages.extend(tool_messages)
            current_messages.extend(tool_messages)
            response = llm_with_tools.invoke(current_messages)
            updated_messages.append(response)
            current_messages.append(response)

        response.name = "support"
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

        response = llm_with_tools.invoke(current_messages)
        updated_messages = [response]
        current_messages.append(response)

        while hasattr(response, "tool_calls") and response.tool_calls:
            tool_results = ToolNode(SUPPORT_TOOLS).invoke({"messages": current_messages})
            tool_messages = tool_results["messages"]
            updated_messages.extend(tool_messages)
            current_messages.extend(tool_messages)
            response = llm_with_tools.invoke(current_messages)
            updated_messages.append(response)
            current_messages.append(response)

        response.name = "support"
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
