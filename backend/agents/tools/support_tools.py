"""
tools/support_tools.py
----------------------
Ferramentas do Agente 3 (Customer Support Agent).
Recupera dados cadastrais, financeiros e operacionais específicos do cliente (user_id),
atendendo aos cenários de teste oficiais da Getnet.
"""

from typing import Optional
from datetime import datetime
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Base de Dados Simulada (Mock Realista Getnet - Indexada por user_id)
#
# Estrutura de cada cliente:
#   - cpf / cnpj / nome / segmento: dados cadastrais básicos.
#   - conta_bancaria: conta de liquidação vinculada ao credenciamento Getnet.
#   - maquininhas: lista de terminais POS ativos (status de conexão, modelo, serial).
#   - historico_financeiro: lista de fechamentos diários de vendas. Cada entrada
#       representa um dia completo com data ISO (YYYY-MM-DD), permitindo consultas
#       por data específica ou listagem de todos os dias disponíveis.
#   - transacoes: lista de transações individuais com data/hora ISO, status variado
#       (APROVADA | RECUSADA | AGUARDANDO_APROVACAO | CANCELADA | ESTORNADA) e
#       orientacao técnica. Suporta filtragem por id, status e data.
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
        "historico_financeiro": [
            {
                "data": "2026-09-22",
                "total_bruto": 1250.00,
                "total_liquido": 1205.50,
                "quantidade_vendas": 8,
                "detalhes": [
                    {"tipo": "Crédito à Vista", "valor": 850.00, "taxa_mdr": "2.8%"},
                    {"tipo": "Débito", "valor": 400.00, "taxa_mdr": "1.3%"}
                ],
                "prazo_liquidacao": "D+2",
                "previsao_deposito": "Depósito previsto para 2026-09-24 até às 18h na conta Santander (Ag: 1234, CC: 98765-4)."
            },
            {
                "data": "2026-09-21",
                "total_bruto": 980.00,
                "total_liquido": 947.14,
                "quantidade_vendas": 6,
                "detalhes": [
                    {"tipo": "Crédito à Vista", "valor": 580.00, "taxa_mdr": "2.8%"},
                    {"tipo": "Débito", "valor": 400.00, "taxa_mdr": "1.3%"}
                ],
                "prazo_liquidacao": "D+2",
                "previsao_deposito": "Depósito previsto para 2026-09-23 até às 18h na conta Santander (Ag: 1234, CC: 98765-4)."
            },
            {
                "data": "2026-09-20",
                "total_bruto": 430.00,
                "total_liquido": 418.17,
                "quantidade_vendas": 3,
                "detalhes": [
                    {"tipo": "Débito", "valor": 430.00, "taxa_mdr": "1.3%"}
                ],
                "prazo_liquidacao": "D+2",
                "previsao_deposito": "Depósito previsto para 2026-09-22 até às 18h na conta Santander (Ag: 1234, CC: 98765-4)."
            }
        ],
        "transacoes": [
            {
                "id_transacao": "TXN-99821",
                "data": "2026-09-22",
                "hora": "16:45",
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
                "data": "2026-09-22",
                "hora": "14:12",
                "valor": 150.00,
                "modalidade": "Débito",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            },
            {
                "id_transacao": "TXN-99798",
                "data": "2026-09-21",
                "hora": "11:30",
                "valor": 200.00,
                "modalidade": "Crédito Parcelado",
                "bandeira": "Visa",
                "status": "AGUARDANDO_APROVACAO",
                "codigo_recusa": None,
                "motivo_tecnico": "Aguardando confirmação do banco emissor",
                "orientacao": "A transação está em análise pelo banco emissor. Normalmente confirmada em até 2 horas. Não tente reprocessar para evitar duplicidade."
            },
            {
                "id_transacao": "TXN-99750",
                "data": "2026-09-20",
                "hora": "09:05",
                "valor": 80.00,
                "modalidade": "Débito",
                "bandeira": "Elo",
                "status": "ESTORNADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Estorno solicitado pelo estabelecimento",
                "orientacao": "O valor foi estornado ao portador dentro do prazo previsto. Nenhuma ação adicional necessária."
            }
        ],
        "chamados": [
            {
                "protocolo": "GET-2026-8819",
                "tipo": "Visita Técnica para Troca de POS",
                "motivo": "Leitor de chip da Get Clássica danificado",
                "data_abertura": "2026-09-16",
                "status": "AGENDADO",
                "data_agendamento": "2026-09-25",
                "periodo": "Tarde (13h às 18h)",
                "tecnico_responsavel": "Marcos Oliveira",
                "observacoes": "Visita técnica confirmada. Técnico levará terminal Get Clássica novo para substituição no local. Permite reagendamento para o período da manhã mediante aviso prévio."
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
        "historico_financeiro": [
            {
                "data": "2026-09-22",
                "total_bruto": 3420.00,
                "total_liquido": 3317.40,
                "quantidade_vendas": 42,
                "detalhes": [
                    {"tipo": "Débito", "valor": 1900.00, "taxa_mdr": "1.2%"},
                    {"tipo": "Crédito à Vista", "valor": 1520.00, "taxa_mdr": "2.5%"}
                ],
                "prazo_liquidacao": "D+1",
                "previsao_deposito": "Depósito previsto para 2026-09-23 até às 20h na conta Bradesco (Ag: 4567, CC: 12345-6), modalidade acelerada."
            },
            {
                "data": "2026-09-21",
                "total_bruto": 2980.00,
                "total_liquido": 2890.60,
                "quantidade_vendas": 37,
                "detalhes": [
                    {"tipo": "Débito", "valor": 1600.00, "taxa_mdr": "1.2%"},
                    {"tipo": "Crédito à Vista", "valor": 1380.00, "taxa_mdr": "2.5%"}
                ],
                "prazo_liquidacao": "D+1",
                "previsao_deposito": "Depositado em 2026-09-22 às 19:45 na conta Bradesco (Ag: 4567, CC: 12345-6)."
            }
        ],
        "transacoes": [
            {
                "id_transacao": "TXN-20241",
                "data": "2026-09-22",
                "hora": "18:40",
                "valor": 65.50,
                "modalidade": "Débito",
                "bandeira": "Elo",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            },
            {
                "id_transacao": "TXN-20235",
                "data": "2026-09-22",
                "hora": "10:22",
                "valor": 122.00,
                "modalidade": "Crédito à Vista",
                "bandeira": "Mastercard",
                "status": "CANCELADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Cancelado pelo operador antes da finalização",
                "orientacao": "A transação foi cancelada pelo operador da maquininha antes de ser concluída. Nenhum débito foi efetuado no cartão do cliente."
            },
            {
                "id_transacao": "TXN-20210",
                "data": "2026-09-21",
                "hora": "15:05",
                "valor": 48.90,
                "modalidade": "Débito",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            }
        ],
        "chamados": [
            {
                "protocolo": "GET-2026-7740",
                "tipo": "Envio de Suprimentos / Bobinas",
                "motivo": "Solicitação de pacote de bobinas térmicas de 57mm para Get Clássica",
                "data_abertura": "2026-09-20",
                "status": "EM_TRANSITO",
                "data_agendamento": None,
                "periodo": None,
                "tecnico_responsavel": None,
                "observacoes": "Pacote despachado via Correios (Rastreio: QB123456789BR). Previsão de entrega em 2 dias úteis."
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
        "historico_financeiro": [
            {
                "data": "2026-09-22",
                "total_bruto": 890.00,
                "total_liquido": 863.30,
                "quantidade_vendas": 15,
                "detalhes": [
                    {"tipo": "Débito", "valor": 540.00, "taxa_mdr": "1.3%"},
                    {"tipo": "Crédito", "valor": 350.00, "taxa_mdr": "2.7%"}
                ],
                "prazo_liquidacao": "D+2",
                "previsao_deposito": "Depósito previsto para 2026-09-24 até às 12h no Banco do Brasil (Ag: 3344, CC: 55667-8)."
            },
            {
                "data": "2026-09-21",
                "total_bruto": 740.00,
                "total_liquido": 718.78,
                "quantidade_vendas": 12,
                "detalhes": [
                    {"tipo": "Débito", "valor": 400.00, "taxa_mdr": "1.3%"},
                    {"tipo": "Crédito", "valor": 340.00, "taxa_mdr": "2.7%"}
                ],
                "prazo_liquidacao": "D+2",
                "previsao_deposito": "Depósito previsto para 2026-09-23 até às 12h no Banco do Brasil (Ag: 3344, CC: 55667-8)."
            }
        ],
        "transacoes": [
            {
                "id_transacao": "TXN-33109",
                "data": "2026-09-22",
                "hora": "17:10",
                "valor": 88.00,
                "modalidade": "Crédito",
                "bandeira": "Visa",
                "status": "RECUSADA",
                "codigo_recusa": "05",
                "motivo_tecnico": "Não Autorizada pelo Banco Emissor (Erro 05)",
                "orientacao": "O banco emissor do cartão bloqueou a transação por suspeita preventiva ou restrição cadastral. O cliente deve ligar para o número no verso do cartão."
            },
            {
                "id_transacao": "TXN-33098",
                "data": "2026-09-22",
                "hora": "13:45",
                "valor": 210.00,
                "modalidade": "Débito",
                "bandeira": "Elo",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            },
            {
                "id_transacao": "TXN-33085",
                "data": "2026-09-21",
                "hora": "09:30",
                "valor": 55.00,
                "modalidade": "Débito",
                "bandeira": "Mastercard",
                "status": "AGUARDANDO_APROVACAO",
                "codigo_recusa": None,
                "motivo_tecnico": "Aguardando confirmação do banco emissor",
                "orientacao": "A transação está em análise pelo banco emissor. Normalmente confirmada em até 2 horas. Não tente reprocessar para evitar duplicidade."
            }
        ],
        "chamados": []
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
        "historico_financeiro": [
            {
                "data": "2026-09-22",
                "total_bruto": 0.00,
                "total_liquido": 0.00,
                "quantidade_vendas": 0,
                "detalhes": [],
                "prazo_liquidacao": "N/A",
                "previsao_deposito": "Sem lançamentos de vendas registradas neste dia."
            },
            {
                "data": "2026-09-19",
                "total_bruto": 450.00,
                "total_liquido": 437.40,
                "quantidade_vendas": 2,
                "detalhes": [
                    {"tipo": "Crédito Parcelado", "valor": 450.00, "taxa_mdr": "2.8%"}
                ],
                "prazo_liquidacao": "D+30 (parcelado)",
                "previsao_deposito": "Parcelas mensais creditadas a partir de 2026-10-19 na conta Caixa Econômica (Ag: 0987, CC: 77889-0)."
            }
        ],
        "transacoes": [
            {
                "id_transacao": "TXN-44001",
                "data": "2026-09-19",
                "hora": "10:15",
                "valor": 450.00,
                "modalidade": "Crédito Parcelado",
                "bandeira": "Mastercard",
                "status": "RECUSADA",
                "codigo_recusa": "96",
                "motivo_tecnico": "Falha de Comunicação / Timeout da Operadora",
                "orientacao": "Houve perda de sinal móvel durante o envio da transação. É necessário reiniciar a maquininha ou reposicionar em local com melhor cobertura celular."
            },
            {
                "id_transacao": "TXN-43980",
                "data": "2026-09-17",
                "hora": "14:00",
                "valor": 890.00,
                "modalidade": "Crédito à Vista",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            }
        ],
        "chamados": [
            {
                "protocolo": "GET-2026-5512",
                "tipo": "Suporte de Conectividade",
                "motivo": "Chip 3G Tim sem sinal há 3 dias na Get Clássica (POS-4410)",
                "data_abertura": "2026-09-19",
                "status": "PENDENTE_CLIENTE",
                "data_agendamento": None,
                "periodo": None,
                "tecnico_responsavel": None,
                "observacoes": "Aguardando confirmação de endereço para envio de novo chip 4G multi-operadora."
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
        "historico_financeiro": [
            {
                "data": "2026-09-22",
                "total_bruto": 12800.00,
                "total_liquido": 12416.00,
                "quantidade_vendas": 114,
                "detalhes": [
                    {"tipo": "Crédito", "valor": 8200.00, "taxa_mdr": "2.4%"},
                    {"tipo": "Débito", "valor": 4600.00, "taxa_mdr": "1.2%"}
                ],
                "prazo_liquidacao": "D+0 (Antecipação Automática)",
                "previsao_deposito": "Antecipação Automática contratada: valor de R$ 12.416,00 creditado hoje às 10:00 na conta Itaú (Ag: 8877, CC: 33221-1)."
            },
            {
                "data": "2026-09-21",
                "total_bruto": 10950.00,
                "total_liquido": 10621.50,
                "quantidade_vendas": 98,
                "detalhes": [
                    {"tipo": "Crédito", "valor": 7100.00, "taxa_mdr": "2.4%"},
                    {"tipo": "Débito", "valor": 3850.00, "taxa_mdr": "1.2%"}
                ],
                "prazo_liquidacao": "D+0 (Antecipação Automática)",
                "previsao_deposito": "Depositado em 2026-09-21 às 10:00 na conta Itaú (Ag: 8877, CC: 33221-1)."
            },
            {
                "data": "2026-09-20",
                "total_bruto": 8200.00,
                "total_liquido": 7956.00,
                "quantidade_vendas": 73,
                "detalhes": [
                    {"tipo": "Crédito", "valor": 5500.00, "taxa_mdr": "2.4%"},
                    {"tipo": "Débito", "valor": 2700.00, "taxa_mdr": "1.2%"}
                ],
                "prazo_liquidacao": "D+0 (Antecipação Automática)",
                "previsao_deposito": "Depositado em 2026-09-20 às 10:00 na conta Itaú (Ag: 8877, CC: 33221-1)."
            }
        ],
        "transacoes": [
            {
                "id_transacao": "TXN-50190",
                "data": "2026-09-22",
                "hora": "19:40",
                "valor": 340.00,
                "modalidade": "Crédito",
                "bandeira": "Visa",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            },
            {
                "id_transacao": "TXN-50175",
                "data": "2026-09-22",
                "hora": "18:10",
                "valor": 520.00,
                "modalidade": "Crédito Parcelado",
                "bandeira": "Mastercard",
                "status": "AGUARDANDO_APROVACAO",
                "codigo_recusa": None,
                "motivo_tecnico": "Aguardando confirmação do banco emissor",
                "orientacao": "A transação está em análise. Normalmente confirmada em até 2 horas. Não tente reprocessar para evitar duplicidade."
            },
            {
                "id_transacao": "TXN-50160",
                "data": "2026-09-21",
                "hora": "22:05",
                "valor": 95.00,
                "modalidade": "Débito",
                "bandeira": "Elo",
                "status": "RECUSADA",
                "codigo_recusa": "14",
                "motivo_tecnico": "Número do Cartão Inválido",
                "orientacao": "O número de cartão digitado manualmente era inválido. Oriente o cliente a tentar novamente pela aproximação (NFC) ou contato com o chip."
            },
            {
                "id_transacao": "TXN-50140",
                "data": "2026-09-21",
                "hora": "20:30",
                "valor": 780.00,
                "modalidade": "Crédito",
                "bandeira": "Amex",
                "status": "APROVADA",
                "codigo_recusa": None,
                "motivo_tecnico": "Transação autorizada com sucesso",
                "orientacao": None
            }
        ],
        "chamados": []
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

    # 3. Match por dígitos de CPF ou CNPJ (suporta CPF exato ou contido na mensagem com datas/códigos)
    digits_only = re.sub(r"\D", "", raw)
    if digits_only and len(digits_only) >= 8:
        for key, data in _CLIENT_DATABASE.items():
            cpf_digits = re.sub(r"\D", "", data.get("cpf", ""))
            if cpf_digits and (digits_only == cpf_digits or cpf_digits in digits_only):
                return key, data

            cnpj_digits = re.sub(r"\D", "", data.get("cnpj", ""))
            if cnpj_digits and (digits_only == cnpj_digits or cnpj_digits in digits_only):
                return key, data

    return None

_ticket_sequence = 2000


@tool
def consultar_vendas_e_liquidacao(user_id: str, data: Optional[str] = None) -> str:
    """
    Consulta o extrato de vendas e a previsão de depósito bancário do cliente.
    Quando 'data' não for informada, retorna todos os dias disponíveis no histórico.
    Quando 'data' for informada (formato YYYY-MM-DD), retorna apenas aquele dia específico.
    Use quando o cliente perguntar sobre depósito, recebíveis ou histórico de vendas.

    Args:
        user_id: Identificador do cliente (ex: 'cliente1988')
        data: Data específica no formato YYYY-MM-DD (opcional). Se omitida, retorna todo o histórico.
    """
    cliente = _CLIENT_DATABASE.get(user_id)
    if not cliente:
        return f"Cliente com identificador '{user_id}' não localizado na base de credenciamento Getnet."

    historico = cliente.get("historico_financeiro", [])
    conta = cliente["conta_bancaria"]

    if not historico:
        return f"Nenhum histórico financeiro encontrado para o cliente '{user_id}'."

    # Filtra por data específica, se informada
    mais_recente = max(historico, key=lambda x: x["data"]) if historico else None
    data_recente = mais_recente["data"] if mais_recente else None

    aviso_data = ""
    if data:
        registros = [r for r in historico if r["data"] == data]
        if not registros:
            # Caso a data informada não conste, retorna o histórico completo e avisa o modelo com transparência
            aviso_data = (
                f"ℹ️ Informação do Banco de Dados: Não constam lançamentos de vendas para a data {data}. "
                f"O fechamento de vendas mais recente registrado no cadastro do cliente é de {data_recente}.\n"
            )
            registros = historico
    else:
        registros = historico  # Retorna todo o histórico

    linhas = [f"📊 Histórico Financeiro — {cliente['nome']} (ID: {user_id})"]
    linhas.append(f"Conta de Liquidação: {conta['banco']}, Ag: {conta['agencia']}, CC: {conta['conta']}")
    if data_recente:
        linhas.append(f"Fechamento de vendas mais recente no cadastro: {data_recente}\n")
    if aviso_data:
        linhas.append(aviso_data)

    for r in sorted(registros, key=lambda x: x["data"], reverse=True):
        tag_recente = " [Fechamento Mais Recente Registrado]" if r["data"] == data_recente else ""
        detalhes_str = " | ".join(
            f"{d['tipo']}: R$ {d['valor']:.2f} (MDR {d['taxa_mdr']})" for d in r["detalhes"]
        ) if r["detalhes"] else "Sem movimentações"

        linhas.append(
            f"📅 Data: {r['data']}{tag_recente}\n"
            f"   Bruto: R$ {r['total_bruto']:.2f} | Líquido: R$ {r['total_liquido']:.2f} | Qtd: {r['quantidade_vendas']} venda(s)\n"
            f"   Modalidades: {detalhes_str}\n"
            f"   Prazo: {r['prazo_liquidacao']}\n"
            f"   {r['previsao_deposito']}"
        )

    return "\n\n".join(linhas)


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
def consultar_transacoes_e_erros(
    user_id: str,
    id_transacao: Optional[str] = None,
    status: Optional[str] = None,
    data: Optional[str] = None,
) -> str:
    """
    Consulta o histórico de transações do cliente com filtragem flexível.
    - Sem filtros: retorna todas as transações disponíveis.
    - Com 'id_transacao': busca diretamente aquela transação específica.
    - Com 'status': filtra por estado (APROVADA, RECUSADA, AGUARDANDO_APROVACAO, CANCELADA, ESTORNADA).
    - Com 'data' (YYYY-MM-DD): filtra transações daquele dia.
    Os filtros podem ser combinados.
    Use quando o cliente informar que a maquininha está recusando transações ou quiser consultar uma transação.

    Args:
        user_id: Identificador do cliente (ex: 'cliente1988')
        id_transacao: ID específico da transação (ex: 'TXN-99821'). Opcional.
        status: Filtro de status (ex: 'RECUSADA'). Opcional.
        data: Data no formato YYYY-MM-DD. Opcional.
    """
    cliente = _CLIENT_DATABASE.get(user_id)
    if not cliente:
        return f"Cliente com identificador '{user_id}' não localizado."

    transacoes = cliente.get("transacoes", [])
    if not transacoes:
        return f"Nenhuma transação encontrada para o cliente '{user_id}'."

    # Aplica filtros progressivamente
    resultado = transacoes

    if id_transacao:
        resultado = [t for t in resultado if t["id_transacao"].lower() == id_transacao.strip().lower()]
        if not resultado:
            return f"Transação '{id_transacao}' não encontrada para o cliente '{cliente['nome']}'."

    if status:
        resultado = [t for t in resultado if t["status"].upper() == status.strip().upper()]

    if data:
        resultado = [t for t in resultado if t["data"] == data]

    if not resultado:
        filtros_usados = []
        if status:
            filtros_usados.append(f"status={status}")
        if data:
            filtros_usados.append(f"data={data}")
        return (
            f"Nenhuma transação encontrada para o cliente '{cliente['nome']}' "
            f"com os filtros: {', '.join(filtros_usados) or 'nenhum'}."
        )

    # Ordenar por data e hora (mais recente primeiro)
    resultado = sorted(resultado, key=lambda t: (t["data"], t["hora"]), reverse=True)

    linhas = [f"📑 Transações — {cliente['nome']} (ID: {user_id}) | Total encontrado: {len(resultado)}"]

    for t in resultado:
        status_icon = {
            "APROVADA": "✅",
            "RECUSADA": "❌",
            "AGUARDANDO_APROVACAO": "⏳",
            "CANCELADA": "🚫",
            "ESTORNADA": "↩️",
        }.get(t["status"], "•")

        recusa_info = f" — Código {t['codigo_recusa']}: {t['motivo_tecnico']}" if t["codigo_recusa"] else f" — {t['motivo_tecnico']}"
        orientacao_str = f"\n   Orientação: {t['orientacao']}" if t.get("orientacao") else ""

        linhas.append(
            f"{status_icon} [{t['status']}] {t['id_transacao']} — {t['data']} às {t['hora']}\n"
            f"   Valor: R$ {t['valor']:.2f} ({t['modalidade']} — {t['bandeira']})"
            f"{recusa_info}"
            f"{orientacao_str}"
        )

    return "\n\n".join(linhas)


@tool
def consultar_chamados_suporte(
    user_id: str,
    protocolo: Optional[str] = None,
) -> str:
    """
    Consulta o histórico e status de chamados técnicos, ordens de serviço, visitas agendadas e solicitações de manutenção abertas pelo cliente.
    Use SEMPRE que o cliente perguntar sobre status de chamados anteriores, agendamento de visita técnica,
    reagendamento de visita, troca de máquina ou solicitações de suporte em andamento.

    Args:
        user_id: Identificador do cliente (ex: 'cliente1988').
        protocolo: Número de protocolo opcional para consulta pontual de chamado específico (ex: 'GET-2026-8819').
    """
    if user_id not in _CLIENT_DATABASE:
        return f"Erro: Cliente '{user_id}' não encontrado na base de dados de suporte."

    cliente = _CLIENT_DATABASE[user_id]
    chamados = cliente.get("chamados", [])

    if not chamados:
        return (
            f"📋 Consulta de Chamados — {cliente['nome']} ({user_id})\n"
            f"Nenhum chamado técnico ou ordem de serviço encontrada em aberto para este cadastro."
        )

    # Filtro por protocolo se especificado
    if protocolo:
        prot_clean = protocolo.strip().upper()
        chamados_filtrados = [
            c for c in chamados
            if prot_clean in c.get("protocolo", "").upper()
        ]
        if not chamados_filtrados:
            return (
                f"Chamado com protocolo '{protocolo}' não localizado para o cliente {cliente['nome']} ({user_id}).\n"
                f"Total de chamados ativos encontrados no cadastro: {len(chamados)}."
            )
        chamados = chamados_filtrados

    linhas = [
        f"📋 Consulta de Chamados e Ordens de Serviço — {cliente['nome']} ({user_id})\n"
        f"Total de chamados localizados: {len(chamados)}\n"
        f"{'-' * 60}"
    ]

    for ch in chamados:
        status_icon = (
            "🟢" if ch.get("status") in ["CONCLUIDO", "RESOLVIDO"]
            else "🟡" if ch.get("status") in ["AGENDADO", "EM_TRANSITO"]
            else "🔵"
        )
        agendamento_info = ""
        if ch.get("data_agendamento"):
            agendamento_info = (
                f"\n   📅 Visita Técnica Agendada: {ch.get('data_agendamento')} — Período: {ch.get('periodo', 'Comercial')}"
            )
        if ch.get("tecnico_responsavel"):
            agendamento_info += f" (Técnico: {ch.get('tecnico_responsavel')})"

        obs_info = f"\n   ℹ️ Observações: {ch.get('observacoes')}" if ch.get("observacoes") else ""

        linhas.append(
            f"{status_icon} Protocolo: {ch.get('protocolo')} | Status: {ch.get('status')}\n"
            f"   Tipo: {ch.get('tipo')}\n"
            f"   Motivo: {ch.get('motivo')}\n"
            f"   Data de Abertura: {ch.get('data_abertura')}"
            f"{agendamento_info}"
            f"{obs_info}"
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
    Use quando o cliente solicitar reposição de bobinas de papel térmico, insumos/suprimentos, troca de POS/leitor com defeito ou quando o problema não puder ser resolvido remotamente.
    
    Args:
        user_id: Identificador do cliente
        motivo: Descrição clara do problema técnico ou solicitação (ex: 'Reposição de bobinas de papel térmico para terminal', 'Troca de leitor de cartão')
        prioridade: 'baixa', 'normal' ou 'alta'
    """
    if not user_id or user_id not in _CLIENT_DATABASE:
        return (
            f"❌ Não foi possível registrar o chamado técnico: cliente '{user_id}' não identificado ou não localizado na base Getnet.\n"
            f"Por favor, solicite a identificação do cliente (CPF/CNPJ) antes de prosseguir com a abertura do chamado."
        )

    global _ticket_sequence
    _ticket_sequence += 1
    ticket_id = f"GET-{_ticket_sequence}"

    # Registra no histórico do cliente na memória simulada
    novo_chamado = {
        "protocolo": ticket_id,
        "tipo": "Chamado Técnico",
        "motivo": motivo,
        "data_abertura": datetime.now().strftime("%Y-%m-%d"),
        "status": "ABERTO",
        "data_agendamento": None,
        "periodo": None,
        "tecnico_responsavel": None,
        "observacoes": f"Chamado registrado com prioridade {prioridade.upper()}. Prazo de atendimento em até 24 horas úteis."
    }
    _CLIENT_DATABASE[user_id].setdefault("chamados", []).append(novo_chamado)

    nome_cliente = _CLIENT_DATABASE[user_id].get("nome", user_id)
    return (
        f"✅ Chamado Técnico Getnet Registrado com Sucesso!\n"
        f"• Protocolo: {ticket_id}\n"
        f"• Cliente: {nome_cliente} ({user_id})\n"
        f"• Motivo: {motivo}\n"
        f"• Prioridade: {prioridade.upper()}\n"
        f"• Prazo de Atendimento: Até 24 horas úteis."
    )


SUPPORT_TOOLS = [
    consultar_vendas_e_liquidacao,
    consultar_status_maquininhas,
    consultar_transacoes_e_erros,
    consultar_chamados_suporte,
    abrir_chamado_suporte,
]

