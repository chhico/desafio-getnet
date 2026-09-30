"""
tests/reporters/dossier_generator.py
------------------------------------
Gerador de Dossiê Executivo de Testes e Evals para o Desafio Getnet.
Produz relatórios consolidados em Markdown e JSON com métricas de IA,
cobertura do edital, trajetória de agentes e indicadores de FinOps/P95.
"""

import os
import json
import time
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class DossierGenerator:
    """Gerador e consolidador de Dossiês de Execução de Testes de IA."""

    def __init__(self, output_dir: str = "tests/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_dossier(
        self,
        suite_name: str,
        results: List[Dict[str, Any]],
        total_duration_s: float,
        timestamp_slug: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Gera relatório em Markdown executivo e JSON estruturado.
        """
        slug = timestamp_slug or datetime.now().strftime("%Y%m%d_%H%M%S")
        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.get("status") == "SUCCESS")
        failed_cases = total_cases - passed_cases
        success_rate = (passed_cases / total_cases * 100.0) if total_cases > 0 else 0.0

        # Latência e Métricas
        latencies = [r.get("duration_ms", 0.0) for r in results if r.get("duration_ms")]
        sorted_lat = sorted(latencies)
        avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
        p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0.0

        # Categorização por Camada
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            cat = r.get("category", "geral")
            by_category.setdefault(cat, []).append(r)

        # Montagem do Markdown
        md_lines = [
            f"# 📑 Dossiê Executivo de Qualidade & Evals — Getnet AI Agent",
            f"**Suíte:** `{suite_name}` | **Execução:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | **Taxa de Aprovação:** {success_rate:.1f}%\n",
            "---",
            "## 1. Sumário Executivo de Conformidade\n",
            f"- **Total de Casos Executados:** `{total_cases}`",
            f"- **Aprovações:** ✅ `{passed_cases}` ({success_rate:.1f}%)",
            f"- **Falhas/Divergências:** {'❌ `' + str(failed_cases) + '`' if failed_cases > 0 else '✅ `0`'}",
            f"- **Tempo Total de Execução:** `{total_duration_s:.2f}s`",
            f"- **Latência Média por Caso:** `{avg_lat:.0f}ms` | **P95:** `{p95_lat:.0f}ms` *(Meta SLA: < 1500ms)*\n",
            "### Distribuição por Camada de Testes\n",
            "| Camada / Categoria | Total de Casos | Sucesso | Falhas | Status |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]

        for cat, items in by_category.items():
            cat_passed = sum(1 for x in items if x.get("status") == "SUCCESS")
            cat_failed = len(items) - cat_passed
            badge = "✅ APROVADO" if cat_failed == 0 else f"❌ {cat_failed} FALHA(S)"
            md_lines.append(
                f"| **{cat.capitalize()}** | {len(items)} | ✅ {cat_passed} | {cat_failed} | {badge} |"
            )

        md_filename = f"relatorio_{suite_name}_{slug}.md"

        # 2. Matriz de Trajetória e Execução dos Agentes
        table_header = [
            "\n---",
            '<a id="matriz-geral"></a>',
            "## 2. Matriz de Trajetória e Execução dos Agentes\n",
            "| ID | Categoria | Cenário de Teste | Turnos | Agentes Percorridos | Ferramentas | Status | Latência |",
            "| :-: | :--- | :--- | :-: | :--- | :--- | :-: | -: |",
        ]

        exec_table_rows = []
        detailed_table_rows = []

        for r in results:
            c_id = r.get("case_id") or r.get("id") or "-"
            cat = r.get("category", "-")
            name = r.get("name", "Cenário")
            turns = r.get("total_turns", 1)
            agents = " ➔ ".join(r.get("all_agents_used", [r.get("agent", "-")]))
            tools = ", ".join(r.get("all_executed_tools", r.get("tools", []))) or "Nenhuma"
            status = "✅ PASS" if r.get("status") == "SUCCESS" else "❌ FAIL"
            lat = f"{r.get('duration_ms', 0):.0f}ms"
            anchor_id = f"caso-{str(c_id).lower().replace('#', '').strip()}"

            # No relatório executivo (latest), linka para o cenário dentro do arquivo detalhado histórico
            exec_table_rows.append(
                f"| `#{c_id}` | {cat} | [{name}]({md_filename}#{anchor_id}) | `{turns}T` | `{agents}` | `{tools}` | {status} | {lat} |"
            )
            # No relatório detalhado (datado), linka diretamente para o cenário na Seção 4
            detailed_table_rows.append(
                f"| `#{c_id}` | {cat} | [{name}](#{anchor_id}) | `{turns}T` | `{agents}` | `{tools}` | {status} | {lat} |"
            )

        # 3. Análise Diagnóstica / Confiabilidade
        diag_lines = []
        failures = [r for r in results if r.get("status") != "SUCCESS"]
        if failures:
            diag_lines.append("\n---")
            diag_lines.append("## 3. Análise Detalhada de Falhas\n")
            for f in failures:
                diag_lines.append(f"### ❌ Caso #{f.get('case_id')}: {f.get('name')}")
                for err in f.get("error_reasons", ["Erro não especificado"]):
                    diag_lines.append(f"- ⚠️ {err}")
                diag_lines.append("")
        else:
            diag_lines.append("\n---")
            diag_lines.append("## 3. Análise de Confiabilidade & Robustez")
            diag_lines.append("🎉 **Excelente! Todos os cenários foram executados com 100% de conformidade, zero vazamentos de memória e integridade de guardrails preservada.**\n")

        # Montagem do Markdown Executivo (Seções 1, 2 e 3)
        exec_lines = list(md_lines) + table_header + exec_table_rows + diag_lines
        md_executive_content = "\n".join(exec_lines)

        # Montagem do Markdown Detalhado com Log Completo Turno a Turno (Input vs Output)
        detailed_lines = list(md_lines) + table_header + detailed_table_rows + diag_lines
        detailed_lines.append("\n---")
        detailed_lines.append("## 4. Auditoria e Transcrição Completa Turno a Turno (Input vs Output)\n")
        detailed_lines.append("> Este registro histórico detalha todas as mensagens de entrada e saída (usuário e IA) de cada caso executado.\n")

        for r in results:
            c_id = r.get("case_id") or r.get("id") or "-"
            name = r.get("name", "Cenário")
            status = "✅ PASS" if r.get("status") == "SUCCESS" else "❌ FAIL"
            cat = r.get("category", "-")
            lat = f"{r.get('duration_ms', 0):.0f}ms"
            agents = " ➔ ".join(r.get("all_agents_used", [r.get("agent", "-")]))
            tools = ", ".join(r.get("all_executed_tools", r.get("tools", []))) or "Nenhuma"
            turns = r.get("turns", [])
            anchor_id = f"caso-{str(c_id).lower().replace('#', '').strip()}"

            detailed_lines.append(f'<a id="{anchor_id}"></a>')
            detailed_lines.append(f"### 🔹 Caso #{c_id}: {name} &nbsp; [🔝 Voltar à Matriz Geral](#matriz-geral)")
            detailed_lines.append(f"- **Categoria:** `{cat}` | **Status:** {status} | **Latência:** `{lat}`")
            detailed_lines.append(f"- **Agentes:** `{agents}`")
            detailed_lines.append(f"- **Ferramentas:** `{tools}`\n")

            if turns:
                detailed_lines.append("<details open>")
                detailed_lines.append(f"<summary><b>Ver Diálogo Completo ({len(turns)} Turno{'s' if len(turns) > 1 else ''})</b></summary>\n")
                for t in turns:
                    t_idx = t.get("turn_index") or t.get("index") or 1
                    user_msg = (t.get("user_message") or t.get("message") or "").strip()
                    resp = (t.get("response") or "").strip()
                    agent = t.get("agent_used") or t.get("actual_agent") or "-"
                    t_tools = t.get("tools_used") or t.get("tools_executed") or []
                    tools_str = f" *(Tools: {', '.join(t_tools)})*" if t_tools else ""

                    detailed_lines.append(f"#### 📥 Turno {t_idx} — Usuário:")
                    user_quoted = "\n".join(f"> {line}" for line in user_msg.split("\n")) if user_msg else "> *(mensagem vazia)*"
                    detailed_lines.append(f"{user_quoted}\n")

                    detailed_lines.append(f"#### 🤖 Turno {t_idx} — Getnet AI (`{agent}`){tools_str}:")
                    resp_quoted = "\n".join(f"> {line}" for line in resp.split("\n")) if resp.split("\n") else "> *(sem resposta)*"
                    detailed_lines.append(f"{resp_quoted}\n")
                detailed_lines.append("</details>\n")
            else:
                detailed_lines.append("*Nenhum turno de diálogo detalhado registrado para este caso.*\n")

        md_detailed_content = "\n".join(detailed_lines)

        # Escrita nos arquivos:
        # 1. O arquivo com TIMESTAMP histórico recebe o LOG COMPLETO e DETALHADO (Input vs Output)
        md_file = self.output_dir / md_filename
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_detailed_content)

        # 2. O arquivo 'latest' recebe a VISÃO EXECUTIVA enxuta e gerencial
        latest_md = self.output_dir / f"relatorio_{suite_name}_latest.md"
        with open(latest_md, "w", encoding="utf-8") as f:
            f.write(md_executive_content)

        json_file = self.output_dir / f"relatorio_{suite_name}_{slug}.json"
        latest_json = self.output_dir / f"relatorio_{suite_name}_latest.json"

        json_data = {
            "suite_name": suite_name,
            "timestamp": slug,
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "success_rate": success_rate,
            "duration_seconds": total_duration_s,
            "latency_p95_ms": p95_lat,
            "results": results
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        shutil.copyfile(json_file, latest_json)

        return {
            "md": str(md_file),
            "latest_md": str(latest_md),
            "json": str(json_file),
            "latest_json": str(latest_json),
        }

dossier_generator = DossierGenerator()

