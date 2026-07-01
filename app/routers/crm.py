"""External CRM integration API (read-only).

Auth: a single header `X-CRM-Key` — no login. A valid CRM key grants read
access to that organization's chatbots, conversations, transcripts, and leads.
Generate CRM keys in the dashboard (Integrations). Multiple keys are supported.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Chatbot, Conversation, Organization
from app.services import crud
from app.services.auth import require_crm_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["crm"], dependencies=[Depends(require_crm_key)])


def _parse_since(since: str | None) -> datetime | None:
    if not since:
        return None
    try:
        s = since.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid 'since' (use ISO 8601).")


@router.get("/chatbots")
def crm_chatbots(
    org: Organization = Depends(require_crm_key), db: Session = Depends(get_db)
) -> dict:
    bots = (
        db.query(Chatbot).filter(Chatbot.org_id == org.id).order_by(Chatbot.created_at).all()
    )
    return {
        "chatbots": [
            {"id": b.id, "name": b.name, "model": b.model} for b in bots
        ],
        "count": len(bots),
    }


@router.get("/conversations")
def crm_conversations(
    chatbot_id: str | None = None,
    since: str | None = Query(None, description="ISO 8601; only convs active since then"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    items = crud.crm_list_conversations(
        db, org.id, chatbot_id, _parse_since(since), limit, offset
    )
    return {"conversations": items, "count": len(items), "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}/messages")
def crm_messages(
    conversation_id: str,
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    conv = db.get(Conversation, conversation_id)
    cb = db.get(Chatbot, conv.chatbot_id) if conv else None
    if conv is None or cb is None or cb.org_id != org.id:  # tenant isolation
        raise HTTPException(status_code=404, detail="Conversation not found.")
    msgs = crud.conversation_messages(db, conversation_id, limit=1000)
    return {
        "conversation": crud.conversation_summary(db, conv),
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,  # visitor | ai | agent | system
                "content": m.content,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


@router.get("/leads")
def crm_leads(
    chatbot_id: str | None = None,
    status: str | None = Query(None, description="new | contacted"),
    since: str | None = Query(None, description="ISO 8601; leads created since then"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    leads = crud.crm_list_leads(
        db, org.id, chatbot_id, status, _parse_since(since), limit, offset
    )
    return {
        "leads": [
            {
                "id": l.id,
                "chatbot_id": l.chatbot_id,
                "conversation_id": l.conversation_id,
                "name": l.name,
                "phone": l.phone,
                "email": l.email,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
        "count": len(leads),
        "limit": limit,
        "offset": offset,
    }
