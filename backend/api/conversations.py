from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from backend.domain.schemas import ChatRequest, ChatResponse
from backend.services.conversation_service import ConversationService
from backend.agents.graph import support_graph

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    x_client_channel: Optional[str] = Header(None, alias="X-Client-Channel"),
):
    """
    Endpoint principal exigido no desafio Getnet:
    Aceita payload com {"message": "...", "user_id": "..."}.
    """
    try:
        return ConversationService.process_message(
            graph=support_graph,
            user_id=request.user_id,
            message_content=request.message,
            thread_id=request.thread_id,
            channel=x_client_channel or "api",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
