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
        "cpf": "111.222.333-44",
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
    },
    "cliente2024": {
        "cpf": "222.333.444-55",
        "nome": "Padaria & Confeitaria Pão D'Ouro",
        "cnpj": "23.456.789/0001-01",
        "segmento": "Alimentação / Panificação",
        "conta_bancaria": {
            "banco": "237 - Banco Bradesco S.A.",
            "agencia": "4567",
            "conta": "12345-6",
            "tipo": "Conta Corrente Jurídica"
        },
        "maquininhas": [
            {
                "serial": "POS-7733",
                "modelo": "Get Mini",
                "status": "Online",
                "conexao": "Chip 4G Vivo (Sinal Excelente)",
                "ultima_comunicacao": "Hoje às 19:15",
                "bobina_status": "Não se aplica (comprovante digital por SMS)"
            },
            {
                "serial": "POS-7734",
                "modelo": "Get Smart",
                "status": "Online",
                "conexao": "Wi-Fi (Balcão)",
                "ultima_comunicacao": "Hoje às 19:20",
                "bobina_status": "Normal"
            }
        ],
        "vendas_ontem": {
            "data": "Ontem",
            "total_bruto": 3420.00,
            "total_liquido": 3317.40,
            "quantidade_vendas": 42,
            "detalhes": [
                {"tipo": "Débito", "valor": 1900.00, "taxa_mdr": "1.2%"},
                {"tipo": "Crédito à Vista", "valor": 1520.00, "taxa_mdr": "2.5%"}
            ],
            "previsao_deposito": "Hoje até às 20h creditado na sua conta Bradesco (Agência 4567, Conta 12345-6), modalidade acelerada D+1."
        },
        "transacoes_recentes": [
            {
                "id_transacao": "TXN-20241",
                "data_hora": "Hoje às 18:40",
                "valor": 65.50,
                "modalidade": "Débito",
                "bandeira": "Elo",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso"
            }
        ]
    },
    "cliente3030": {
        "cpf": "333.444.555-66",
        "nome": "Drogaria & Farmácia Vida e Saúde",
        "cnpj": "34.567.890/0001-12",
        "segmento": "Saúde / Drogaria",
        "conta_bancaria": {
            "banco": "001 - Banco do Brasil S.A.",
            "agencia": "3344",
            "conta": "55667-8",
            "tipo": "Conta Corrente Jurídica"
        },
        "maquininhas": [
            {
                "serial": "POS-3321",
                "modelo": "Get Smart",
                "status": "Online",
                "conexao": "Wi-Fi Principal",
                "ultima_comunicacao": "Hoje às 19:50",
                "bobina_status": "Alerta: Pouco Papel (Troca recomendada)"
            }
        ],
        "vendas_ontem": {
            "data": "Ontem",
            "total_bruto": 890.00,
            "total_liquido": 863.30,
            "quantidade_vendas": 15,
            "detalhes": [
                {"tipo": "Débito", "valor": 540.00, "taxa_mdr": "1.3%"},
                {"tipo": "Crédito", "valor": 350.00, "taxa_mdr": "2.7%"}
            ],
            "previsao_deposito": "Amanhã até às 12h no Banco do Brasil (Agência 3344, Conta 55667-8), prazo D+2."
        },
        "transacoes_recentes": [
            {
                "id_transacao": "TXN-33109",
                "data_hora": "Hoje às 17:10",
                "valor": 88.00,
                "modalidade": "Crédito",
                "bandeira": "Visa",
                "status": "RECUSADA",
                "codigo_recusa": "05",
                "motivo_tecnico": "Não Autorizada pelo Banco Emissor (Erro 05)",
                "orientacao": "O banco emissor do cartão bloqueou a transação por suspeita preventiva ou restrição cadastral. O cliente deve ligar para o número no verso do cartão."
            }
        ]
    },
    "cliente4040": {
        "cpf": "444.555.666-77",
        "nome": "Auto Mecânica & Peças Central",
        "cnpj": "45.678.901/0001-23",
        "segmento": "Automotivo / Serviços",
        "conta_bancaria": {
            "banco": "104 - Caixa Econômica Federal",
            "agencia": "0987",
            "conta": "77889-0",
            "tipo": "Conta Jurídica"
        },
        "maquininhas": [
            {
                "serial": "POS-4410",
                "modelo": "Get Clássica",
                "status": "Offline / Sem Sinal",
                "conexao": "Chip 3G Tim (Sem comunicação há 3 dias)",
                "ultima_comunicacao": "3 dias atrás",
                "bobina_status": "Normal"
            }
        ],
        "vendas_ontem": {
            "data": "Ontem",
            "total_bruto": 0.00,
            "total_liquido": 0.00,
            "quantidade_vendas": 0,
            "detalhes": [],
            "previsao_deposito": "Sem lançamentos de vendas registradas no dia de ontem."
        },
        "transacoes_recentes": [
            {
                "id_transacao": "TXN-44001",
                "data_hora": "3 dias atrás",
                "valor": 450.00,
                "modalidade": "Crédito Parcelado",
                "bandeira": "Mastercard",
                "status": "RECUSADA",
                "codigo_recusa": "96",
                "motivo_tecnico": "Falha de Comunicação / Timeout da Operadora",
                "orientacao": "Houve perda de sinal móvel durante o envio da transação. É necessário reiniciar a maquininha ou reposicionar em local com melhor cobertura celular."
            }
        ]
    },
    "cliente5050": {
        "cpf": "555.666.777-88",
        "nome": "Restaurante e Churrascaria Brasa Nobre",
        "cnpj": "56.789.012/0001-34",
        "segmento": "Gastronomia / Restaurante",
        "conta_bancaria": {
            "banco": "341 - Itaú Unibanco S.A.",
            "agencia": "8877",
            "conta": "33221-1",
            "tipo": "Conta Corrente Jurídica"
        },
        "maquininhas": [
            {
                "serial": "POS-501",
                "modelo": "Get Smart",
                "status": "Online",
                "conexao": "Wi-Fi 5Ghz Salão",
                "ultima_comunicacao": "Hoje às 19:55",
                "bobina_status": "Normal"
            },
            {
                "serial": "POS-502",
                "modelo": "Get Smart",
                "status": "Online",
                "conexao": "Wi-Fi 5Ghz Salão",
                "ultima_comunicacao": "Hoje às 19:58",
                "bobina_status": "Normal"
            }
        ],
        "vendas_ontem": {
            "data": "Ontem",
            "total_bruto": 12800.00,
            "total_liquido": 12416.00,
            "quantidade_vendas": 114,
            "detalhes": [
                {"tipo": "Crédito", "valor": 8200.00, "taxa_mdr": "2.4%"},
                {"tipo": "Débito", "valor": 4600.00, "taxa_mdr": "1.2%"}
            ],
            "previsao_deposito": "Antecipação Automática contratada: valor líquido de R$ 12.416,00 creditado com sucesso hoje às 10:00 na conta Itaú (Agência 8877, Conta 33221-1)."
        },
        "transacoes_recentes": [
            {
                "id_transacao": "TXN-50190",
                "data_hora": "Hoje às 19:40",
                "valor": 340.00,
                "modalidade": "Crédito",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso"
            }
        ]
    }
}


def buscar_cliente_por_documento(doc_or_id: str) -> Optional[tuple[str, dict]]:
    """
    Busca um cliente na base simulada a partir do ID de cliente, CPF ou CNPJ.
    Ignora pontuações, traços e formatação.
    Retorna (client_key, client_data) se encontrado, ou None se não localizado.
    """
    if not doc_or_id:
        return None

    import re
    raw = doc_or_id.strip()
    raw_lower = raw.lower()

    # 1. Match direto por chave exata (ex: 'cliente1988', 'cliente2024')
    if raw_lower in _CLIENT_DATABASE:
        return raw_lower, _CLIENT_DATABASE[raw_lower]

    # 2. Busca por menção da chave no texto (ex: 'meu id é cliente1988')
    for key, data in _CLIENT_DATABASE.items():
        if key in raw_lower:
            return key, data

    # 3. Match por dígitos de CPF ou CNPJ
    digits_only = re.sub(r"\D", "", raw)
    if digits_only and len(digits_only) >= 8:
        for key, data in _CLIENT_DATABASE.items():
            cpf_digits = re.sub(r"\D", "", data.get("cpf", ""))
            if cpf_digits and digits_only == cpf_digits:
                return key, data

            cnpj_digits = re.sub(r"\D", "", data.get("cnpj", ""))
            if cnpj_digits and digits_only == cnpj_digits:
                return key, data

    return None

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
