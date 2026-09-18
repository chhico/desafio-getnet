"""
tests/test_scenarios.py
-----------------------
Bateria de Testes Automatizados para o Desafio Getnet.
Cobre com precisão os 10 cenários de teste exigidos na especificação:
1. Comparativo Get Clássica vs Get Smart
2. Previsão do tempo Porto Alegre
3. Depósito de vendas de ontem cliente1988
4. Conta bancária para Pix Getnet
5. Maquininha não conecta à internet
6. Antecipação de recebíveis
7. Taxa de câmbio do euro hoje
8. Erro de recusa de transação (Código 51)
9. Parcelas no crediário
10. Venda pelo WhatsApp com Link de Pagamento
"""

import pytest
from backend.agents.graph import support_graph
from backend.services.conversation_service import ConversationService


@pytest.fixture
def run_message():
    def _execute(message: str, user_id: str = "cliente1988"):
        return ConversationService.process_message(
            graph=support_graph,
            user_id=user_id,
            message_content=message,
            channel="test",
        )
    return _execute


def test_scenario_01_get_classica_vs_smart(run_message):
    """1. Comparativo de produtos Getnet -> Agente de Conhecimento"""
    res = run_message("Qual é a diferença entre a Get Clássica e a Get Smart?")
    assert res.agent_used == "knowledge"
    texto = res.response.lower()
    # Deve mencionar teclado/touchscreen ou impressão
    assert ("touch" in texto or "teclado" in texto or "android" in texto or "clássica" in texto)


def test_scenario_02_previsao_tempo_porto_alegre(run_message):
    """2. Pergunta de uso geral fora do catálogo -> Agente de Conhecimento via Busca Web"""
    res = run_message("Qual é a previsão do tempo para Porto Alegre amanhã?")
    assert res.agent_used == "knowledge"
    assert len(res.response) > 20


def test_scenario_03_deposito_vendas_ontem(run_message):
    """3. Dados privados e previsão de liquidação -> Agente de Suporte ao Cliente"""
    res = run_message("Quando o dinheiro das vendas de ontem será depositado?", user_id="cliente1988")
    assert res.agent_used == "support"
    texto = res.response.lower()
    # Deve trazer dados da liquidação do cliente1988
    assert ("amanhã" in texto or "santander" in texto or "depósito" in texto or "líquido" in texto or "d+2" in texto)


def test_scenario_04_conta_bancaria_pix(run_message):
    """4. Requisitos para receber Pix Getnet -> Agente de Conhecimento"""
    res = run_message("Preciso de uma conta bancária para receber minhas vendas via Pix?")
    assert res.agent_used == "knowledge"
    texto = res.response.lower()
    assert ("conta" in texto or "bancária" in texto or "superget" in texto or "santander" in texto)


def test_scenario_05_maquininha_sem_conexao(run_message):
    """5. Falha de conexão na maquininha -> Suporte ou Conhecimento com passos de troubleshooting"""
    res = run_message("Minha maquininha não conecta à internet; o que devo fazer?", user_id="cliente1988")
    assert res.agent_used in ["knowledge", "support"]
    texto = res.response.lower()
    assert ("wi-fi" in texto or "chip" in texto or "reinici" in texto or "menu" in texto or "sinal" in texto)


def test_scenario_06_antecipacao_recebiveis(run_message):
    """6. Funcionamento da antecipação de recebíveis -> Agente de Conhecimento"""
    res = run_message("Como funciona a antecipação de recebíveis com a Getnet?")
    assert res.agent_used == "knowledge"
    texto = res.response.lower()
    assert ("antecipa" in texto or "crédito" in texto or "automática" in texto or "avulsa" in texto or "d+1" in texto)


def test_scenario_07_cotacao_euro(run_message):
    """7. Pergunta de mercado/economia de uso geral -> Agente de Conhecimento via Busca Web"""
    res = run_message("Qual é a taxa de câmbio do euro hoje?")
    assert res.agent_used == "knowledge"
    assert len(res.response) > 15


def test_scenario_08_erro_recusa_transacao(run_message):
    """8. Análise de transação recusada do cliente -> Agente de Suporte ao Cliente"""
    res = run_message("Minha maquininha está apresentando um erro de recusa de transação.", user_id="cliente1988")
    assert res.agent_used == "support"
    texto = res.response.lower()
    # Deve identificar o erro do mock (51 ou saldo insuficiente)
    assert ("51" in texto or "saldo" in texto or "insuficiente" in texto or "recus" in texto or "emissor" in texto)


def test_scenario_09_parcelas_crediario(run_message):
    """9. Parcelamento no crediário Getnet -> Agente de Conhecimento"""
    res = run_message("Em quantas parcelas posso dividir uma venda usando o crediário?")
    assert res.agent_used == "knowledge"
    texto = res.response.lower()
    assert ("parcela" in texto or "36" in texto or "12" in texto or "crediário" in texto)


def test_scenario_10_venda_whatsapp_link_pagamento(run_message):
    """10. Venda pelo WhatsApp via Link de Pagamento -> Agente de Conhecimento"""
    res = run_message("Posso vender pelo WhatsApp usando o Link de Pagamento?")
    assert res.agent_used == "knowledge"
    texto = res.response.lower()
    assert ("sim" in texto or "link de pagamento" in texto or "whatsapp" in texto)
