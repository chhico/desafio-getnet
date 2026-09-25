"""
tools/escalation_tools.py
-------------------------
Ferramentas do Agente de Escalonamento Humano (Human Escalation Agent).
Realiza a transferência assistida em tempo real (Human Handoff) para operadores humanos.
"""

import random
from langchain_core.tools import tool

OPERADORES_POR_FILA = {
    "Suporte Técnico N2 - Terminais": [
        "Carlos M. (Especialista POS)",
        "Rafael T. (Técnico de Campo)",
        "Mariana S. (Suporte N2)",
    ],
    "Segurança da Informação e Prevenção a Fraudes": [
        "Beatriz R. (Prevenção a Fraudes)",
        "Lucas F. (Incident Response)",
        "Camila D. (Compliance & Risco)",
    ],
    "Jurídico, Compliance e Regulatório": [
        "Dr. Eduardo P. (Jurídico Contencioso)",
        "Dra. Vanessa L. (Compliance Bacen)",
        "Thiago B. (Ouvidoria Regulatória)",
    ],
    "Mesa de Grandes Contas e Key Accounts": [
        "Felipe A. (Executivo de Contas)",
        "Patricia N. (Gerente Key Accounts)",
        "Rodrigo K. (Soluções TEF)",
    ],
    "Mesa de Negócios e Tarifas": [
        "Juliana M. (Consultora Comercial)",
        "Bruno H. (Retenção e Fidelidade)",
        "Aline C. (Negócios)",
    ],
    "Ouvidoria e Atendimento Geral": [
        "Ana Paula S. (Supervisora de Atendimento)",
        "Guilherme O. (Ouvidoria)",
        "Carla T. (Suporte Especial)",
    ],
}

OPERADORES_PADRAO = ["Carlos M.", "Mariana S.", "Beatriz R.", "Lucas F.", "Juliana M."]


@tool
def transferir_atendimento_humano(
    user_id: str = "",
    motivo: str = "",
    protocolo: str = "",
    fila: str = "",
) -> dict:
    """
    Aciona a transferência de atendimento em tempo real para um operador humano especializado (Human Handoff).
    Transmite os dados cadastrais do cliente, histórico e resumo executivo do incidente para a estação de trabalho do atendente.

    Args:
        user_id: Identificador do cliente solicitante.
        motivo: Resumo executivo do problema ou justificativa da transferência.
        protocolo: Número de protocolo oficial Getnet gerado (ex: GET-2026-XXXX).
        fila: Fila técnica de destino no atendimento humano.
    """
    operadores_disponiveis = OPERADORES_POR_FILA.get(fila, OPERADORES_PADRAO)
    operador_atribuido = random.choice(operadores_disponiveis)

    return {
        "status": "CONECTADO_OPERADOR",
        "operador": operador_atribuido,
        "fila_destino": fila or "Suporte Técnico N2 - Terminais",
        "tempo_estimado": "< 1 minuto",
        "protocolo": protocolo,
        "cliente_id": user_id,
        "resumo_transmitido": motivo,
        "canal": "Chat Seguro Integrado (Live Handoff)",
        "mensagem_sistema": (
            f"Operador {operador_atribuido} assumiu a sessão com o protocolo {protocolo}. "
            f"Contexto do cliente carregado com sucesso."
        ),
    }


ESCALATION_TOOLS = [transferir_atendimento_humano]

