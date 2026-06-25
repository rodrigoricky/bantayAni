from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from services.auth_service import get_current_user
from services.chat_service import (
    classify_intent,
    validate_response,
    execute_intent,
    process_chat,
)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str
    action: Optional[dict] = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    satellite_date: Optional[str] = "2024-10-25"


@router.post("")
def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    history = [m.model_dump() for m in request.conversation_history]
    result = process_chat(
        request.message,
        history,
        user,
        request.satellite_date or "2024-10-25",
    )
    return {
        "success": True,
        "data": {
            "response": result["response"],
            "action": result.get("action"),
            "buttons": result.get("buttons", []),
            "intent": result.get("intent"),
        },
        "error": None,
    }