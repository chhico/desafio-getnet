import time
import re
from typing import Tuple, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from backend.domain.schemas import ChatResponse, HarnessTrace
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

        # Extrai ferramentas utilizadas exclusivamente no turno atual
        last_human_idx = -1
        for i, m in enumerate(all_msgs):
            if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
                last_human_idx = i

        turn_msgs = all_msgs[last_human_idx:] if last_human_idx != -1 else all_msgs
        tools_used = []
        tool_calls_details = []
        for m in turn_msgs:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    t_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    t_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                    if t_name and t_name not in tools_used:
                        tools_used.append(t_name)
                    if t_name:
                        tool_calls_details.append({"tool": t_name, "args": t_args})
            if getattr(m, "type", "") == "tool" and hasattr(m, "name") and m.name:
                if m.name not in tools_used:
                    tools_used.append(m.name)

        if not tools_used and result.get("tools_used"):
            tools_used = result.get("tools_used")

        # Rastreamento de nós percorridos no grafo
        is_fast_path = bool(result.get("fast_path_response"))
        if is_fast_path:
            nodes_visited = ["fast_path"]
        elif agent_used == "guardrail_block":
            nodes_visited = ["guardrail_node"]
        else:
            nodes_visited = ["guardrail_node", "orchestrator_node", f"{agent_used}_node"]

        # Extração de tokens reais (OpenAI response_metadata) ou cálculo proporcional
        real_tokens = None
        for m in reversed(turn_msgs):
            if hasattr(m, "response_metadata") and isinstance(m.response_metadata, dict):
                tu = m.response_metadata.get("token_usage")
                if tu:
                    real_tokens = tu
                    break
            if hasattr(m, "usage_metadata") and isinstance(m.usage_metadata, dict):
                real_tokens = m.usage_metadata
                break

        prompt_len = len(message_content)
        resp_len = len(ai_msg)
        if real_tokens:
            prompt_tokens = real_tokens.get("prompt_tokens") or real_tokens.get("input_tokens") or 0
            completion_tokens = real_tokens.get("completion_tokens") or real_tokens.get("output_tokens") or 0
            estimated_tokens = prompt_tokens + completion_tokens
            estimated_cost_usd = round((prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060), 6)
        else:
            prompt_tokens = int(prompt_len / 3.2) + 280
            completion_tokens = int(resp_len / 3.2)
            estimated_tokens = prompt_tokens + completion_tokens
            estimated_cost_usd = round((prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060), 6)

        # Detecção inteligente de mutação de estado (escrita) vs leitura pura
        mutation_tools = {"abrir_chamado_suporte"}
        executed_tools_set = set(tools_used) | {tc.get("tool") for tc in tool_calls_details if isinstance(tc, dict)}
        has_mutation = bool(executed_tools_set.intersection(mutation_tools)) or (agent_used == "escalation" and bool(result.get("ticket_protocol")))

        mutation_details = None
        if has_mutation:
            mutation_details = "Registro de chamado inserido com sucesso na base SQLite local (Contido em Sandbox)"

        # Extrai protocolo de chamado (seja gerado por abrir_chamado_suporte ou por transbordo humano)
        protocol = result.get("ticket_protocol")
        if not protocol:
            for m in reversed(turn_msgs):
                content = getattr(m, "content", "")
                if isinstance(content, str):
                    match = re.search(r"\b(GET-\d{4,8}|GET-2026-\d{4})\b", content, re.IGNORECASE)
                    if match:
                        protocol = match.group(1).upper()
                        break
            if not protocol:
                match = re.search(r"\b(GET-\d{4,8}|GET-2026-\d{4})\b", ai_msg, re.IGNORECASE)
                if match:
                    protocol = match.group(1).upper()

        # Registrar telemetria persistente e durável no SQLite
        try:
            telemetry_collector.record_turn(
                agent_used=agent_used,
                latency_ms=latency_ms,
                is_safe=result.get("is_safe", True),
                guardrail_reason=result.get("guardrail_reason"),
                category=category,
                protocol=protocol,
                thread_id=final_thread_id,
                user_id=user_id,
                message_text=message_content,
                response_text=ai_msg,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=estimated_cost_usd,
            )
        except Exception:
            pass

        # Snapshot 100% real das variáveis ativas no StateGraph (sem duplicar especialista do Pilar 1)
        state_snapshot = {}
        if result.get("authenticated_user_id"):
            state_snapshot["cliente_autenticado"] = result["authenticated_user_id"]
        if protocol:
            state_snapshot["protocolo_chamado"] = protocol
        if result.get("category"):
            state_snapshot["categoria_ativa"] = result["category"]
        if result.get("queue_target"):
            state_snapshot["fila_atendimento"] = result["queue_target"]
        if result.get("awaiting_identification"):
            state_snapshot["aguardando_documento"] = True
        if result.get("human_handoff_requested"):
            state_snapshot["transbordo_solicitado"] = True

        # Contagem analítica e categorizada de mensagens no buffer StateGraph
        human_messages_count = sum(1 for m in all_msgs if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human")
        tool_messages_count = sum(1 for m in all_msgs if isinstance(m, ToolMessage) or getattr(m, "type", "") == "tool")
        ai_messages_count = sum(1 for m in all_msgs if isinstance(m, AIMessage) or getattr(m, "type", "") == "ai")
        turn_count = max(1, human_messages_count)

        # Montagem do objeto de telemetria e inspeção do Harness
        trace = HarnessTrace(
            turn_count=turn_count,
            thread_id=final_thread_id,
            user_id=result.get("authenticated_user_id") or user_id,
            execution_mode="SANDBOX_SQLITE_LOCAL",
            side_effects_prevented=True,
            mutation_performed=has_mutation,
            mutation_details=mutation_details,
            authenticated=bool(result.get("authenticated_user_id")),
            nodes_visited=nodes_visited,
            tool_calls=tool_calls_details,
            latency_ms=round(latency_ms, 2),
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost_usd,
            guardrail_safe=result.get("is_safe", True),
            buffer_messages_count=len(all_msgs),
            human_messages_count=human_messages_count,
            ai_messages_count=ai_messages_count,
            tool_messages_count=tool_messages_count,
            agent_used=agent_used,
            tools_used=tools_used,
            state_snapshot=state_snapshot,
        )

        return ChatResponse(
            response=ai_msg,
            agent_used=agent_used,
            category=category,
            tools_used=tools_used,
            trace=trace,
        )

