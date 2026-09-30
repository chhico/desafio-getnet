# Diretrizes do Projeto (Spec-Driven & Agent Rules)

Este projeto segue rigorosamente a metodologia **Spec-Driven Development (SDD)** e **Evals-First**.
Todas as implementações, refatorações e sugestões de arquitetura devem obedecer às seguintes diretrizes:

---

## 1. Fonte da Verdade (Single Source of Truth)
- A especificação oficial deste projeto é o arquivo `desafio.md`.
- Nenhuma funcionalidade nova, agente ou ferramenta deve ser criada sem respaldo no `desafio.md` ou nos requisitos de bônus acordados.
- Em caso de dúvida sobre escopo, consulte o `desafio.md` antes de tomar decisões de código.

---

## 2. Integridade da Orquestração e Agentes
- **Motor de Orquestração:** LangGraph com máquina de estados (`StateGraph`) e memória conversacional multi-turnos via `MemorySaver`.
- **Agentes do Sistema:**
  1. `orchestrator_node` (Roteador): Analisa intenção semântica e histórico para rotear entre especialistas. Não gera respostas finais nem executa ferramentas de negócio.
  2. `knowledge_node` (Conhecimento): Especialista institucional Getnet. Consulta RAG local (ChromaDB), varredura web e DuckDuckGo. **Obrigatório citar fontes consultadas no rodapé da resposta.**
  3. `support_node` (Suporte ao Cliente): Exige validação de documento (CPF/ID) antes de expor dados privados. Opera com 5 ferramentas corporativas (`consultar_vendas_e_liquidacao`, `consultar_status_maquininhas`, `consultar_transacoes_e_erros`, `consultar_chamados_suporte`, `abrir_chamado_suporte`).
  4. `escalation_node` (Human Handoff): Transbordo para operadores humanos com triagem, classificação em 6 filas e geração de protocolo oficial (`GET-2026-XXXX`).
  5. `guardrail_node` (Segurança): Intercepta e bloqueia deterministicamente Prompt Injections, Jailbreaks, SQLi, fraudes e termos abusivos na entrada do grafo.

---

## 3. Qualidade de Código, Evals-First e Arquitetura de Testes (TDD)
- Qualquer alteração em lógica de agentes, ferramentas ou rotas da API **deve manter a suíte de testes 100% verde**.
- A suíte de testes é organizada em uma **Arquitetura Sequencial de 4 Camadas**:
  1. `tests/test_01_edital_scenarios.py`: 27 cenários oficiais e de bônus do edital (10 obrigatórios + 17 bônus).
  2. `tests/test_02_agents.py`: Testes unitários e comportamentais para os 5 especialistas (Guardrail, Orchestrator, Knowledge, Support, Escalation).
  3. `tests/test_03_tools_and_internal.py`: Ferramentas internas, Fast-Path regex, crawler web, admin upload e sincronização RAG SQLite.
  4. `tests/test_04_multiturn_harness.py`: 50 cenários de robustez conversacional profunda (3 a 6 turnos) com gravação progressiva e geração automática de Dossiê Executivo (Markdown e JSON).
- **Comandos de validação padrão no terminal:**
  - `pytest tests/test_01_edital_scenarios.py -v` (ou `pytest tests/test_scenarios.py -v`)
  - `pytest tests/test_02_agents.py -v` (Especialistas do Grafo)
  - `pytest tests/test_03_tools_and_internal.py -v` (Ferramentas e Métodos Internos)
  - `python tests/test_04_multiturn_harness.py` (ou `pytest tests/test_04_multiturn_harness.py -v`)
  - `pytest -v` (Bateria completa)
- **Relatórios Executivos:** Centralizados em `tests/reporters/dossier_generator.py` e gerados em `tests/reports/relatorio_*_latest.md` e `.json`.
- Nunca comente ou remova asserções de testes para "forçar" um teste a passar. Adapte a implementação para cumprir a asserção.

---

## 4. Contratos de API e Infraestrutura
- **Endpoint Principal:** `POST /api/v1/chat` validado estritamente pelos schemas Pydantic `ChatRequest` e `ChatResponse` em `backend/domain/schemas.py`.
- **Docker:** O projeto deve sempre compilar e subir com `docker compose up --build`. Mantenha os volumes `./bds` e `./fonte_de_dados` mapeados.
- **Frontend:** Desenvolvido em HTML5/CSS/JavaScript puro na pasta `frontend/`, sem dependências pesadas de build.
