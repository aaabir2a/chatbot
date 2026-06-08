"""POST /chat — streamed RAG response (SSE). Scoped to the API key's chatbot."""
import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.db.base import get_db
from app.db.models import Chatbot
from app.schemas import ChatRequest
from app.services import rag
from app.services.auth import require_api_key
from app.services.ratelimit import RATE_LIMIT, limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/chat")
@limiter.limit(RATE_LIMIT)
async def chat(
    request: Request,
    body: ChatRequest,
    chatbot: Chatbot = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    async def event_generator():
        try:
            async for token in rag.stream_answer(
                db, chatbot, body.message, body.session_id
            ):
                yield {"event": "token", "data": json.dumps({"token": token})}
            yield {"event": "done", "data": json.dumps({"done": True})}
        except Exception as e:
            logger.exception(
                "Chat stream failed for chatbot=%s session=%s",
                chatbot.id, body.session_id,
            )
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
