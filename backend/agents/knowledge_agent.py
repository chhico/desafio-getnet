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
