"""
tests/conftest.py
-----------------
Fixtures centrais e configurações globais para a suíte de testes do Desafio Getnet.
Padroniza o isolamento de sessões, chamadas ao grafo e relatórios executivos de execução (Markdown e JSON).
"""

import pytest
import uuid
import time
import re
from typing import Callable, Dict, Any, List
from backend.agents.graph import support_graph
from backend.services.conversation_service import ConversationService
from backend.domain.schemas import ChatResponse
from tests.reporters.dossier_generator import dossier_generator

# Registro em memória para consolidar telemetria dos testes da sessão
_CURRENT_TEST_CONTEXT: Dict[str, Any] = {}


@pytest.fixture
def run_message(request) -> Callable[..., ChatResponse]:
    """
    Fixture padrão unificada para envio de mensagens ao ConversationService.
    Garante canal 'test', gera thread_id único e captura telemetria para o relatório executivo.
    """
    def _execute(message: str, user_id: str = "cliente1988", thread_id: str = None, channel: str = "test") -> ChatResponse:
        final_thread = thread_id or f"test_session_{uuid.uuid4().hex[:8]}"
        res = ConversationService.process_message(
            graph=support_graph,
            user_id=user_id,
            message_content=message,
            thread_id=final_thread,
            channel=channel,
        )

        # Captura telemetria para o dossiê executivo
        item_nodeid = request.node.nodeid
        if item_nodeid not in _CURRENT_TEST_CONTEXT:
            _CURRENT_TEST_CONTEXT[item_nodeid] = {
                "responses": [],
                "agents": [],
                "tools": [],
                "category": None,
                "turns": [],
            }
        _CURRENT_TEST_CONTEXT[item_nodeid]["responses"].append(res)

        turn_entry = {
            "turn_index": len(_CURRENT_TEST_CONTEXT[item_nodeid]["turns"]) + 1,
            "user_message": message,
            "response": res.response,
            "agent_used": res.agent_used,
            "tools_used": res.tools_used or [],
            "category": res.category,
        }
        _CURRENT_TEST_CONTEXT[item_nodeid]["turns"].append(turn_entry)

        if res.agent_used and res.agent_used not in _CURRENT_TEST_CONTEXT[item_nodeid]["agents"]:
            _CURRENT_TEST_CONTEXT[item_nodeid]["agents"].append(res.agent_used)
        if res.tools_used:
            for t in res.tools_used:
                if t not in _CURRENT_TEST_CONTEXT[item_nodeid]["tools"]:
                    _CURRENT_TEST_CONTEXT[item_nodeid]["tools"].append(t)
        if res.category and not _CURRENT_TEST_CONTEXT[item_nodeid]["category"]:
            _CURRENT_TEST_CONTEXT[item_nodeid]["category"] = res.category

        return res
    return _execute


@pytest.fixture
def unique_thread_id() -> str:
    """Retorna um identificador de thread isolado e único."""
    return f"thread_{uuid.uuid4().hex[:10]}"


# ============================================================================
# HOOKS DO PYTEST PARA GERAÇÃO AUTOMÁTICA DO DOSSIÊ EXECUTIVO
# ============================================================================

def pytest_sessionstart(session):
    """Inicializa as variáveis de controle da sessão de testes."""
    session._dossier_start_time = time.time()
    session._dossier_results = []
    _CURRENT_TEST_CONTEXT.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Captura o status e duração de cada teste executado."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        raw_name = item.name
        doc = getattr(item.function, "__doc__", "") or ""
        doc_first_line = doc.strip().split("\n")[0] if doc else raw_name

        match_id = re.search(r'test_scenario_(\d+)', raw_name)
        case_id = match_id.group(1) if match_id else raw_name.replace("test_", "")

        ctx = _CURRENT_TEST_CONTEXT.get(item.nodeid, {})
        agents = ctx.get("agents", [])
        tools = ctx.get("tools", [])
        category = ctx.get("category")
        turns_list = ctx.get("turns", [])
        turns_count = len(turns_list) or 1

        if not category:
            name_lower = raw_name.lower()
            if any(k in name_lower for k in ["guardrail", "seguranca", "bloqueio", "sql", "injection", "fraude"]):
                category = "Segurança"
            elif any(k in name_lower for k in ["escalation", "humano", "handoff", "retencao", "procon"]):
                category = "Human Handoff"
            elif any(k in name_lower for k in ["suporte", "transacao", "deposito", "extrato", "maquininha", "recusa", "chamado"]):
                category = "Suporte"
            else:
                category = "Conhecimento"

        status = "SUCCESS" if report.passed else "FAIL"
        duration_ms = report.duration * 1000.0

        errors = []
        if report.failed and report.longrepr:
            errors.append(str(report.longrepr))

        item.session._dossier_results.append({
            "case_id": case_id,
            "id": case_id,
            "name": doc_first_line or raw_name,
            "category": category,
            "status": status,
            "duration_ms": duration_ms,
            "total_turns": turns_count,
            "turns": turns_list,
            "all_agents_used": agents or ["-"],
            "all_executed_tools": tools,
            "error_reasons": errors,
        })


def pytest_sessionfinish(session, exitstatus):
    """Ao finalizar a execução dos testes, consolida e grava os relatórios Markdown e JSON."""
    results = getattr(session, "_dossier_results", [])
    if not results:
        return

    total_duration_s = time.time() - getattr(session, "_dossier_start_time", time.time())

    args_str = " ".join(getattr(session.config, "args", []))
    if "test_01_edital" in args_str or "test_scenarios" in args_str:
        suite_name = "edital_scenarios"
    elif "test_02_agents" in args_str:
        suite_name = "agents_unit"
    elif "test_03_tools" in args_str:
        suite_name = "tools_internal"
    elif "test_support_ticket" in args_str:
        suite_name = "support_tickets"
    else:
        suite_name = "pytest_suite"

    paths = dossier_generator.generate_dossier(
        suite_name=suite_name,
        results=results,
        total_duration_s=total_duration_s,
    )

    # Imprime no terminal o link direto para os relatórios criados
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    msg = (
        f"\n{'=' * 80}\n"
        f"📑 DOSSIÊ EXECUTIVO DE QUALIDADE & EVALS GERADO COM SUCESSO!\n"
        f"• Casos Executados:  {len(results)}\n"
        f"• Aprovações:        ✅ {sum(1 for r in results if r.get('status') == 'SUCCESS')}/{len(results)}\n"
        f"• Tempo Total:       {total_duration_s:.2f}s\n"
        f"\n"
        f"📄 Relatório Markdown: {paths['latest_md']}\n"
        f"📊 Relatório JSON:     {paths['latest_json']}\n"
        f"{'=' * 80}\n"
    )
    if tr:
        tr.write_line(msg)
    else:
        print(msg)

