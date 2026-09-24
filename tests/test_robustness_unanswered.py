"""
tests/test_robustness_unanswered.py
-----------------------------------
Bateria de Testes Focada: Casos Não Respondidos pelo Agente de Conhecimento (RAG / Web).

Origem:
Extraído das rodadas anteriores de testes de robustez:
  - Bateria 1 (tests/reports/relatorio_testes_50.md): Casos #27, #28, #29, #32, #34
  - Bateria 2 (tests/reports/relatorio_testes_v2_50.md): Casos #76, #77, #80, #81, #83, #84, #87

Objetivo:
Avaliar se, após as atualizações no Crawler e indexação de novos conteúdos da Central de Ajuda Getnet,
o Agente de Conhecimento agora é capaz de responder com sucesso a essas 12 perguntas específicas,
superando a resposta padrão de ausência de informações ("Não consegui encontrar informações específicas sobre...").

CRITÉRIOS DE AVALIAÇÃO:
1. Validação Técnica (Tool & Agente):
   - Agente roteado: 'knowledge'
   - Execução de ferramenta RAG/Web ('consultar_base_local_getnet', 'consultar_base_web_getnet')
2. Resolução de Conhecimento (RAG Resolution):
   - Detecta se a resposta contém conteúdo substantivo ou se ainda recorreu ao fallback
     ("Não consegui encontrar informações específicas sobre...").

EXECUÇÃO MANUAL PELO TERMINAL:
  # Executar os 12 casos:
  python tests/test_robustness_unanswered.py

  # Modo verboso (exibe inputs e respostas no terminal):
  python tests/test_robustness_unanswered.py -v

  # Limitar quantidade de casos:
  python tests/test_robustness_unanswered.py --limit 3

RELATÓRIOS GERADOS:
  - tests/reports/relatorio_testes_unanswered.md
  - tests/reports/relatorio_testes_unanswered.json
"""

import sys
import os
import re
import json
import time
import argparse
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# Garante compatibilidade UTF-8 no stdout/stderr no Windows
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------------------------------------------------------------------------
# 1. Blindagem contra Execução Acidental no Pytest
# ---------------------------------------------------------------------------
if "pytest" in sys.modules:
    is_direct_run = any("test_robustness_unanswered.py" in arg for arg in sys.argv)
    if not is_direct_run:
        try:
            import pytest
            pytest.skip(
                "Bateria de testes de casos não respondidos (RAG). Execute diretamente via terminal: "
                "python tests/test_robustness_unanswered.py",
                allow_module_level=True,
            )
        except Exception:
            pass

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.graph import support_graph
from backend.services.conversation_service import ConversationService


# ---------------------------------------------------------------------------
# 2. Estrutura de Dados dos Casos de Teste
# ---------------------------------------------------------------------------
@dataclass
class Turn:
    """Representa um turno de conversação dentro de um cenário."""
    message: str
    user_id: str = "cliente1988"
    expected_agent: Optional[str] = None
    expected_tools: List[str] = field(default_factory=list)


@dataclass
class TestCase:
    """Definição de um caso de teste no catálogo."""
    id: int
    original_id: int
    original_suite: str         # "Bateria 1 (50)" | "Bateria 2 (v2 50)"
    category: str               # knowledge
    name: str                   # Nome sucinto do cenário
    description: str            # Objetivo técnico e de negócio
    input_message: str          # Mensagem do usuário
    user_id: str = "cliente1988"
    expected_agent: str = "knowledge"
    expected_tools: List[str] = field(default_factory=lambda: ["consultar_base_local_getnet", "consultar_base_web_getnet"])
    additional_turns: List[Turn] = field(default_factory=list)


@dataclass
class TurnResult:
    message: str
    agent_used: str
    tools_used: List[str]
    response: str
    duration_ms: float


@dataclass
class TestResult:
    """Resultado da execução e validação de conhecimento."""
    case_id: int
    original_id: int
    original_suite: str
    category: str
    name: str
    status: str                         # SUCCESS | FAIL (Critério técnico de roteamento/tools)
    knowledge_resolved: bool            # True se encontrou conteúdo, False se caiu no fallback negativo
    fallback_detected: Optional[str]    # Trecho da mensagem negativa detectada, se houver
    expected_agent: str
    actual_agent: str
    expected_tools: List[str]
    actual_tools: List[str]
    duration_ms: float
    error_reasons: List[str] = field(default_factory=list)
    input_message: str = ""
    final_response: str = ""
    final_response_snippet: str = ""
    turns: List[TurnResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Catálogo dos 12 Casos Não Respondidos (Foco em RAG / Base Getnet)
# ---------------------------------------------------------------------------
TEST_REGISTRY_UNANSWERED: List[TestCase] = [
    # =========================================================================
    # CASOS EXTRAÍDOS DA BATERIA 1 (test_robustness_50.py)
    # =========================================================================
    TestCase(
        id=1,
        original_id=27,
        original_suite="Bateria 1 (50)",
        category="knowledge",
        name="Regras e Parcelamento do Crediário Getnet",
        description="Dúvida sobre número máximo de parcelas e funcionamento do crediário.",
        input_message="Em quantas parcelas posso dividir uma venda usando o crediário da Getnet?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=2,
        original_id=28,
        original_suite="Bateria 1 (50)",
        category="knowledge",
        name="Antecipação de Recebíveis (Avulsa vs Automática)",
        description="Explicação de como solicitar antecipação de crédito e condições na Getnet.",
        input_message="Como funciona a antecipação de recebíveis com a Getnet e quais são os tipos?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=3,
        original_id=29,
        original_suite="Bateria 1 (50)",
        category="knowledge",
        name="Requisitos para Pix na Maquininha Getnet",
        description="Condições para recebimento de Pix e conta bancária necessária.",
        input_message="Preciso ter uma conta bancária específica para aceitar Pix na maquininha Getnet?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=4,
        original_id=32,
        original_suite="Bateria 1 (50)",
        category="knowledge",
        name="Prazos Oficiais de Liquidação (D+1, D+2, D+30)",
        description="Explicação das regras de repasse para modalidades de débito e crédito.",
        input_message="Quais são os prazos de recebimento padrão para vendas no débito e no crédito?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=5,
        original_id=34,
        original_suite="Bateria 1 (50)",
        category="knowledge",
        name="Tabela Geral de Taxas MDR Getnet",
        description="Dúvida de lojista sobre taxas aplicadas sobre transações de débito e crédito à vista.",
        input_message="Quais são as taxas médias praticadas pela Getnet no débito e crédito?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),

    # =========================================================================
    # CASOS EXTRAÍDOS DA BATERIA 2 (test_robustness_v2_50.py)
    # =========================================================================
    TestCase(
        id=6,
        original_id=76,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Bandeiras de Cartões Aceitas na Getnet",
        description="Consulta sobre aceitação de bandeiras nacionais e internacionais.",
        input_message="Quais são as bandeiras de cartão de crédito e débito aceitas nas maquininhas Getnet?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=7,
        original_id=77,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Pagamento por Aproximação (NFC / Contactless)",
        description="Orientações sobre pagamento por aproximação com cartão, celular ou relógio.",
        input_message="Como funciona o pagamento por aproximação NFC nas máquinas Getnet?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=8,
        original_id=80,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="App Getnet e Gestão de Vendas no Celular",
        description="Funcionalidades do aplicativo Getnet para acompanhar faturamento.",
        input_message="Quais recursos estão disponíveis no aplicativo Getnet para gerenciar as vendas pelo celular?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=9,
        original_id=81,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Conta Digital SuperGet / Gestão de Saldo",
        description="Como movimentar o dinheiro das vendas sem necessidade de conta bancária tradicional.",
        input_message="Como funciona a conta digital SuperGet para quem não tem conta em banco?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=10,
        original_id=83,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Regras sobre Taxa de Inatividade ou Mensalidade",
        description="Esclarecimento sobre cobrança ou isenção de aluguel por faixa de faturamento.",
        input_message="Existe cobrança de taxa de inatividade se eu ficar alguns dias sem vender na maquininha?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=11,
        original_id=84,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Recursos de Acessibilidade na Get Smart",
        description="Informações sobre recursos para pessoas com deficiência visual na tela touch.",
        input_message="A Get Smart possui recursos de acessibilidade para clientes com deficiência visual?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
    TestCase(
        id=12,
        original_id=87,
        original_suite="Bateria 2 (v2 50)",
        category="knowledge",
        name="Prazos de Liquidação no E-commerce Getnet",
        description="Dúvida sobre compensação de vendas realizadas pela internet e links.",
        input_message="Qual é o prazo de depósito para vendas realizadas pela loja virtual através da Getnet?",
        expected_agent="knowledge",
        expected_tools=["consultar_base_local_getnet", "consultar_base_web_getnet"],
    ),
]


# ---------------------------------------------------------------------------
# 4. Padrões para Detecção de Resposta Negativa (Ausência de Conhecimento)
# ---------------------------------------------------------------------------
NEGATIVE_KNOWLEDGE_PATTERNS = [
    r"não consegui encontrar informações específicas",
    r"não consegui encontrar informações",
    r"não foi possível encontrar",
    r"não encontrei informações específicas",
    r"não encontrei detalhes",
    r"não dispomos de informações",
    r"não há informações específicas",
    r"infelizmente, não consegui",
    r"não tenho informações sobre",
]


def detect_negative_fallback(response_text: str) -> Optional[str]:
    """Verifica se a resposta do modelo indica que não foi possível responder."""
    if not response_text:
        return "Resposta vazia"
    for pattern in NEGATIVE_KNOWLEDGE_PATTERNS:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


# ---------------------------------------------------------------------------
# 5. Mecanismo de Execução e Verificação
# ---------------------------------------------------------------------------
def execute_case(test_case: TestCase, thread_prefix: str = "unanswered_test") -> TestResult:
    """
    Executa o caso de teste no grafo LangGraph e valida se a resposta possui conteúdo informativo.
    """
    thread_id = f"{thread_prefix}_{test_case.id}_{int(time.time() * 1000)}"
    error_reasons: List[str] = []
    turn_results: List[TurnResult] = []
    total_duration_ms = 0.0

    t0 = time.time()
    try:
        res = ConversationService.process_message(
            graph=support_graph,
            user_id=test_case.user_id,
            message_content=test_case.input_message,
            thread_id=thread_id,
            channel="test_suite_unanswered",
        )
        t_dur = (time.time() - t0) * 1000.0
        total_duration_ms += t_dur

        actual_agent = res.agent_used or "unknown"
        actual_tools = res.tools_used or []
        resp_text = res.response or ""

        turn_results.append(
            TurnResult(
                message=test_case.input_message,
                agent_used=actual_agent,
                tools_used=actual_tools,
                response=resp_text,
                duration_ms=t_dur,
            )
        )

        for turn in test_case.additional_turns:
            t_sub0 = time.time()
            res_turn = ConversationService.process_message(
                graph=support_graph,
                user_id=turn.user_id,
                message_content=turn.message,
                thread_id=thread_id,
                channel="test_suite_unanswered",
            )
            t_sub_dur = (time.time() - t_sub0) * 1000.0
            total_duration_ms += t_sub_dur

            turn_results.append(
                TurnResult(
                    message=turn.message,
                    agent_used=res_turn.agent_used or "unknown",
                    tools_used=res_turn.tools_used or [],
                    response=res_turn.response or "",
                    duration_ms=t_sub_dur,
                )
            )
            actual_agent = res_turn.agent_used or "unknown"
            resp_text = res_turn.response or ""

    except Exception as e:
        actual_agent = "error"
        actual_tools = []
        resp_text = f"Exceção durante execução: {str(e)}"
        error_reasons.append(f"Exceção não tratada: {str(e)}")

    all_executed_tools = []
    for tr in turn_results:
        for t in tr.tools_used:
            if t not in all_executed_tools:
                all_executed_tools.append(t)

    # 1. Validações Técnicas
    if test_case.expected_agent:
        exp_agents = [a.strip() for a in test_case.expected_agent.split(",")]
        if actual_agent not in exp_agents:
            error_reasons.append(
                f"Agente divergente: esperado '{test_case.expected_agent}', obtido '{actual_agent}'"
            )

    if test_case.expected_tools:
        matched_tool = any(t in all_executed_tools for t in test_case.expected_tools)
        if not matched_tool:
            error_reasons.append(
                f"Nenhuma ferramenta esperada ({test_case.expected_tools}) foi executada. Obtidas: {all_executed_tools or 'Nenhuma'}"
            )

    if not resp_text or not resp_text.strip():
        error_reasons.append("Resposta do agente retornou vazia.")
    elif "Exceção durante execução:" in resp_text:
        error_reasons.append("Ocorreu uma exceção de execução não tratada.")

    status = "SUCCESS" if len(error_reasons) == 0 else "FAIL"

    # 2. Avaliação de Resolução de Conteúdo no RAG
    fallback_match = detect_negative_fallback(resp_text)
    knowledge_resolved = (fallback_match is None) and (status == "SUCCESS")

    snippet = resp_text.replace("\n", " ")[:160] + "..." if len(resp_text) > 160 else resp_text.replace("\n", " ")

    return TestResult(
        case_id=test_case.id,
        original_id=test_case.original_id,
        original_suite=test_case.original_suite,
        category=test_case.category,
        name=test_case.name,
        status=status,
        knowledge_resolved=knowledge_resolved,
        fallback_detected=fallback_match,
        expected_agent=test_case.expected_agent,
        actual_agent=actual_agent,
        expected_tools=test_case.expected_tools,
        actual_tools=all_executed_tools,
        duration_ms=round(total_duration_ms, 2),
        error_reasons=error_reasons,
        input_message=test_case.input_message,
        final_response=resp_text,
        final_response_snippet=snippet,
        turns=turn_results,
    )


# ---------------------------------------------------------------------------
# 6. Gerador de Relatórios (Markdown e JSON)
# ---------------------------------------------------------------------------
def generate_reports(
    results: List[TestResult],
    catalog_cases: List[TestCase],
    output_dir: str,
) -> Dict[str, str]:
    """Gera relatórios estruturados de auditoria para os 12 casos."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_executed = len(results)
    technical_success = sum(1 for r in results if r.status == "SUCCESS")
    resolved_count = sum(1 for r in results if r.knowledge_resolved)
    unresolved_count = total_executed - resolved_count
    resolution_rate = (resolved_count / total_executed * 100.0) if total_executed > 0 else 0.0
    total_time_s = sum(r.duration_ms for r in results) / 1000.0

    # 1. JSON
    json_path = os.path.join(output_dir, "relatorio_testes_unanswered.json")
    json_data = {
        "metadata": {
            "suite_name": "Bateria de Casos Não Respondidos (Foco RAG / Base Getnet)",
            "timestamp": timestamp,
            "total_cases": len(catalog_cases),
            "total_executed": total_executed,
            "technical_success_count": technical_success,
            "knowledge_resolved_count": resolved_count,
            "knowledge_unresolved_count": unresolved_count,
            "resolution_rate": round(resolution_rate, 2),
            "total_time_seconds": round(total_time_s, 2),
        },
        "results": [asdict(r) for r in results],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # 2. Markdown
    md_path = os.path.join(output_dir, "relatorio_testes_unanswered.md")
    lines = []
    lines.append("# 📋 Relatório de Execução — Casos Não Respondidos pelo RAG\n")
    lines.append(f"**Data da Execução:** {timestamp}  ")
    lines.append(f"**Duração Total:** {total_time_s:.2f}s  ")
    lines.append(f"**Status de Resolução RAG:** {resolved_count}/{total_executed} resolvidos ({resolution_rate:.1f}%)\n")

    lines.append("## 1. Sumário Executivo\n")
    lines.append("| Métrica | Valor |")
    lines.append("| :--- | :--- |")
    lines.append(f"| **Total de Casos no Catálogo** | {len(catalog_cases)} |")
    lines.append(f"| **Casos Executados** | {total_executed} |")
    lines.append(f"| **Conhecimento Respondido com Sucesso** | {'🟢 ' + str(resolved_count)} |")
    lines.append(f"| **Ainda Não Respondidos (Fallback Negativo)** | {'⚠️ ' + str(unresolved_count) if unresolved_count > 0 else '0'} |")
    lines.append(f"| **Taxa de Resolução de Conhecimento** | **{resolution_rate:.1f}%** |")
    lines.append(f"| **Sucesso Técnico (Roteamento + Tools)** | {technical_success}/{total_executed} |")
    lines.append(f"| **Tempo Médio por Pergunta** | {(total_time_s / total_executed * 1000):.1f}ms |\n")

    lines.append("## 2. Tabela Comparativa de Resolução de Conhecimento\n")
    lines.append("| ID | Origem | Cenário | Tools Usadas | Resolução RAG | Latência |")
    lines.append("| :-: | :---: | :--- | :--- | :---: | -: |")

    for r in results:
        res_badge = "🟢 RESOLVIDO" if r.knowledge_resolved else f"⚠️ FALLBACK ({r.fallback_detected or 'Não encontrado'})"
        tools_str = ", ".join(r.actual_tools) if r.actual_tools else "-"
        lines.append(
            f"| `#{r.case_id:02d}` | Caso #{r.original_id} ({r.original_suite}) | {r.name} | "
            f"`{tools_str}` | **{res_badge}** | {r.duration_ms:.0f}ms |"
        )
    lines.append("\n")

    lines.append("## 3. Dossiê Completo de Auditoria (Input vs Output)\n")
    lines.append("Abaixo constam na íntegra as perguntas enviadas e as respostas emitidas pelo agente:\n")

    for r in results:
        res_badge = "🟢 CONHECIMENTO ENCONTRADO" if r.knowledge_resolved else "⚠️ FALLBACK: INFORMAÇÃO NÃO ENCONTRADA"
        lines.append(f"### 💬 Caso #{r.case_id:02d} (Original #{r.original_id} — {r.original_suite}): {r.name}\n")
        lines.append(f"- **Status de Conteúdo:** {res_badge}")
        lines.append(f"- **Agente:** Esperado `{r.expected_agent}` | Obtido `{r.actual_agent}`")
        lines.append(f"- **Tools Executadas:** `{', '.join(r.actual_tools) or 'Nenhuma'}`")
        lines.append(f"- **Latência:** {r.duration_ms:.0f}ms\n")

        for t_idx, tr in enumerate(r.turns, 1):
            turn_label = f" (Turno {t_idx})" if len(r.turns) > 1 else ""
            lines.append(f"**📥 Pergunta Enviada{turn_label}:**")
            lines.append(f"> {tr.message}\n")
            lines.append(f"**📤 Resposta do Agente{turn_label}:**")
            resp_lines = tr.response.strip().split("\n")
            quoted_resp = "\n".join(f"> {line}" for line in resp_lines)
            lines.append(f"{quoted_resp}\n")
        lines.append("---\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"md": md_path, "json": json_path}


# ---------------------------------------------------------------------------
# 7. CLI Runner Principal
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Runner dos 12 Casos Não Respondidos pelo RAG/Agente de Conhecimento."
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=None,
        help="Limitar o número máximo de casos a executar.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=os.path.join(PROJECT_ROOT, "tests", "reports"),
        help="Diretório onde os relatórios Markdown e JSON serão salvos.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Exibir inputs e respostas completas no console durante a execução.",
    )

    args = parser.parse_args()

    cases_to_run = list(TEST_REGISTRY_UNANSWERED)
    if args.limit and args.limit > 0:
        cases_to_run = cases_to_run[:args.limit]

    print("\n" + "=" * 80)
    print(f"🎯 INICIANDO BATERIA DE CASOS NÃO RESPONDIDOS ({len(cases_to_run)} Casos Selecionados)")
    print("• Origem: Casos #27, #28, #29, #32, #34 (Bateria 1) e #76, #77, #80, #81, #83, #84, #87 (Bateria 2)")
    print("• Objetivo: Verificar se a indexação RAG atualizada solucionou as lacunas de informação")
    print("=" * 80 + "\n")

    results: List[TestResult] = []
    t_suite_start = time.time()

    for idx, case in enumerate(cases_to_run, 1):
        print(f"[{idx:02d}/{len(cases_to_run):02d}] Caso #{case.id:02d} (Orig: #{case.original_id} {case.original_suite}) {case.name} ... ", end="", flush=True)
        res = execute_case(case)
        results.append(res)

        if res.knowledge_resolved:
            print(f"🟢 RESOLVIDO ({res.duration_ms:.0f}ms) [Tools: {', '.join(res.actual_tools)}]")
        else:
            fallback_label = f"'{res.fallback_detected}'" if res.fallback_detected else "Falha técnica"
            print(f"⚠️ FALLBACK ({res.duration_ms:.0f}ms) [{fallback_label}]")

        if args.verbose:
            print(f"       📥 Pergunta: {case.input_message}")
            print(f"       🛠️ Tools: {res.actual_tools}")
            print(f"       📤 Resposta: {res.final_response_snippet}\n")

    total_time = time.time() - t_suite_start
    resolved_count = sum(1 for r in results if r.knowledge_resolved)
    unresolved_count = len(results) - resolved_count

    # Gera relatórios
    report_paths = generate_reports(results, TEST_REGISTRY_UNANSWERED, args.output_dir)

    print("\n" + "=" * 80)
    print(f"🏁 EXECUÇÃO CONCLUÍDA EM {total_time:.2f}s")
    print(f"• Total Executado:               {len(results)}")
    print(f"• Conhecimento Respondido:       🟢 {resolved_count} ({resolved_count / len(results) * 100:.1f}%)")
    print(f"• Fallback (Ainda sem resposta): ⚠️ {unresolved_count}")
    print(f"\n📄 Relatório Markdown salvo em: {report_paths['md']}")
    print(f"📊 Relatório JSON salvo em:     {report_paths['json']}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
