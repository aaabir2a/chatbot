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
from app.db.models import Chatbot, Conversation, Lead, Organization
from app.schemas import CrmAgentMessage, CrmTakeover, LeadStatusUpdate
from app.services import crud
from app.services.auth import require_crm_key
from app.services.ws_manager import manager, visitor_key

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


@router.patch("/leads/{lead_id}")
def crm_update_lead(
    lead_id: str,
    body: LeadStatusUpdate,
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    """Write-back: let the CRM mark a lead new|contacted."""
    lead = db.get(Lead, lead_id)
    cb = db.get(Chatbot, lead.chatbot_id) if lead else None
    if lead is None or cb is None or cb.org_id != org.id:  # tenant isolation
        raise HTTPException(status_code=404, detail="Lead not found.")
    lead.status = body.status
    db.commit()
    return {"id": lead.id, "status": lead.status}


# ── Live-agent actions (CRM acts as a live agent) ─────────────────────────────
def _owned_conversation(db: Session, org: Organization, conversation_id: str) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    cb = db.get(Chatbot, conv.chatbot_id) if conv else None
    if conv is None or cb is None or cb.org_id != org.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@router.post("/conversations/{conversation_id}/takeover")
async def crm_takeover(
    conversation_id: str,
    body: CrmTakeover,
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    """Take over a conversation as a live agent (pauses the AI)."""
    conv = _owned_conversation(db, org, conversation_id)
    agent_id = f"crm:{body.agent_name}"
    # Collision guard: someone else already handling.
    if conv.mode == "human" and conv.assigned_agent_id not in (None, agent_id):
        raise HTTPException(
            status_code=409, detail=f"Already handled by {conv.assigned_agent_name}."
        )
    conv.mode = "human"
    conv.assigned_agent_id = agent_id
    conv.assigned_agent_name = body.agent_name
    conv.waiting_for_human = False
    crud.add_conversation_message(db, conv, "system", f"{body.agent_name} joined the chat.")
    cb = db.get(Chatbot, conv.chatbot_id)
    vkey = visitor_key(cb.id, conv.session_id)
    await manager.send_to_visitor(
        vkey,
        {"type": "mode", "mode": "human", "agent_name": body.agent_name,
         "text": f"You're now chatting with {body.agent_name}."},
    )
    await manager.broadcast_to_org_agents(
        org.id, {"type": "mode", "conversation_id": conv.id, "mode": "human",
                 "agent_id": agent_id, "agent_name": body.agent_name}
    )
    return {"conversation_id": conv.id, "mode": "human", "assigned_agent_name": body.agent_name}


@router.post("/conversations/{conversation_id}/messages")
async def crm_send_message(
    conversation_id: str,
    body: CrmAgentMessage,
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    """Send an agent reply to the visitor (relayed live to the widget)."""
    conv = _owned_conversation(db, org, conversation_id)
    if conv.mode != "human":
        raise HTTPException(status_code=409, detail="Take over the conversation first.")
    agent_id = f"crm:{body.agent_name}"
    msg = crud.add_conversation_message(
        db, conv, "agent", body.text, agent_id=agent_id, agent_name=body.agent_name
    )
    cb = db.get(Chatbot, conv.chatbot_id)
    vkey = visitor_key(cb.id, conv.session_id)
    await manager.send_to_visitor(
        vkey, {"type": "agent_message", "text": body.text, "agent_name": body.agent_name}
    )
    await manager.broadcast_to_org_agents(
        org.id,
        {"type": "message", "conversation_id": conv.id,
         "message": {"id": msg.id, "sender": "agent", "content": body.text,
                     "agent_name": body.agent_name,
                     "created_at": msg.created_at.isoformat() if msg.created_at else None}},
    )
    return {"id": msg.id, "conversation_id": conv.id, "sender": "agent"}


@router.post("/conversations/{conversation_id}/release")
async def crm_release(
    conversation_id: str,
    org: Organization = Depends(require_crm_key),
    db: Session = Depends(get_db),
) -> dict:
    """Hand the conversation back to the AI."""
    conv = _owned_conversation(db, org, conversation_id)
    conv.mode = "ai"
    conv.assigned_agent_id = None
    conv.assigned_agent_name = None
    crud.add_conversation_message(db, conv, "system", "Handed back to the AI assistant.")
    cb = db.get(Chatbot, conv.chatbot_id)
    vkey = visitor_key(cb.id, conv.session_id)
    await manager.send_to_visitor(
        vkey, {"type": "mode", "mode": "ai", "text": "You're back with the AI assistant."}
    )
    await manager.broadcast_to_org_agents(
        org.id, {"type": "mode", "conversation_id": conv.id, "mode": "ai"}
    )
    return {"conversation_id": conv.id, "mode": "ai"}
