"""
agents/knowledge_agent.py
-------------------------
Agente 2 — Agente de Conhecimento (Knowledge Agent).
Processa consultas que exigem recuperação de informações da Getnet via RAG
e utiliza busca web externa para perguntas de uso geral.
"""

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from backend.agents.state import SupportState
from backend.core.config import settings
from backend.agents.tools.knowledge_tools import KNOWLEDGE_TOOLS

llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY,
)
llm_with_tools = llm.bind_tools(KNOWLEDGE_TOOLS)

SYSTEM_PROMPT = """Você é o Agente de Conhecimento (Knowledge Agent) oficial da Getnet.

Sua missão é fornecer respostas precisas, profissionais e completas para o usuário.

Ferramentas disponíveis:
1. `consultar_base_getnet`: use SEMPRE que a pergunta for sobre produtos Getnet (Get Clássica, Get Smart, Get Mini), taxas, regras de Pix, antecipação de recebíveis, crediário, links de pagamento, documentações ou procedimentos da empresa.
2. `pesquisar_web`: use para perguntas de uso geral fora do catálogo da Getnet, como previsão do tempo, cotações de moedas (ex: euro, dólar), notícias externas ou fatos dinâmicos.

Diretrizes Críticas:
- SEMPRE utilize uma ferramenta antes de formular a resposta final.
- Se a pergunta envolver a Getnet, priorize a base interna `consultar_base_getnet`.
- Se a pergunta for externa/geral, use `pesquisar_web`.
- Seja direto, cortês e coeso. Nunca invente dados técnicos ou taxas.

OBRIGATÓRIO — IDENTIFICAÇÃO E CITAÇÃO DAS FONTES:
- Sempre que você utilizar informações recuperadas pelas ferramentas (`consultar_base_getnet` ou `pesquisar_web`), você DEVE OBRIGATORIAMENTE indicar ao final da resposta a(s) fonte(s) onde a resposta foi encontrada.
- Especifique claramente se a fonte é um Arquivo físico local ou uma URL web.
- Formate a seção de fontes exatamente no final da sua mensagem com o seguinte padrão:

---
📌 **Fontes consultadas:**
- 📄 Arquivo: `<nome_do_arquivo>` (ex: `Perguntas Frequentes (FAQ).txt`, `Procedimento de Onboarding de Novos Clientes.pdf`)
- 🌐 URL: `<url_completa>` (ex: `https://www.getnet.net/pt/...`)

(Atenção: cite apenas as fontes reais que de fato fundamentaram a resposta dada. Não invente arquivos ou URLs que não constam no retorno das ferramentas).
"""


def knowledge_node(state: SupportState, config: RunnableConfig) -> dict:
    """Nó do Agente de Conhecimento."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    updated_messages = [response]
    current_messages = messages + [response]

    while hasattr(response, "tool_calls") and response.tool_calls:
        tool_results = ToolNode(KNOWLEDGE_TOOLS).invoke({"messages": current_messages})
        tool_messages = tool_results["messages"]
        updated_messages.extend(tool_messages)
        current_messages.extend(tool_messages)
        response = llm_with_tools.invoke(current_messages)
        updated_messages.append(response)
        current_messages.append(response)

    response.name = "knowledge"
    return {
        "messages": updated_messages,
        "next_agent": "knowledge",
    }
