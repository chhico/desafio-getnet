"""
tests/test_05_fluxos_criticos.py
---------------------------------
Bateria de Testes de Fluxos Críticos e Casos de Borda (Corner Cases).
Cobre especificamente os 22 cenários mapeados onde o fluxo conversacional
anteriormente apresentava desvios, loops de estado ou falsos positivos:

1. Transbordo para Humano durante espera de documento (Quebra de Loop/Deadlock)
2. Incidente Crítico (Fogo/Sinistro) durante espera de documento
3. Lojista relatando contestação de fraude/chargeback sem ser bloqueado pelo Guardrail
4. Narrativa de suporte com citação a 'telefone da getnet' sem acionar Fast-Path indevido
5. Pergunta técnica curta inline com documento ('cliente1988 erro 51') preservada
6. Encerramento cordial durante pending_escalation ('já resolvi, obrigado, tchau')
7. Troca de assunto conceitual durante espera de identificação de suporte
8. Menção de CPF de comprador/cliente final no balcão sem bloqueio de sigilo
9. Pergunta composta multiobjetivo (Conhecimento + Suporte) acolhida com sucesso
10. Solicitação de humano com documento informado no primeiro turno sem triagem redundante
11. Frustração com assistente virtual pula triagem e transborda imediato
12. Handoff flexível sem documento gera protocolo visitante oficial sem bloqueio
13. Solicitação vaga de abertura de chamado técnico exige qualificação prévia do sintoma
14. Consulta de status de chamado por número de protocolo existente (GET-2026-8819)
15. Dúvida sobre regra comercial e meta de faturamento do Aluguel Zero roteada para Knowledge
16. Consulta a transação inexistente (TXN-00000) retorna aviso transparente sem alucinação
17. Saudação composta com relato de defeito técnico não é engolida pelo Fast-Path e vai para Support
18. Tutorial passo a passo de estorno/cancelamento na maquininha roteado para Knowledge
19. Consulta de vendas em data sem movimentação informa ausência e fechamento mais recente
20. Orientação técnica e comercial sobre recusa de cartão com erro 51 no balcão da loja
21. Recuperação de dados e confirmação de comprovante de transação aprovada (TXN-99810)
22. Prospect sem cadastro consultando taxas do plano Receba Já atendido por Knowledge com fontes
"""

import pytest
from typing import Callable
from backend.domain.schemas import ChatResponse


class TestFluxosCriticosECornerCases:
    """Valida os 22 cenários críticos de fluxos conversacionais e casos de borda."""

    def test_cenario_01_deadlock_transbordo_em_awaiting_id(self, run_message: Callable[..., ChatResponse]):
        """Cenário 1: Usuário em espera de documento pede atendente humano e não deve cair em loop de documento não localizado."""
        thread = "critico_cenario_01"
        res1 = run_message("Quero consultar minhas vendas de ontem", thread_id=thread)
        assert res1.agent_used == "support"
        assert ("documento" in res1.response.lower() or "cpf" in res1.response.lower() or "código" in res1.response.lower())

        # Turno 2: Não tem o documento e solicita humano
        res2 = run_message("Não sei meu CPF de cabeça, quero falar com um atendente humano agora por favor", thread_id=thread)
        assert res2.agent_used == "escalation"
        assert "não encontramos" not in res2.response.lower()

    def test_cenario_02_incidente_critico_durante_espera_de_documento(self, run_message: Callable[..., ChatResponse]):
        """Cenário 2: Incidente crítico de perigo físico/sinistro tem prioridade sobre espera de documento."""
        thread = "critico_cenario_02"
        res1 = run_message("Minha maquininha não está ligando", thread_id=thread)
        assert res1.agent_used == "support"

        # Turno 2: Relato de incêndio / fumaça na maquininha
        res2 = run_message("Socorro! A máquina começou a pegar fogo na tomada e tem muita fumaça tóxica!", thread_id=thread)
        assert res2.agent_used == "escalation"
        assert "não encontramos" not in res2.response.lower()

    def test_cenario_03_lojista_relatando_contestacao_fraude_nao_bloqueado(self, run_message: Callable[..., ChatResponse]):
        """Cenário 3: Lojista relatando contestação de chargeback com menção a fraude não deve ser bloqueado pelo Guardrail."""
        thread = "critico_cenario_03"
        res = run_message(
            "Recebi uma contestação da operadora dizendo que houve fraude na maquininha do meu caixa, como faço para enviar comprovante e me defender?",
            thread_id=thread,
        )
        assert res.agent_used != "guardrail_block"

    def test_cenario_04_narrativa_com_telefone_nao_dispara_fast_path(self, run_message: Callable[..., ChatResponse]):
        """Cenário 4: Menção contextual a 'telefone da getnet' em dúvida de transação não deve disparar lista estática de números."""
        thread = "critico_cenario_04"
        res = run_message(
            "Liguei no telefone da Getnet para pedir o cancelamento da transação TXN-99821 e me orientaram a ver o motivo da recusa aqui no chat, pode verificar para mim?",
            thread_id=thread,
        )
        assert res.category != "Canais de Atendimento"
        # Deve seguir para o fluxo de suporte/identificação/transação
        assert res.agent_used in ["support", "knowledge"]

    def test_cenario_05_pergunta_tecnica_inline_com_documento_preservada(self, run_message: Callable[..., ChatResponse]):
        """Cenário 5: Pergunta técnica curta enviada junto com o identificador ('cliente1988 erro 51') é preservada e respondida."""
        thread = "critico_cenario_05"
        res = run_message("cliente1988 erro 51", thread_id=thread)
        assert res.agent_used == "support"
        texto = res.response.lower()
        # Deve analisar o motivo do erro 51 (saldo insuficiente / limite)
        assert ("saldo" in texto or "limite" in texto or "51" in texto or "recus" in texto)

    def test_cenario_06_encerramento_e_agradecimento_durante_pending_escalation(self, run_message: Callable[..., ChatResponse]):
        """Cenário 6: Cliente em pending_escalation que agradece e encerra ('já resolvi, obrigado, tchau') não é forçado a digitar CPF."""
        thread = "critico_cenario_06"
        res1 = run_message("Quero falar com um atendente humano", thread_id=thread)
        assert res1.agent_used == "escalation"

        res2 = run_message("Muito obrigado, já consegui resolver por aqui sozinho, tchau!", thread_id=thread)
        # Não deve emitir mensagem de documento não localizado
        assert "não encontramos" not in res2.response.lower()

    def test_cenario_07_troca_de_assunto_conceitual_durante_espera_de_documento(self, run_message: Callable[..., ChatResponse]):
        """Cenário 7: Usuário em espera de documento que muda de assunto para catálogo/produto é roteado para knowledge."""
        thread = "critico_cenario_07"
        res1 = run_message("Quero ver meu extrato financeiro", thread_id=thread)
        assert res1.agent_used == "support"

        # Turno 2: Pergunta conceitual de catálogo
        res2 = run_message("Deixa o extrato pra depois. Me tira uma dúvida: qual a diferença entre a Get Smart e a Get Clássica?", thread_id=thread)
        assert res2.agent_used == "knowledge"
        texto = res2.response.lower()
        assert ("get smart" in texto or "get clássica" in texto or "bobina" in texto or "touch" in texto or "android" in texto)

    def test_cenario_08_mencao_cpf_comprador_balcao_nao_bloqueia_sessao(self, run_message: Callable[..., ChatResponse]):
        """Cenário 8: Lojista autenticado citando CPF do comprador no balcão para checar recusa não tem a sessão bloqueada."""
        thread = "critico_cenario_08"
        # Autentica primeiro como cliente1988
        run_message("Preciso ver meu extrato", thread_id=thread)
        run_message("cliente1988", thread_id=thread)

        # Cita o CPF de um cliente da loja que passou o cartão
        res = run_message(
            "O cartão do cliente com CPF 222.333.444-55 foi recusado aqui no balcão da loja, você consegue ver por que a transação dele não passou?",
            thread_id=thread,
        )
        assert res.agent_used == "support"
        # Não deve disparar o bloqueio de segurança de sigilo bancário
        assert "acesso não permitido por segurança" not in res.response.lower()

    def test_cenario_09_pergunta_composta_multiobjetivo_atendimento(self, run_message: Callable[..., ChatResponse]):
        """Cenário 9: Pergunta composta (bobina + status de maquininha) é acolhida sem travar ou gerar erro de execução."""
        thread = "critico_cenario_09"
        res = run_message(
            "Como troco a bobina de papel na Get Smart e aproveita para consultar se a minha maquininha POS-8812 do cliente1988 está online?",
            thread_id=thread,
        )
        assert res.agent_used in ["knowledge", "support"]
        assert len(res.response) > 30

    def test_cenario_10_escalonamento_com_documento_imediato_sem_retencao_redundante(self, run_message: Callable[..., ChatResponse]):
        """Cenário 10: Solicitação de humano que já inclui documento válido no primeiro turno avança para transferência e protocolo."""
        thread = "critico_cenario_10"
        res = run_message("Preciso falar com um atendente humano urgente, meu documento é cliente1988", thread_id=thread)
        assert res.agent_used == "escalation"
        assert "GET-2026-" in res.response
        assert ("conectando com atendimento humano" in res.response.lower() or "protocolo" in res.response.lower())

    def test_cenario_11_frustracao_com_ia_transborda_imediato_sem_perguntar_assunto(self, run_message: Callable[..., ChatResponse]):
        """Cenário 11: Frustração/irritação com o robô ('cansei dessa IA inútil') pula a triagem de assunto e transfere no Turno 1."""
        thread = "critico_cenario_11"
        res = run_message("Cansei dessa IA inútil, robô burro que não ajuda nada, me passa pra alguém de verdade agora!", thread_id=thread)
        assert res.agent_used == "escalation"
        assert "GET-2026-" in res.response
        assert ("conectando com atendimento humano" in res.response.lower() or "atendente designado" in res.response.lower())

    def test_cenario_12_handoff_sem_documento_gera_protocolo_visitante_sem_bloqueio(self, run_message: Callable[..., ChatResponse]):
        """Cenário 12: Usuário que não tem ou não informa documento transborda com protocolo oficial sem ser bloqueado."""
        thread = "critico_cenario_12"
        # Turno 1: Pedido genérico
        res1 = run_message("Quero falar com um atendente humano", thread_id=thread)
        assert res1.agent_used == "escalation"
        assert "sobre qual assunto" in res1.response.lower()

        # Turno 2: Informa o assunto e expressa preferência pela transferência humana mesmo sem ter documento prévio
        res2 = run_message("É sobre uma proposta comercial urgente, mas ainda não sou cliente, transfere para um especialista humano por favor", thread_id=thread)
        assert res2.agent_used == "escalation"
        assert "GET-2026-" in res2.response
        assert ("conectando com atendimento humano" in res2.response.lower() or "atendente designado" in res2.response.lower())
        assert "não encontramos" not in res2.response.lower()

    def test_cenario_13_solicitacao_vaga_de_chamado_exige_qualificacao(self, run_message: Callable[..., ChatResponse]):
        """Cenário 13: Solicitação vaga de chamado ('abram um chamado') acolhe o cliente e qualifica o defeito antes de abrir OS."""
        thread = "critico_cenario_13"
        # Turno 1: Autentica o cliente e faz o pedido vago de chamado técnico
        run_message("Preciso de suporte para minha maquininha, sou o cliente1988", thread_id=thread)
        res1 = run_message("Abram um chamado técnico para mim agora por favor", thread_id=thread)
        assert res1.agent_used == "support"
        # Não deve abrir chamado presuntivo genérico sem motivo; deve pedir qualificação do problema
        texto1 = res1.response.lower()
        assert ("qual" in texto1 or "problema" in texto1 or "defeito" in texto1 or "sintoma" in texto1 or "acontecendo" in texto1)

        # Turno 2: Cliente qualifica o defeito real
        res2 = run_message("A bateria não segura mais carga e a máquina desliga fora da base", thread_id=thread)
        assert res2.agent_used == "support"
        assert ("GET-2026-" in res2.response or "chamado" in res2.response.lower() or "ordem de serviço" in res2.response.lower())

    def test_cenario_14_consulta_status_chamado_por_protocolo_existente(self, run_message: Callable[..., ChatResponse]):
        """Cenário 14: Lojista que consulta chamado por protocolo exato ('GET-2026-8819') recebe status real sem erro de documento."""
        thread = "critico_cenario_14"
        res = run_message("Sou o cliente1988 e quero saber o andamento do meu chamado GET-2026-8819", thread_id=thread)
        assert res.agent_used == "support"
        texto = res.response.lower()
        # Deve consultar e retornar dados reais do chamado de cliente1988
        assert ("8819" in texto or "agendado" in texto or "marcos oliveira" in texto or "visita" in texto)
        assert "não encontramos" not in texto

    def test_cenario_15_regra_comercial_aluguel_zero_vai_para_knowledge(self, run_message: Callable[..., ChatResponse]):
        """Cenário 15: Pergunta sobre política comercial de Aluguel Zero vai para Knowledge sem exigir CPF de extrato."""
        thread = "critico_cenario_15"
        res = run_message(
            "Se em determinado mês minhas vendas caírem abaixo da meta de faturamento do Aluguel Zero, qual valor de aluguel eu terei que pagar?",
            thread_id=thread,
        )
        assert res.agent_used == "knowledge"
        assert "documento não localizado" not in res.response.lower()
        texto = res.response.lower()
        assert ("aluguel" in texto or "meta" in texto or "faturamento" in texto or "isenção" in texto or "isencao" in texto)

    def test_cenario_16_consulta_transacao_inexistente_retorna_aviso_transparente(self, run_message: Callable[..., ChatResponse]):
        """Cenário 16: Consulta a transação inexistente ('TXN-00000') retorna aviso transparente sem inventar valores ou autorizações."""
        thread = "critico_cenario_16"
        run_message("cliente1988", thread_id=thread)
        res = run_message("Por favor, consulte para mim o status e valor da transação TXN-00000", thread_id=thread)
        assert res.agent_used == "support"
        texto = res.response.lower()
        assert ("não encontrada" in texto or "não localizada" in texto or "não consta" in texto or "nenhuma transação" in texto or "não foi encontrada" in texto)

    def test_cenario_17_saudacao_composta_com_defeito_tecnico_vai_para_support(self, run_message: Callable[..., ChatResponse]):
        """Cenário 17: Saudação combinada com defeito físico ('Boa tarde, a tela da Get Smart quebrou') não cai em Fast-Path de saudação."""
        thread = "critico_cenario_17"
        res = run_message(
            "Boa tarde, tudo bem? A tela da minha Get Smart quebrou e parou de responder ao toque, preciso de reparo técnico urgente.",
            thread_id=thread,
        )
        assert res.agent_used == "support"
        # Não deve ser o texto genérico do Fast-Path de boas-vindas
        assert "como posso ajudar o seu negócio hoje?" not in res.response.lower()

    def test_cenario_18_tutorial_estorno_maquininha_vai_para_knowledge(self, run_message: Callable[..., ChatResponse]):
        """Cenário 18: Procedimento operacional de estorno no teclado da maquininha é tratado como tutorial em Knowledge."""
        thread = "critico_cenario_18"
        res = run_message(
            "Como faço para fazer um cancelamento ou estorno de venda direto no teclado da maquininha Get Smart?",
            thread_id=thread,
        )
        assert res.agent_used == "knowledge"
        texto = res.response.lower()
        assert ("menu" in texto or "cancelamento" in texto or "estorno" in texto or "senha" in texto or "opção" in texto)

    def test_cenario_19_consulta_vendas_data_sem_movimentacao_transparente(self, run_message: Callable[..., ChatResponse]):
        """Cenário 19: Consulta a data sem movimentação (ex: 2026-09-15) relata ausência de registros sem inventar números."""
        thread = "critico_cenario_19"
        run_message("cliente1988", thread_id=thread)
        res = run_message("Qual foi o total das minhas vendas no dia 2026-09-15?", thread_id=thread)
        assert res.agent_used == "support"
        texto = res.response.lower()
        assert ("não há vendas" in texto or "não constam" in texto or "nenhuma venda" in texto or "não foram encontradas" in texto or "sem lançamentos" in texto)

    def test_cenario_20_orientacao_recusa_cartao_portador_codigo_51(self, run_message: Callable[..., ChatResponse]):
        """Cenário 20: Dúvida do lojista sobre o que dizer ao cliente com recusa código 51 é orientada como suporte a pagamentos."""
        thread = "critico_cenario_20"
        run_message("cliente1988", thread_id=thread)
        res = run_message(
            "Uma cliente passou o cartão e apareceu erro 51 no visor. O que eu como lojista devo falar para ela no balcão da loja?",
            thread_id=thread,
        )
        assert res.agent_used in ["support", "knowledge"]
        assert res.agent_used != "guardrail_block"
        texto = res.response.lower()
        assert ("saldo" in texto or "limite" in texto or "outro cartão" in texto or "outra forma" in texto or "emissor" in texto or "método" in texto or "metodo" in texto)

    def test_cenario_21_recuperacao_dados_comprovante_transacao_aprovada(self, run_message: Callable[..., ChatResponse]):
        """Cenário 21: Recuperação de dados da transação aprovada TXN-99810 quando acaba o papel da bobina."""
        thread = "critico_cenario_21"
        run_message("cliente1988", thread_id=thread)
        res = run_message(
            "A bobina acabou de terminar na impressão e não saiu o comprovante da transação TXN-99810. Pode me confirmar se foi aprovada e qual o valor dela?",
            thread_id=thread,
        )
        assert res.agent_used == "support"
        texto = res.response.lower()
        assert ("aprovada" in texto or "autorizada" in texto or "confirmada" in texto)
        assert "150" in texto

    def test_cenario_22_prospect_perguntando_taxas_sem_documento_atendido_por_knowledge(self, run_message: Callable[..., ChatResponse]):
        """Cenário 22: Novo comerciante sem cadastro prévio pergunta taxas do plano Receba Já e é atendido por Knowledge com fontes."""
        thread = "critico_cenario_22"
        res = run_message(
            "Quero saber quais são as taxas de débito e crédito no plano Receba Já para novos comerciantes, ainda não tenho cadastro com vocês.",
            thread_id=thread,
        )
        assert res.agent_used == "knowledge"
        assert "documento não localizado" not in res.response.lower()
        texto = res.response.lower()
        assert ("taxa" in texto or "receba já" in texto or "débito" in texto or "crédito" in texto)
        assert ("fontes consultadas" in texto or "fonte" in texto or ".txt" in texto or ".pdf" in texto or "getnet" in texto)


