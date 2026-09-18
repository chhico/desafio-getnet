"""
agents/support_agent.py
-----------------------
Agente 3 — Agente de Suporte ao Cliente (Customer Support Agent).
Oferece suporte ao cliente recuperando dados relevantes do usuário (user_id)
para resolver solicitações financeiras, operacionais e técnicas de maquininhas.
"""

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.support_tools import SUPPORT_TOOLS

llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(SUPPORT_TOOLS)

SYSTEM_PROMPT = """Você é o Agente de Suporte ao Cliente (Customer Support Agent) da Getnet.

Seu foco é resolver problemas e dúvidas personalizadas de clientes credenciados.
Você tem acesso ao identificador do cliente atual: {user_id}.

Ferramentas disponíveis:
1. `consultar_vendas_e_liquidacao`: use para responder sobre previsão de depósito de vendas de ontem, saldo a receber e dados bancários cadastrados.
2. `consultar_status_maquininhas`: use quando o cliente relatar problemas de conexão na maquininha, verificar modelos vinculados e sinal de rede.
3. `consultar_transacoes_e_erros`: use quando o cliente relatar transação recusada ou erros no terminal (ex: erro 51).
4. `abrir_chamado_suporte`: use para registrar chamado técnico formal quando necessário.

Diretrizes:
- SEMPRE passe o identificador do cliente `{user_id}` nas ferramentas.
- Seja empático, claro e forneça os detalhes exatos (valores, datas, contas ou orientações técnicas de recusa).
"""


def support_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do Agente de Suporte ao Cliente."""
    user_id = state.get("user_id", "cliente1988")
    custom_system_prompt = SYSTEM_PROMPT.format(user_id=user_id)

    messages = [SystemMessage(content=custom_system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    updated_messages = [response]
    current_messages = messages + [response]

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
    }
