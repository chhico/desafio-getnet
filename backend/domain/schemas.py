from pydantic import BaseModel, Field
from typing import Optional, Any

class ChatRequest(BaseModel):
    message: str = Field(..., description="Consulta ou declaração do usuário")
    user_id: Optional[str] = Field("cliente1988", description="Identificador único do usuário/cliente (padrão: cliente1988)")
    thread_id: Optional[str] = Field(None, description="Identificador opcional de sessão (padrão é o próprio user_id)")

class HarnessTrace(BaseModel):
    turn_count: int = Field(1, description="Número do turno na conversa")
    thread_id: str = Field(..., description="ID da sessão/thread isolada")
    user_id: Optional[str] = Field(None, description="Identificador do cliente autenticado")
    execution_mode: str = Field("SANDBOX_SQLITE_LOCAL", description="Ambiente de isolamento e execução")
    side_effects_prevented: bool = Field(True, description="Indica se mutações e efeitos colaterais foram contidos")
    mutation_performed: bool = Field(False, description="Indica se houve mutação de estado ou inserção de registro")
    mutation_details: Optional[str] = Field(None, description="Detalhamento da mutação contida ou executada")
    authenticated: bool = Field(False, description="Flag de autenticação de sessão via documento")
    nodes_visited: list[str] = Field(default_factory=list, description="Lista sequencial de nós percorridos no StateGraph")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Ferramentas corporativas executadas com seus parâmetros")
    latency_ms: float = Field(..., description="Tempo total de execução em milissegundos")
    estimated_tokens: int = Field(0, description="Estimativa de tokens consumidos")
    estimated_cost_usd: float = Field(0.0, description="Custo estimado em dólares")
    guardrail_safe: bool = Field(True, description="Status de integridade avaliado pelo Guardrail")
    buffer_messages_count: int = Field(0, description="Quantidade real de mensagens acumuladas no histórico")
    human_messages_count: int = Field(1, description="Quantidade de mensagens enviadas pelo usuário")
    ai_messages_count: int = Field(1, description="Quantidade de mensagens/sínteses geradas pela IA")
    tool_messages_count: int = Field(0, description="Quantidade de retornos intermediários de ferramentas")
    state_snapshot: dict[str, Any] = Field(default_factory=dict, description="Snapshot das variáveis ativas persistidas no StateGraph")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Resposta do agente especialista")
    agent_used: str = Field(..., description="Agente que processou a mensagem (router, knowledge, support)")
    category: Optional[str] = Field(None, description="Classificação do assunto")
    tools_used: list[str] = Field(default_factory=list, description="Lista de ferramentas utilizadas pelo agente")
    trace: Optional[HarnessTrace] = Field(None, description="Metadados de observabilidade e execução do Harness")
