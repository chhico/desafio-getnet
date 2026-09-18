from typing import Tuple, Optional
from langchain_core.messages import HumanMessage, AIMessage
from backend.domain.schemas import ChatResponse
from backend.core.config import settings

class ConversationService:
    @staticmethod
    def process_message(graph, user_id: str, message_content: str, thread_id: Optional[str] = None, channel: Optional[str] = None) -> ChatResponse:
        """
        Organiza o ID da sessão, repassa user_id e message_content e invoca o grafo.
        """
        session_thread = thread_id or user_id
        final_thread_id = f"{channel or 'web'}_{session_thread}"

        config = {
            "configurable": {"thread_id": final_thread_id},
            "recursion_limit": settings.AGENT_MAX_ITERATIONS,
        }

        # Invoca o grafo passando user_id e a mensagem
        result = graph.invoke(
            {
                "user_id": user_id,
                "messages": [HumanMessage(content=message_content)],
            },
            config=config,
        )

        # Extração da resposta textual final
        all_msgs = result.get("messages", [])
        ai_msg = next(
            (m.content for m in reversed(all_msgs) if isinstance(m, AIMessage)), 
            "O agente processou sua solicitação, mas não retornou texto."
        )
        
        agent_used = result.get("next_agent", "unknown")
        category = result.get("category", "Geral")

        return ChatResponse(response=ai_msg, agent_used=agent_used, category=category)
