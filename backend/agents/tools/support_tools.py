"""
tools/support_tools.py
----------------------
Ferramentas do Agente 3 (Customer Support Agent).
Recupera dados cadastrais, financeiros e operacionais específicos do cliente (user_id),
atendendo aos cenários de teste oficiais da Getnet.
"""

from typing import Optional
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Base de Dados Simulada (Mock Realista Getnet - Indexada por user_id)
# ---------------------------------------------------------------------------

_CLIENT_DATABASE = {
    "cliente1988": {
        "nome": "Comércio Silva & Santos Ltda",
        "cnpj": "12.345.678/0001-90",
        "segmento": "Varejo / Moda",
        "conta_bancaria": {
            "banco": "033 - Banco Santander (Brasil) S.A.",
            "agencia": "1234",
            "conta": "98765-4",
            "tipo": "Conta Corrente Jurídica"
        },
        "maquininhas": [
            {
                "serial": "POS-8812",
                "modelo": "Get Smart",
                "status": "Online",
                "conexao": "Wi-Fi (Rede Corporativa) + 4G Claro",
                "ultima_comunicacao": "Hoje às 17:30",
                "bobina_status": "Normal"
            },
            {
                "serial": "POS-5541",
                "modelo": "Get Clássica",
                "status": "Offline / Sem Sinal",
                "conexao": "Chip 3G Vivo (falha de sinal detectada)",
                "ultima_comunicacao": "Ontem às 18:22",
                "bobina_status": "Normal"
            }
        ],
        "vendas_ontem": {
            "data": "Ontem",
            "total_bruto": 1250.00,
            "total_liquido": 1205.50,
            "quantidade_vendas": 8,
            "detalhes": [
                {"tipo": "Crédito à Vista", "valor": 850.00, "taxa_mdr": "2.8%"},
                {"tipo": "Débito", "valor": 400.00, "taxa_mdr": "1.3%"}
            ],
            "previsao_deposito": "Amanhã até às 18h na sua conta cadastrada Santander (Agência 1234, Conta 98765-4), conforme prazo contratual de liquidação D+2."
        },
        "transacoes_recentes": [
            {
                "id_transacao": "TXN-99821",
                "data_hora": "Hoje às 16:45",
                "valor": 320.00,
                "modalidade": "Crédito",
                "bandeira": "Mastercard",
                "status": "RECUSADA",
                "codigo_recusa": "51",
                "motivo_tecnico": "Saldo Insuficiente do Portador",
                "orientacao": "A recusa ocorreu porque o cartão do cliente não possuía limite/saldo suficiente. Não se trata de falha na maquininha. Oriente o cliente a utilizar outro cartão ou contatar o banco emissor."
            },
            {
                "id_transacao": "TXN-99810",
                "data_hora": "Hoje às 14:12",
                "valor": 150.00,
                "modalidade": "Débito",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso"
            }
        ]
    }
}

_ticket_sequence = 2000


@tool
def consultar_vendas_e_liquidacao(user_id: str) -> str:
    """
    Consulta o extrato de vendas recentes, valores a receber e a previsão exata de depósito
    bancário para o cliente especificado.
    Use quando o cliente perguntar quando o dinheiro de vendas será depositado ou sobre recebíveis.
    
    Args:
        user_id: Identificador do cliente (ex: 'cliente1988')
    """
    cliente = _CLIENT_DATABASE.get(user_id)
    if not cliente:
        return f"Cliente com identificador '{user_id}' não localizado na base de credenciamento Getnet."

    vendas = cliente["vendas_ontem"]
    conta = cliente["conta_bancaria"]

    return (
        f"📊 Extrato Financeiro - Cliente: {cliente['nome']} (ID: {user_id})\n"
        f"• Vendas de Ontem: R$ {vendas['total_bruto']:.2f} (Líquido: R$ {vendas['total_liquido']:.2f})\n"
        f"• Quantidade de Transações: {vendas['quantidade_vendas']}\n"
        f"• Previsão de Depósito: {vendas['previsao_deposito']}\n"
        f"• Conta de Liquidação: {conta['banco']}, Ag: {conta['agencia']}, CC: {conta['conta']}"
    )


@tool
def consultar_status_maquininhas(user_id: str) -> str:
    """
    Consulta a lista e a situação operacional das maquininhas POS vinculadas ao cliente,
    incluindo conectividade, modelo, número de série e status de sinal.
    Use quando o cliente relatar que a maquininha não conecta ou apresentar problemas de comunicação.
    
    Args:
        user_id: Identificador do cliente (ex: 'cliente1988')
    """
    cliente = _CLIENT_DATABASE.get(user_id)
    if not cliente:
        return f"Cliente com identificador '{user_id}' não localizado."

    maquininhas = cliente.get("maquininhas", [])
    if not maquininhas:
        return f"Nenhum terminal POS ativo encontrado para o cliente '{user_id}'."

    linhas = [f"💳 Terminais Vinculados ao Cliente: {cliente['nome']}"]
    for m in maquininhas:
        linhas.append(
            f"- Modelo: {m['modelo']} (Serial: {m['serial']})\n"
            f"  Status: {m['status']}\n"
            f"  Conexão Atual: {m['conexao']}\n"
            f"  Último Sinal: {m['ultima_comunicacao']}"
        )

    return "\n\n".join(linhas)


@tool
def consultar_transacoes_e_erros(user_id: str) -> str:
    """
    Consulta o histórico das últimas transações do cliente, detalhando tentativas recusadas,
    códigos de erro retornados pela adquirente (ex: erro 51, erro 05) e orientação técnica.
    Use quando o cliente informar que a maquininha está recusando transações.
    
    Args:
        user_id: Identificador do cliente (ex: 'cliente1988')
    """
    cliente = _CLIENT_DATABASE.get(user_id)
    if not cliente:
        return f"Cliente com identificador '{user_id}' não localizado."

    transacoes = cliente.get("transacoes_recentes", [])
    if not transacoes:
        return f"Nenhuma transação recente encontrada para o cliente '{user_id}'."

    linhas = [f"📑 Últimas Transações do Cliente: {cliente['nome']}"]
    for t in transacoes:
        status_icon = "❌" if t["status"] == "RECUSADA" else "✅"
        recusa_info = f" (Código {t['codigo_recusa']}: {t['motivo_tecnico']})" if t["codigo_recusa"] else ""
        linhas.append(
            f"{status_icon} Transação {t['id_transacao']} - {t['data_hora']}\n"
            f"   Valor: R$ {t['valor']:.2f} ({t['modalidade']} - {t['bandeira']})\n"
            f"   Status: {t['status']}{recusa_info}\n"
            f"   Orientação: {t['orientacao'] if t.get('orientacao') else 'N/A'}"
        )

    return "\n\n".join(linhas)


@tool
def abrir_chamado_suporte(
    user_id: str,
    motivo: str,
    prioridade: str = "normal",
) -> str:
    """
    Abre um chamado ou ticket de suporte técnico especializado na Getnet.
    Use quando o problema operacional não puder ser resolvido de forma remota ou requerer visita/troca de POS.
    
    Args:
        user_id: Identificador do cliente
        motivo: Descrição clara do problema técnico ou solicitação
        prioridade: 'baixa', 'normal' ou 'alta'
    """
    global _ticket_sequence
    _ticket_sequence += 1
    ticket_id = f"GET-{_ticket_sequence}"

    return (
        f"✅ Chamado Técnico Getnet Registrado com Sucesso!\n"
        f"• Protocolo: {ticket_id}\n"
        f"• Cliente: {user_id}\n"
        f"• Motivo: {motivo}\n"
        f"• Prioridade: {prioridade.upper()}\n"
        f"• Prazo de Atendimento: Até 24 horas úteis."
    )


SUPPORT_TOOLS = [
    consultar_vendas_e_liquidacao,
    consultar_status_maquininhas,
    consultar_transacoes_e_erros,
    abrir_chamado_suporte,
]
