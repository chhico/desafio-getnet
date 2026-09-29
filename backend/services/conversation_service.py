import time
from typing import Tuple, Optional
from langchain_core.messages import HumanMessage, AIMessage
from backend.domain.schemas import ChatResponse
from backend.core.config import settings
from backend.infrastructure.telemetry import telemetry_collector

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

        start_time = time.perf_counter()

        # Invoca o grafo passando user_id e a mensagem
        result = graph.invoke(
            {
                "user_id": user_id,
                "messages": [HumanMessage(content=message_content)],
            },
            config=config,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Extração da resposta textual final
        all_msgs = result.get("messages", [])
        ai_msg = next(
            (m.content for m in reversed(all_msgs) if isinstance(m, AIMessage) and m.content and str(m.content).strip()),
            "O agente processou sua solicitação, mas não retornou texto."
        )
        
        agent_used = result.get("next_agent", "unknown")
        category = result.get("category", "Geral")

        # Registrar telemetria em tempo real
        try:
            telemetry_collector.record_turn(
                agent_used=agent_used,
                latency_ms=latency_ms,
                is_safe=result.get("is_safe", True),
                guardrail_reason=result.get("guardrail_reason"),
                category=category
            )
        except Exception:
            pass

        # Extrai ferramentas utilizadas exclusivamente no turno atual
        last_human_idx = -1
        for i, m in enumerate(all_msgs):
            if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
                last_human_idx = i

        turn_msgs = all_msgs[last_human_idx:] if last_human_idx != -1 else all_msgs
        tools_used = []
        for m in turn_msgs:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    t_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if t_name and t_name not in tools_used:
                        tools_used.append(t_name)
            if getattr(m, "type", "") == "tool" and hasattr(m, "name") and m.name:
                if m.name not in tools_used:
                    tools_used.append(m.name)

        if not tools_used and result.get("tools_used"):
            tools_used = result.get("tools_used")

        return ChatResponse(
            response=ai_msg,
            agent_used=agent_used,
            category=category,
            tools_used=tools_used,
        )

