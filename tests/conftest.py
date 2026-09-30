"""
tests/conftest.py
-----------------
Fixtures centrais e configurações globais para a suíte de testes do Desafio Getnet.
Padroniza o isolamento de sessões, chamadas ao grafo e relatórios de execução.
"""

import pytest
import uuid
import time
from typing import Callable
from backend.agents.graph import support_graph
from backend.services.conversation_service import ConversationService
from backend.domain.schemas import ChatResponse


@pytest.fixture
def run_message() -> Callable[..., ChatResponse]:
    """
    Fixture padrão unificada para envio de mensagens ao ConversationService.
    Garante canal 'test' e gera thread_id único caso não fornecido.
    """
    def _execute(message: str, user_id: str = "cliente1988", thread_id: str = None, channel: str = "test") -> ChatResponse:
        final_thread = thread_id or f"test_session_{uuid.uuid4().hex[:8]}"
        return ConversationService.process_message(
            graph=support_graph,
            user_id=user_id,
            message_content=message,
            thread_id=final_thread,
            channel=channel,
        )
    return _execute


@pytest.fixture
def unique_thread_id() -> str:
    """Retorna um identificador de thread isolado e único."""
    return f"thread_{uuid.uuid4().hex[:10]}"
