"""REST endpoints for the Live Chats inbox (org-scoped, JWT).

Live updates flow over the agent WebSocket; these endpoints serve the initial
load and history fetch.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Chatbot, Conversation, Organization
from app.services import crud
from app.services.auth import require_org

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversations"], dependencies=[Depends(require_org)])


@router.get("/conversations")
def list_conversations(
    org: Organization = Depends(require_org), db: Session = Depends(get_db)
) -> dict:
    items = crud.list_active_conversations(db, org.id)
    return {"conversations": items, "count": len(items)}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> dict:
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    cb = db.get(Chatbot, conv.chatbot_id)
    if cb is None or cb.org_id != org.id:  # tenant isolation
        raise HTTPException(status_code=404, detail="Conversation not found.")
    msgs = crud.conversation_messages(db, conversation_id)
    return {
        "conversation": crud.conversation_summary(db, conv),
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "content": m.content,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }
