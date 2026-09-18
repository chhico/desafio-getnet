from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description="Consulta ou declaração do usuário")
    user_id: Optional[str] = Field("cliente1988", description="Identificador único do usuário/cliente (padrão: cliente1988)")
    thread_id: Optional[str] = Field(None, description="Identificador opcional de sessão (padrão é o próprio user_id)")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Resposta do agente especialista")
    agent_used: str = Field(..., description="Agente que processou a mensagem (router, knowledge, support)")
    category: Optional[str] = Field(None, description="Classificação do assunto")
