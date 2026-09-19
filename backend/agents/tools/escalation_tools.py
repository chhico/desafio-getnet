"""
tools/escalation_tools.py
-------------------------
Ferramentas do Agente de Escalonamento Humano (Human Escalation Agent).
"""

from langchain_core.tools import tool


@tool
def abrir_chamado_servicenow(
    user_id: str = "",
    motivo: str = "",
    protocolo: str = "",
    fila: str = "",
) -> None:
    """
    Registra a abertura de chamado/incidente no ServiceNow para transferência e atendimento humano.
    Sempre invocada automaticamente quando houver transferência de atendimento para operador humano.

    Args:
        user_id: Identificador do cliente solicitante.
        motivo: Resumo do problema ou justificativa da transferência.
        protocolo: Número de protocolo oficial Getnet gerado.
        fila: Fila técnica de destino no ServiceNow.
    """
    return None


ESCALATION_TOOLS = [abrir_chamado_servicenow]
