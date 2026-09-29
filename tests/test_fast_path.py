"""
tests/test_fast_path.py
-----------------------
Bateria de testes unitários para o Tier 1 — Fast-Path (Opção A).
Garante respostas instantâneas (< 15ms) e determinísticas para interações de alta frequência:
- Saudações e Boas-Vindas
- Agradecimentos e Despedidas
- Confirmações Simples
- Canais de Atendimento (FAQ Estático)
- Não interceptação de perguntas de negócio, suporte, RAG ou escalonamento humano.
"""

import pytest
from backend.agents.fast_path import check_fast_path
from backend.agents.orchestrator import orchestrator_node
from backend.agents.state import SupportState
from langchain_core.messages import HumanMessage


class TestFastPathPatterns:
    """Testes dos padrões de regex e respostas do fast_path.py."""

    @pytest.mark.parametrize("msg", [
        "oi", "Oi", "OI!", "olá", "Ola", "olá getnet", "oie", "opa",
        "bom dia", "Bom dia!", "boa tarde", "boa noite",
        "olá, tudo bem?", "oi tudo bem", "e aí", "eae"
    ])
    def test_greetings(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer saudação: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Saudação / Apresentação"
        assert "Olá! Sou o assistente virtual da Getnet" in res["response"]
        assert "Maquininhas e Taxas" in res["response"]

    @pytest.mark.parametrize("msg", [
        "obrigado", "Obrigada!", "muito obrigado", "valeu", "vlw",
        "tchau", "até mais", "até logo", "valeu, até mais", "abraço"
    ])
    def test_thanks_and_closing(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer agradecimento: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Agradecimento / Encerramento"
        assert "Por nada!" in res["response"] or "agradece o seu contato" in res["response"]

    @pytest.mark.parametrize("msg", [
        "ok", "Ok.", "beleza", "blz", "entendi", "perfeito", "certo", "show de bola", "combinado"
    ])
    def test_confirmations(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer confirmação: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Confirmação"
        assert "Combinado!" in res["response"]

    @pytest.mark.parametrize("msg", [
        "qual o telefone da getnet", "qual é o telefone da getnet?",
        "sac getnet", "0800 getnet", "ouvidoria getnet",
        "qual o whatsapp da getnet", "como ligar na getnet"
    ])
    def test_channels_faq(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer canais: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Canais de Atendimento"
        assert "4002-4000" in res["response"]
        assert "0800-648-8000" in res["response"]
        assert "site.getnet.com.br" in res["response"]

    @pytest.mark.parametrize("msg", [
        "Qual é a diferença entre a Get Clássica e a Get Smart?",
        "Como funciona o Pix na maquininha?",
        "Quero consultar minhas vendas de ontem",
        "Minha maquininha está dando erro 99",
        "Quero falar com um atendente humano agora",
        "Preciso de suporte com um atendente",
        "123.456.789-00",
        "DROP TABLE usuarios;",
        "Qual a taxa de débito?",
    ])
    def test_negative_cases_should_not_trigger_fast_path(self, msg: str):
        """Perguntas conceituais, de suporte, escalonamento e segurança não devem ser interceptadas."""
        res = check_fast_path(msg)
        assert res is None, f"Mensagem não deveria acionar fast-path: '{msg}'"


class TestOrchestratorFastPathIntegration:
    """Testes de integração do Fast-Path dentro do orchestrator_node."""

    def test_orchestrator_routes_greeting_to_knowledge_fast_path(self):
        state: SupportState = {
            "user_id": "cliente_teste",
            "messages": [HumanMessage(content="oi")],
            "turn_count": 1,
            "next_agent": None,
            "routing_reason": None,
            "category": None,
            "authenticated_user_id": None,
            "awaiting_identification": False,
            "pending_support_query": None,
            "is_safe": True,
            "guardrail_reason": None,
            "human_handoff_requested": False,
            "ticket_protocol": None,
            "summary_for_human": None,
            "queue_target": None,
            "pending_escalation": False,
            "escalation_intent_retries": 0,
            "awaiting_escalation_subject": False,
            "originated_from_human_intent": False,
            "had_self_service_attempt": False,
            "tools_used": [],
            "fast_path_response": None,
        }

        output = orchestrator_node(state)
        assert output["next_agent"] == "knowledge"
        assert output["category"] == "Saudação / Apresentação"
        assert "fast_path_response" in output
        assert "Olá! Sou o assistente virtual da Getnet" in output["fast_path_response"]

    def test_orchestrator_preserves_escalation_subject_triaging(self):
        """Se o sistema estiver aguardando o assunto da triagem de escalonamento humano, 'ok' não deve desviar para fast-path."""
        state: SupportState = {
            "user_id": "cliente_teste",
            "messages": [HumanMessage(content="ok")],
            "turn_count": 2,
            "next_agent": None,
            "routing_reason": None,
            "category": None,
            "authenticated_user_id": None,
            "awaiting_identification": False,
            "pending_support_query": None,
            "is_safe": True,
            "guardrail_reason": None,
            "human_handoff_requested": True,
            "ticket_protocol": None,
            "summary_for_human": None,
            "queue_target": None,
            "pending_escalation": False,
            "escalation_intent_retries": 0,
            "awaiting_escalation_subject": True,
            "originated_from_human_intent": True,
            "had_self_service_attempt": False,
            "tools_used": [],
            "fast_path_response": None,
        }

        output = orchestrator_node(state)
        # Não pode ter sido capturado pelo fast-path
        assert output.get("fast_path_response") is None
