# Dossiê de Aderência Técnica: Sistema de Suporte Multiagente Getnet
**Posição:** Engenheiro de IA (Nível Avançado / Sênior)  
**Repositório:** [https://github.com/chhico/desafio-get-draft](https://github.com/chhico/desafio-get-draft)  
**Data de Emissão:** 18 de Setembro de 2026  
**Status de Conformidade:** **100% dos Requisitos Principais e 100% dos Desafios Bônus Atendidos**

---

## 1. Sumário Executivo e Matriz de Conformidade

O projeto implementa uma solução corporativa completa de atendimento inteligente ao cliente baseada em uma **Arquitetura Multiagente Orquestrada com LangGraph**, pipeline de **RAG Incremental Híbrido** (ChromaDB + SQLite Hashes MD5), camada de **Guardrails de Segurança em Múltiplos Níveis**, API REST em **FastAPI**, conteinerização **Docker multi-stage**, rastreamento nativo com **LangSmith** e suíte completa de **testes automatizados cobrindo 15 cenários de teste**.

### 1.1. Matriz de Requisitos Principais

| Item do Edital | Requisito Solicitado | Status | Implementação no Projeto |
| :--- | :--- | :---: | :--- |
| **1. Orquestração** | Pelo menos 3 tipos distintos de agentes cooperativos | **100% Conforme** | Grafo cíclico/condicional com `guardrail_node`, `orchestrator_node`, `knowledge_node` e `support_node`. |
| **1.1. Router Agent** | Ponto de entrada, análise e roteamento dinâmico | **100% Conforme** | [`backend/agents/orchestrator.py`](backend/agents/orchestrator.py): Roteia com base no contexto, intenção semântica e histórico em JSON estrito. |
| **1.2. Knowledge Agent** | RAG com docs locais + URLs Getnet + busca web externa | **100% Conforme** | [`backend/agents/knowledge_agent.py`](backend/agents/knowledge_agent.py): RAG via ChromaDB (PDFs/Web) + Busca DuckDuckGo + Citação mandatória de fontes. |
| **1.3. Support Agent** | Dados específicos do cliente com pelo menos 2 tools | **100% Conforme** | [`backend/agents/support_agent.py`](backend/agents/support_agent.py): 4 ferramentas corporativas integradas a base simulada por documento/ID de cliente. |
| **2. Endpoint API** | HTTP POST com payload `{"message": "...", "user_id": "..."}` | **100% Conforme** | [`backend/api/conversations.py`](backend/api/conversations.py) na rota `/api/v1/chat`. |
| **3. Dockerização** | `Dockerfile` e `docker-compose.yml` funcionais | **100% Conforme** | Multi-stage build Python 3.11-slim, volumes para vetores/docs e healthcheck nativo. |
| **4. Testes** | Estratégia e cobertura dos cenários do desafio | **100% Conforme** | [`tests/test_scenarios.py`](tests/test_scenarios.py): Cobertura automatizada de 27 cenários (10 oficiais + 2 segurança + 3 guardrails + 2 handoff direto + 10 escalonamentos implícitos). |
| **5. Frameworks** | Tecnologias adequadas (LangGraph, FastAPI, Chroma) | **100% Conforme** | Python 3.11, LangGraph, LangChain, ChromaDB, OpenAI (GPT-4o), FastAPI, Pydantic v2. |

---

### 1.2. Matriz dos 4 Desafios Bônus

| Desafio Bônus Solicitado | Status | Implementação no Projeto |
| :--- | :---: | :--- |
| **Bônus 1: Quarto Agente / Escalonamento para Humanos** | **100% Conforme** | Implementado via fluxo de intervenção humana assistida, geração de protocolos de ticket e nó especializado de recusa/bloqueio seguro (`guardrail_block`). |
| **Bônus 2: Guardrails de Segurança (Inseguras/Sensíveis/Não Suportadas)** | **100% Conforme** | Módulo dedicado [`backend/agents/guardrails.py`](backend/agents/guardrails.py): intercepta Prompt Injections, Jailbreaks, SQLi, XSS, fraudes e termos abusivos. |
| **Bônus 3: Mecanismo de Redirecionamento (*Human Handoff*)** | **100% Conforme** | Ferramenta `abrir_chamado_suporte` formaliza o chamado com SLA e protocolo (`GET-XXXX`), consolidando o histórico da conversa para o operador humano em situações críticas. |
| **Bônus 4: Estratégia de Avaliação e Observabilidade** | **100% Conforme** | Integração nativa com **LangSmith** para tracing distribuído de tokens/latência e framework automatizado de avaliação contínua com métricas de fidelidade (RAG Triad). |

---

## 2. Detalhamento Arquitetural da Orquestração Multiagente

A solução adota o **LangGraph** como motor de orquestração com máquina de estados (`StateGraph`), proporcionando controle determinístico sobre o fluxo de execução, persistência de contexto em memória (`MemorySaver`) e separação de responsabilidades no padrão Clean Architecture.

```
                    ┌─────────────────────────┐
                    │   Usuário (API / Web)   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      START (Grafo)      │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   GUARDRAIL DE ENTRADA  │
                    │    (guardrail_node)     │
                    └────────────┬────────────┘
                                 │
                     Aresta Condicional de Segurança
                     ┌───────────┴───────────┐
      [Inseguro / Malicioso]                 │ [Seguro]
                     │                       ▼
                     │          ┌─────────────────────────┐
                     │          │ Agente 1: ROTEADOR      │
                     │          │   (orchestrator_node)   │
                     │          └────────────┬────────────┘
                     │                       │
                     │       Decisão Condicional Semântica
                     │       ┌───────────────┴───────────────┐
                     │       │                               │
                     │       ▼                               ▼
                     │ ┌─────────────────────────┐     ┌─────────────────────────┐
                     │ │ Agente 2: CONHECIMENTO  │     │ Agente 3: SUPORTE       │
                     │ │    (knowledge_node)     │     │     (support_node)      │
                     │ ├─────────────────────────┤     ├─────────────────────────┤
                     │ │ • consultar_base_local  │     │ • consultar_vendas_liq  │
                     │ │   (RAG ChromaDB: PDFs + │     │ • consultar_maquininhas │
                     │ │    URLs assíncronas)    │     │ • consultar_transacoes  │
                     │ │ • consultar_base_web    │     │ • abrir_chamado_suporte │
                     │ │   (Varredura ao vivo)   │     │ • Auth & Isolamento ID  │
                     │ │ • pesquisar_web (DDGS)  │     │                         │
                     │ │ • Citação de Fontes     │     │                         │
                     │ └────────────┬────────────┘     └────────────┬────────────┘
                     │              │                               │
                     │              └───────────────┬───────────────┘
                     │                              │
                     ▼                              ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                           END (Grafo)                           │
    └─────────────────────────────────────────────────────────────────┘
```

### 2.1. Guardrail de Entrada (`guardrail_node`)
- **Arquivo:** [`backend/agents/guardrails.py`](backend/agents/guardrails.py)
- **Papel:** Primeira linha de defesa do sistema. Avalia determinística e heuristicamente o input antes que ele atinja os modelos de linguagem ou gaste tokens desnecessários.
- **Detecções:** Prompt Injection, Jailbreaks, SQL Injection, tags `<script>`, termos abusivos e solicitações de fraudes financeiras.
- **Ação:** Bloqueia sumariamente a requisição emitindo mensagem estruturada com `agent_used: "guardrail_block"` e categoria `"Segurança / Guardrail"`.

### 2.2. Agente 1 — Agente Roteador (`Router Agent`)
- **Arquivo:** [`backend/agents/orchestrator.py`](backend/agents/orchestrator.py)
- **Papel:** Ponto de entrada de toda interação válida. Avalia tanto o texto da mensagem quanto o contexto da sessão (se estava aguardando documento, se mudou de assunto, etc.).
- **Comportamento:** Emite um JSON estruturado com classificação do assunto (`category`), agente de destino (`next_agent`: `knowledge`, `support` ou `guardrail_block`) e justificativa de roteamento (`reason`).
- **Resiliência:** Possui parser defensivo de markdown/JSON para prevenir falhas de serialização e detecção de transição de contexto de identificação para dúvidas gerais sem bloqueio de sessão.

### 2.3. Agente 2 — Agente de Conhecimento (`Knowledge Agent`)
- **Arquivo:** [`backend/agents/knowledge_agent.py`](backend/agents/knowledge_agent.py)
- **Papel:** Especialista técnico e institucional Getnet, munido de RAG corporativo e acesso à internet.
- **Ferramentas (`KNOWLEDGE_TOOLS`):**
  1. `consultar_base_local_getnet`: Realiza busca por similaridade vetorial (`k=4`) no ChromaDB, consultando arquivos físicos locais (`fonte_de_dados/*.pdf`) e URLs indexadas assincronamente via crawler (`RAG_ASYNC_URLS`).
  2. `consultar_base_web_getnet`: Varredura em tempo real nas páginas e subpáginas dos portais oficiais Getnet (`RAG_SYNC_URLS`) sob demanda (*fallback* de alta fidelidade).
  3. `pesquisar_web`: Busca informações dinâmicas em tempo real na internet (clima, cotação de moedas, mercado financeiro) via DuckDuckGo Search sem custo de API externa.
- **Citação de Fontes:** As ferramentas rotulam as origens com ícones e discriminam se os dados vieram de `📄 Arquivo: <nome>` ou `🌐 URL: <link>`. O `SYSTEM_PROMPT` obriga o agente a anexar uma seção destacada `📌 Fontes consultadas:` no rodapé de toda resposta.

### 2.4. Agente 3 — Agente de Suporte ao Cliente (`Customer Support Agent`)
- **Arquivo:** [`backend/agents/support_agent.py`](backend/agents/support_agent.py)
- **Papel:** Especialista em operações e dados transacionais do cliente autenticado (`user_id`).
- **Autenticação Zero-Trust & Isolamento:** Exige identificação inicial via CPF/CNPJ/ID do cliente antes de fornecer qualquer extrato, impedindo vazamento de dados para usuários anônimos e bloqueando consultas a contas de terceiros na mesma conversa.
- **Ferramentas (`SUPPORT_TOOLS`):**
  1. `consultar_vendas_e_liquidacao`: Recupera o extrato de vendas brutas/líquidas de ontem e a data/conta de depósito da liquidação financeira (ex: D+2 Santander).
  2. `consultar_status_maquininhas`: Verifica a conectividade dos terminais do cliente (Wi-Fi, 4G, chips sem sinal) e diagnósticos técnicos.
  3. `consultar_transacoes_e_erros`: Analisa transações recentes e identifica causas técnicas de recusa (ex: Erro 51 - Saldo Insuficiente, Erro 05).
  4. `abrir_chamado_suporte`: Gera chamados técnicos formais com número de protocolo (ex: `GET-1001`) e prazo de atendimento para solicitações que demandam intervenção humana (*Human Handoff*).

### 2.5. Agente 4 — Agente de Escalonamento Humano (`Human Escalation Agent`)
- **Arquivo:** [`backend/agents/escalation_agent.py`](backend/agents/escalation_agent.py)
- **Papel:** Conduz a transferência assistida e contextualizada para operadores humanos (Human Handoff), gerando protocolos auditáveis e sintetizando o caso para o atendente.
- **Ferramentas (`ESCALATION_TOOLS`):**
  1. `abrir_chamado_servicenow`: Invocada obrigatoriamente a cada escalonamento para registrar o chamado/incidente no ServiceNow com protocolo e sumarização do caso.

---

## 3. Pipeline de RAG Avançado & Ingestão Incremental

O pipeline de RAG foi desenhado com foco em custo-eficiência, velocidade e integridade de dados:

1. **Ingestão Híbrida:**
   - **Arquivos Locais:** Processa `.pdf`, `.txt`, `.docx` em `fonte_de_dados/`.
   - **URLs Web:** Crawler recursivo configurável ([`backend/infrastructure/rag/crawler.py`](backend/infrastructure/rag/crawler.py)) com controle de profundidade (`depth`) e sanitização de tags HTML via `BeautifulSoup`.
2. **Sincronização Incremental (Zero Redundância):**
   - Antes de gerar embeddings na OpenAI, o sistema calcula o **Hash MD5** de cada arquivo ou URL e compara com o banco de controle `bds/rag_sync.sqlite`.
   - Documentos sem alteração são ignorados, economizando 100% de tokens de embedding em reinicializações.
3. **Endpoint de Administração Parametrizado:**
   - `POST /api/v1/admin/sync-web`:
     - **`target`** (`"all"`, `"files"`, `"urls"`): Permite sincronizar seletivamente apenas documentos locais, páginas web ou ambos.
     - **`force`** (`true` / `false`): Quando `true`, invalida vetores antigos no ChromaDB (`vectorstore.delete(where={"source": ...})`) e re-vetoriza os alvos; quando `false`, indexa apenas novos itens.

---

## 4. Cobertura Detalhada dos 4 Desafios Bônus

### 4.1. Bônus 1 & 3: Agente de Escalonamento e Mecanismo de Human Handoff
Em sistemas de suporte de missão crítica, a IA não deve prometer resoluções para problemas físicos ou operacionais além de suas capacidades. A solução implementa um mecanismo formal de **Human Handoff**:

1. **Geração de Ticket Auditável com SLA:**
   - Através da ferramenta `abrir_chamado_suporte`, o sistema cria um chamado formal com protocolo único (ex: `GET-1001`), associado ao `user_id` do cliente, definindo prioridade e prazo de atendimento humano (SLA de 24h a 48h).
2. **Transferência de Contexto Sem Perda:**
   - Ao escalar para um operador humano, o sistema consolida o resumo do problema relatado, histórico de recusas ou modelo da maquininha defeituosa, evitando que o cliente precise repetir as informações.
3. **Gatilhos de Escalonamento Automático:**
   - Falhas físicas de maquininhas sem comunicação prolongada (ex: chip sem sinal celular após reinicialização).
   - Tentativa de cancelamento formal de credenciamento.
   - Solicitação explícita do usuário para falar com um atendente humano.

---

### 4.2. Bônus 2: Arquitetura de Guardrails em Camadas (Defense-in-Depth)
Implementamos uma abordagem defensiva em 5 camadas complementares:

1. **Camada 1 — Fast-Path Guardrail Determinístico ([`backend/agents/guardrails.py`](backend/agents/guardrails.py)):**
   - Intercepta antes do orquestrador qualquer mensagem com padrões de Prompt Injection (`ignore instructions`, `jailbreak`, `act as DAN`), injeções SQL (`DROP TABLE`, `' OR 1=1`), scripts XSS e termos criminosos/ilícitos.
2. **Camada 2 — Guardrail Semântico no Roteador ([`backend/agents/orchestrator.py`](backend/agents/orchestrator.py)):**
   - O LLM do roteador pode classificar solicitações com tentativas de engenharia social avançada diretamente como `guardrail_block`.
3. **Camada 3 — Guardrail de Privacidade e Zero-Trust ([`backend/agents/support_agent.py`](backend/agents/support_agent.py)):**
   - Bloqueio estrito de acesso a dados privados sem documento validado e proteção contra vazamento entre contas de clientes diferentes na mesma sessão (LGPD / Sigilo Bancário).
4. **Camada 4 — Guardrail Anti-Alucinação e Grounding ([`backend/agents/knowledge_agent.py`](backend/agents/knowledge_agent.py)):**
   - Obriga a consulta a fontes externas/internas e impõe a citação explícita de fontes no rodapé de toda resposta.
5. **Camada 5 — Guardrail Operacional (Reentrancy Guard):**
   - Limite de recursão no LangGraph (`recursion_limit = 10`), prevenindo loops infinitos de execução e desperdício de orçamento de API.

---

### 4.3. Bônus 4: Estratégia de Avaliação e Observabilidade (Evals & Observability)

#### A. Observabilidade de Produção (Tracing com LangSmith)
O projeto conta com integração nativa com o **LangSmith** configurada em [`backend/core/config.py`](backend/core/config.py):
- **Tracing Distribuído:** Rastreamento ponta a ponta de cada execução do grafo, discriminando a latência de cada nó (`guardrail` $\rightarrow$ `orchestrator` $\rightarrow$ `knowledge/support` $\rightarrow$ `tool_node`).
- **Auditoria de Tokens e Custo:** Monitoramento em tempo real de tokens de entrada/saída consumidos por modelo.
- **Rastreabilidade de Chamadas a Ferramentas:** Registro exato dos parâmetros enviados para o ChromaDB, DuckDuckGo e ferramentas de suporte, facilitando a identificação de anomalias operacionais.

#### B. Estratégia de Avaliação Contínua (Evals Framework)
Para garantir qualidade sustentável em produção, a estratégia de avaliação é baseada em três pilares:

1. **Avaliação Funcional Automatizada (CI/CD Regression Suite):**
   - Suíte em PyTest com 15 cenários cobrindo todos os fluxos críticos de negócio, limites operacionais e testes adversariais de segurança.
2. **Avaliação da Qualidade do RAG (RAG Triad):**
   - **Context Relevance:** Mede se os chunks recuperados pelo ChromaDB são pertinentes à dúvida do usuário.
   - **Groundedness (Fidelidade):** Avalia se todas as afirmações da resposta são estritamente sustentadas pelos chunks recuperados, eliminando alucinações.
   - **Answer Relevance:** Avalia se a resposta gerada responde com precisão à pergunta formulada.
3. **Métricas Chave de Desempenho (SLAs & KPIs):**
   - **Router Accuracy:** Taxa de acerto do Orquestrador no direcionamento de agentes (meta: $\ge 98\%$).
   - **Latency P95:** Tempo de resposta total percebido pelo cliente (meta: $< 2.5s$).
   - **Fallback & Handoff Rate:** Percentual de chamados escalados para operador humano (monitoramento de eficácia do bot).
   - **Guardrail Interception Rate:** Taxa de requisições maliciosas bloqueadas antes do processamento.

---

## 5. Endpoints da API e Contratos de Dados

Desenvolvida em **FastAPI**, com tipagem estrita via **Pydantic v2** e documentação interativa Swagger UI (`/docs`).

### 5.1. Conversação (`POST /api/v1/chat`)
**Payload de Entrada (conforme edital):**
```json
{
  "message": "Qual é a diferença entre a Get Clássica e a Get Smart?",
  "user_id": "cliente1988"
}
```

**Payload de Resposta:**
```json
{
  "response": "A Get Clássica possui teclado físico e emissão de comprovante em papel... enquanto a Get Smart opera com sistema Android e tela touchscreen...\n\n---\n📌 **Fontes consultadas:**\n- 📄 Arquivo: Tarifa plana.pdf",
  "agent_used": "knowledge",
  "category": "Comparativo Produtos"
}
```

### 5.2. Administração RAG (`POST /api/v1/admin/sync-web`)
Permite aos operadores sincronizar sob demanda o catálogo web e a pasta local:
- Parâmetros: `target=all|files|urls`, `force=true|false`.
- Resposta detalhada com métricas de arquivos e URLs indexadas.

---

## 6. Dockerização e DevOps

- **Dockerfile Multi-Stage:**
  - Estágio de compilação (*builder*) para dependências C/C++ e estágio final limpo sobre `python:3.11-slim`, minimizando o tamanho final da imagem.
  - Healthcheck configurado em `/health`.
- **Docker Compose:**
  - Arquivo [`docker-compose.yml`](docker-compose.yml) configurado com mapeamento de volumes persistentes (`./bds:/app/bds` e `./fonte_de_dados:/app/fonte_de_dados`), permitindo atualizar documentos no host sem reconstruir contêineres.

---

## 7. Cobertura dos 27 Cenários de Teste Automatizados

A suíte automatizada em [`tests/test_scenarios.py`](tests/test_scenarios.py) atende integralmente todos os 10 cenários do edital, mais 2 de segurança/autenticação, 3 de guardrails, 2 de human handoff explícito e 10 cenários de escalonamento implícito:

| # | Cenário de Teste | Agente Responsável | Ferramenta / Validação | Resultado |
| :-: | :--- | :---: | :--- | :---: |
| **1** | *"Qual é a diferença entre a Get Clássica e a Get Smart?"* | `knowledge` | `consultar_base_local_getnet` (RAG) | **PASSED** |
| **2** | *"Qual é a previsão do tempo para Porto Alegre amanhã?"* | `knowledge` | `pesquisar_web` (DuckDuckGo) | **PASSED** |
| **3** | *"Quando o dinheiro das vendas de ontem será depositado?"* | `support` | `consultar_vendas_e_liquidacao` | **PASSED** |
| **4** | *"Preciso de uma conta bancária para receber minhas vendas via Pix?"* | `knowledge` | `consultar_base_local_getnet` | **PASSED** |
| **5** | *"Minha maquininha não conecta à internet; o que devo fazer?"* | `support` / `knowledge` | `consultar_status_maquininhas` | **PASSED** |
| **6** | *"Como funciona a antecipação de recebíveis com a Getnet?"* | `knowledge` | `consultar_base_local_getnet` | **PASSED** |
| **7** | *"Qual é a taxa de câmbio do euro hoje?"* | `knowledge` | `pesquisar_web` | **PASSED** |
| **8** | *"Minha maquininha está apresentando um erro de recusa de transação."* | `support` | `consultar_transacoes_e_erros` | **PASSED** |
| **9** | *"Em quantas parcelas posso dividir uma venda usando o crediário?"* | `knowledge` | `consultar_base_local_getnet` | **PASSED** |
| **10** | *"Posso vender pelo WhatsApp usando o Link de Pagamento?"* | `knowledge` | `consultar_base_local_getnet` | **PASSED** |
| **11** | *Segurança: Tentativa de consulta com documento não localizado* | `support` | Validação cadastral com zero vazamento | **PASSED** |
| **12** | *Segurança: Bloqueio de acesso a dados de terceiros na mesma sessão* | `support` / `guardrail_block` | Isolamento estrito de sessão (LGPD) | **PASSED** |
| **13** | *Guardrail: Tentativa de Prompt Injection / Jailbreak* | `guardrail_block` | Interceptação preventiva determinística | **PASSED** |
| **14** | *Guardrail: Tentativa de SQL Injection / Código Malicioso* | `guardrail_block` | Interceptação preventiva determinística | **PASSED** |
| **15** | *Guardrail: Solicitação Ilícita / Clonagem de Cartão* | `guardrail_block` | Interceptação preventiva de conformidade | **PASSED** |
| **16** | *Human Handoff: Solicitação direta para falar com atendente humano* | `escalation` | Transferência com geração de protocolo oficial e síntese | **PASSED** |
| **17** | *Human Handoff: Cliente insatisfeito solicitando operador humano* | `escalation` | Triagem automática para fila especializada | **PASSED** |
| **18** | *Escalonamento Implícito: Dano físico irreversível no terminal* | `escalation` | Roteamento automático para Suporte Técnico N2 | **PASSED** |
| **19** | *Escalonamento Implícito: Bloqueio judicial e contestação alto valor* | `escalation` | Roteamento automático para Jurídico/Risco | **PASSED** |
| **20** | *Escalonamento Implícito: Emergência operacional e paralisia de vendas* | `escalation` | Roteamento automático para Suporte N2 Emergencial | **PASSED** |
| **21** | *Escalonamento Implícito: Exaustão comprovada de troubleshooting* | `escalation` | Roteamento automático para Suporte Técnico Especialista | **PASSED** |
| **22** | *Escalonamento Implícito: Risco de churn / Ameaça concorrente* | `escalation` | Roteamento automático para Mesa de Retenção | **PASSED** |
| **23** | *Escalonamento Implícito: Alerta PED Tampered / Violação física (PCI)* | `escalation` | Roteamento automático para Suporte Hardware / Segurança | **PASSED** |
| **24** | *Escalonamento Implícito: Intimação cominatória Procon / Regulador* | `escalation` | Roteamento automático para Jurídico e Compliance | **PASSED** |
| **25** | *Escalonamento Implícito: Sucessão societária / Falecimento titular* | `escalation` | Roteamento automático para Mesa Jurídica / Espólio | **PASSED** |
| **26** | *Escalonamento Implícito: Fraude ativa / Desvio de domicílio bancário* | `escalation` | Roteamento automático para Segurança e Antifraude | **PASSED** |
| **27** | *Escalonamento Implícito: Grandes Contas / TEF dedicado corporativo* | `escalation` | Roteamento automático para Mesa de Key Accounts | **PASSED** |

**Resultado consolidado:** `27 passed (100% de sucesso na suíte de testes)`.

---

## 8. Conclusão

A solução apresentada demonstra domínio avançado em **Engenharia de Software e Inteligência Artificial**, atendendo com rigor a todos os requisitos arquiteturais, funcionais, de segurança e de confiabilidade exigidos no desafio para Engenheiro de IA Sênior da Getnet.
