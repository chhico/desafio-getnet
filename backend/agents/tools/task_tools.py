"""
tools/task_tools.py
-------------------
Ferramentas do Task Agent.

Gerencia tarefas, listas de afazeres e geração de relatórios/resumos.

Implementação em memória (mock) — em produção conecte a:
Jira, Asana, Trello, Notion, banco de dados próprio, etc.
"""

from datetime import datetime
from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Simulação de banco de dados de tarefas em memória
# ---------------------------------------------------------------------------

_tasks_db: list[dict] = []
_task_counter = 0


def _next_id() -> str:
    global _task_counter
    _task_counter += 1
    return f"TASK-{_task_counter:03d}"


# ---------------------------------------------------------------------------
# Ferramentas
# ---------------------------------------------------------------------------

@tool
def criar_tarefa(
    titulo: str,
    descricao: str = "",
    prioridade: str = "normal",
    responsavel: str = "não atribuído",
) -> str:
    """
    Cria uma nova tarefa na lista de afazeres.
    Use quando o usuário quiser registrar algo para ser feito.

    Args:
        titulo: Título curto e descritivo da tarefa
        descricao: Detalhes adicionais (opcional)
        prioridade: baixa, normal ou alta
        responsavel: Nome da pessoa responsável (opcional)
    """
    task = {
        "id": _next_id(),
        "titulo": titulo,
        "descricao": descricao,
        "prioridade": prioridade,
        "responsavel": responsavel,
        "status": "pendente",
        "criada_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    _tasks_db.append(task)
    return (
        f"✅ Tarefa criada!\n"
        f"   ID: {task['id']}\n"
        f"   Título: {task['titulo']}\n"
        f"   Prioridade: {task['prioridade']}\n"
        f"   Responsável: {task['responsavel']}"
    )


@tool
def listar_tarefas(filtro_status: str = "todas") -> str:
    """
    Lista as tarefas existentes com opção de filtrar por status.
    Use quando o usuário quiser ver o que está pendente ou em andamento.

    Args:
        filtro_status: todas, pendente, em_andamento ou concluida
    """
    if not _tasks_db:
        return "📋 Nenhuma tarefa cadastrada ainda."

    tasks = _tasks_db
    if filtro_status != "todas":
        tasks = [t for t in _tasks_db if t["status"] == filtro_status]

    if not tasks:
        return f"Nenhuma tarefa com status '{filtro_status}'."

    linhas = [f"📋 Tarefas ({filtro_status}):"]
    for t in tasks:
        emoji = {"pendente": "⏳", "em_andamento": "🔄", "concluida": "✅"}.get(t["status"], "•")
        linhas.append(
            f"  {emoji} [{t['id']}] {t['titulo']} "
            f"| {t['prioridade']} | {t['responsavel']}"
        )
    return "\n".join(linhas)


@tool
def atualizar_status_tarefa(task_id: str, novo_status: str) -> str:
    """
    Atualiza o status de uma tarefa existente.
    Use quando o usuário quiser marcar uma tarefa como concluída ou em andamento.

    Args:
        task_id: ID da tarefa (ex: TASK-001)
        novo_status: pendente, em_andamento ou concluida
    """
    valid_statuses = ["pendente", "em_andamento", "concluida"]
    if novo_status not in valid_statuses:
        return f"Status inválido. Use: {', '.join(valid_statuses)}"

    for task in _tasks_db:
        if task["id"].upper() == task_id.upper():
            old_status = task["status"]
            task["status"] = novo_status
            return (
                f"✅ Tarefa {task_id} atualizada!\n"
                f"   {old_status} → {novo_status}"
            )
    return f"Tarefa {task_id} não encontrada."


@tool
def gerar_relatorio_tarefas() -> str:
    """
    Gera um relatório resumido de todas as tarefas.
    Use quando o usuário quiser um resumo do que foi feito e o que está pendente.
    """
    if not _tasks_db:
        return "Nenhuma tarefa para incluir no relatório."

    total = len(_tasks_db)
    por_status = {"pendente": 0, "em_andamento": 0, "concluida": 0}
    por_prioridade = {"alta": 0, "normal": 0, "baixa": 0}

    for t in _tasks_db:
        por_status[t.get("status", "pendente")] += 1
        por_prioridade[t.get("prioridade", "normal")] += 1

    relatorio = f"""📊 Relatório de Tarefas — {datetime.now().strftime('%d/%m/%Y %H:%M')}
{'='*45}
Total de tarefas: {total}

Por status:
  ⏳ Pendentes:     {por_status['pendente']}
  🔄 Em andamento:  {por_status['em_andamento']}
  ✅ Concluídas:    {por_status['concluida']}

Por prioridade:
  🔴 Alta:   {por_prioridade['alta']}
  🟡 Normal: {por_prioridade['normal']}
  🟢 Baixa:  {por_prioridade['baixa']}
{'='*45}"""
    return relatorio


TASK_TOOLS = [criar_tarefa, listar_tarefas, atualizar_status_tarefa, gerar_relatorio_tarefas]
