"""WebSocket endpoints: visitor chat + agent dashboard, with live handoff."""
import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.db.base import SessionLocal
from app.db.models import Chatbot, Conversation
from app.services import crud, rag, webhooks
from app.services.auth import hash_key
from app.services.security import decode_access_token
from app.services.ws_manager import manager, visitor_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


def _msg_dict(m) -> dict:
    return {
        "id": m.id,
        "sender": m.sender,
        "content": m.content,
        "agent_name": m.agent_name,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _resolve_chatbot_by_key(db, api_key: str) -> Chatbot | None:
    from app.db.models import ApiKey

    ak = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_key(api_key), ApiKey.revoked.is_(False))
        .first()
    )
    if ak is None:
        return None
    return db.get(Chatbot, ak.chatbot_id)


async def _maybe_prompt_lead(key: str, conv_id: str, chatbot_id: str) -> None:
    """Show the lead form after enough visitor messages.

    First shown after lead_after_messages. If the visitor skips ("No thanks"),
    lead_next_at schedules a re-prompt after that many MORE messages.
    """
    with SessionLocal() as db:
        conv = db.get(Conversation, conv_id)
        cb = db.get(Chatbot, chatbot_id)
        if not cb or not cb.lead_enabled or conv.lead_captured:
            return
        count = crud.count_visitor_messages(db, conv_id)
        if not conv.lead_prompted:
            threshold = cb.lead_after_messages          # first prompt
        elif conv.lead_next_at is not None:
            threshold = conv.lead_next_at               # re-prompt after a skip
        else:
            return  # form currently shown / awaiting a response
        if count < threshold:
            return
        conv.lead_prompted = True
        conv.lead_next_at = None
        db.commit()
    await manager.send_to_visitor(
        key,
        {
            "type": "lead_form",
            "title": "Want a callback from our team?",
            "subtitle": "Leave your details — a specialist will reach out.",
            "fields": ["name", "phone", "email"],
        },
    )


async def _prompt_lead_now(key: str, conv_id: str, chatbot_id: str) -> None:
    """Show the lead form immediately (bypasses the message threshold).

    Used for sales/contact intent and no-answer cases. Still respects
    lead_enabled and skips if a lead was already captured.
    """
    with SessionLocal() as db:
        conv = db.get(Conversation, conv_id)
        cb = db.get(Chatbot, chatbot_id)
        if not cb or not cb.lead_enabled or conv.lead_captured:
            return
        conv.lead_prompted = True
        conv.lead_next_at = None
        db.commit()
    await manager.send_to_visitor(
        key,
        {
            "type": "lead_form",
            "title": "Request a callback",
            "subtitle": "Leave your details and our sales team will contact you.",
            "fields": ["name", "phone", "email"],
        },
    )


async def _send_bot_message(key: str, conv_id: str, chatbot_id: str, text: str) -> None:
    """Send a canned bot message as its own bubble, persist it, notify agents."""
    await manager.send_to_visitor(key, {"type": "token", "token": text})
    await manager.send_to_visitor(key, {"type": "ai_done"})
    with SessionLocal() as db:
        conv = db.get(Conversation, conv_id)
        amsg = crud.add_conversation_message(db, conv, "ai", text)
        amsg_dict = _msg_dict(amsg)
        org_id = db.get(Chatbot, chatbot_id).org_id
        summary = crud.conversation_summary(db, conv)
    await manager.broadcast_to_org_agents(
        org_id,
        {"type": "message", "conversation_id": conv_id, "message": amsg_dict,
         "conversation": summary},
    )


# ── Visitor WebSocket ───────────────────────────────────────────────────────
@router.websocket("/ws/chat/{session_id}")
async def ws_visitor(
    websocket: WebSocket,
    session_id: str,
    api_key: str = Query(...),
):
    # Auth via API key (browser WebSocket can't set headers → query param).
    with SessionLocal() as db:
        chatbot = _resolve_chatbot_by_key(db, api_key)
        if chatbot is None:
            await websocket.close(code=4401)
            return
        chatbot_id = chatbot.id
        chatbot_model = chatbot.model  # detached-safe copy
        conv = crud.get_or_create_conversation(db, chatbot_id, session_id)
        conv_id = conv.id
        mode = conv.mode
        agent_name = conv.assigned_agent_name
        history_msgs = [_msg_dict(m) for m in crud.conversation_messages(db, conv_id)]

    key = visitor_key(chatbot_id, session_id)
    await manager.connect_visitor(websocket, key)
    await websocket.send_json(
        {"type": "history", "messages": history_msgs, "mode": mode, "agent_name": agent_name}
    )

    try:
        while True:
            data = await websocket.receive_json()
            # One bad event must NOT kill the connection: handle each event in
            # its own try/except and keep the loop alive on failure.
            try:
                await _handle_visitor_event(
                    websocket, key, conv_id, chatbot_id, session_id, data
                )
            except WebSocketDisconnect:
                raise
            except Exception:
                logger.exception("Visitor event failed for %s (kept alive)", key)
                # Unstick the widget (clears its typing indicator).
                await manager.send_to_visitor(key, {"type": "ai_done"})
                await manager.send_to_visitor(
                    key,
                    {"type": "system",
                     "text": "Sorry, something went wrong. Please try again."},
                )
    except WebSocketDisconnect:
        manager.disconnect_visitor(key)
    except Exception:
        logger.exception("Visitor WS error for %s", key)
        manager.disconnect_visitor(key)


async def _handle_visitor_event(
    websocket: WebSocket,
    key: str,
    conv_id: str,
    chatbot_id: str,
    session_id: str,
    data: dict,
) -> None:
    """Process one visitor WS event. ORM objects are serialized to plain dicts
    INSIDE each session block — they expire on commit and detach on close."""
    mtype = data.get("type")

    if mtype == "request_human":
        with SessionLocal() as db:
            conv = db.get(Conversation, conv_id)
            conv.waiting_for_human = True
            sys_msg = crud.add_conversation_message(
                db, conv, "system", "Visitor requested a human agent."
            )
            sys_dict = _msg_dict(sys_msg)
            summary = crud.conversation_summary(db, conv)
            org_id = db.get(Chatbot, chatbot_id).org_id
        await websocket.send_json(
            {"type": "system", "text": "A team member has been notified and will join shortly."}
        )
        await manager.broadcast_to_org_agents(
            org_id,
            {"type": "conversation_updated", "conversation": summary,
             "message": sys_dict},
        )
        return

    if mtype == "lead":
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        if not name or not phone:
            return
        with SessionLocal() as db:
            conv = db.get(Conversation, conv_id)
            lead = crud.create_lead(db, chatbot_id, conv_id, name, phone, email)
            lead_id = lead.id
            conv.lead_captured = True
            conv.lead_next_at = None
            details = f"{name}, {phone}" + (f", {email}" if email else "")
            sys_msg = crud.add_conversation_message(
                db, conv, "system", f"Lead captured — {details}"
            )
            sys_dict = _msg_dict(sys_msg)
            org_id = db.get(Chatbot, chatbot_id).org_id
            summary = crud.conversation_summary(db, conv)
        await manager.send_to_visitor(
            key,
            {"type": "lead_saved",
             "text": "Thank you! Our team will contact you shortly."},
        )
        await manager.broadcast_to_org_agents(
            org_id,
            {"type": "lead", "conversation_id": conv_id,
             "lead": {"id": lead_id, "name": name, "phone": phone,
                      "email": email or None},
             "conversation": summary, "message": sys_dict},
        )
        # Push to the org's CRM webhook (if configured).
        webhooks.schedule(
            org_id,
            "lead.created",
            {
                "id": lead_id,
                "chatbot_id": chatbot_id,
                "conversation_id": conv_id,
                "name": name,
                "phone": phone,
                "email": email or None,
                "status": "new",
            },
        )
        return

    if mtype == "lead_skip":
        # Visitor declined the form: re-offer it after lead_after_messages
        # more visitor messages.
        with SessionLocal() as db:
            conv = db.get(Conversation, conv_id)
            cb = db.get(Chatbot, chatbot_id)
            if conv.lead_captured or not cb:
                return
            count = crud.count_visitor_messages(db, conv_id)
            conv.lead_next_at = count + cb.lead_after_messages
            db.commit()
        return

    if mtype != "message":
        return

    text = (data.get("text") or "").strip()
    if not text:
        return

    # Persist visitor message; notify agents.
    with SessionLocal() as db:
        conv = db.get(Conversation, conv_id)
        vmsg = crud.add_conversation_message(db, conv, "visitor", text)
        vmsg_dict = _msg_dict(vmsg)
        mode = conv.mode
        org_id = db.get(Chatbot, chatbot_id).org_id
        summary = crud.conversation_summary(db, conv)
    await manager.broadcast_to_org_agents(
        org_id,
        {"type": "message", "conversation_id": conv_id, "message": vmsg_dict,
         "conversation": summary},
    )

    if mode == "human":
        # Live agent handles it; AI stays silent.
        await _maybe_prompt_lead(key, conv_id, chatbot_id)
        return

    # Sales / contact intent: skip RAG, give the phone + lead form right away.
    if rag.is_sales_intent(text):
        with SessionLocal() as db:
            cb = db.get(Chatbot, chatbot_id)
            reply = rag.contact_message(cb)
        await _send_bot_message(key, conv_id, chatbot_id, reply)
        await _prompt_lead_now(key, conv_id, chatbot_id)
        return

    # AI mode: stream a RAG answer over the socket.
    with SessionLocal() as db:
        conv = db.get(Conversation, conv_id)
        history = crud.history_for_llm(db, conv_id)
        cb = db.get(Chatbot, chatbot_id)
        usage: dict = {}
        parts: list[str] = []
        try:
            async for token in rag.stream_rag(cb, text, history, usage):
                parts.append(token)
                await manager.send_to_visitor(key, {"type": "token", "token": token})
        finally:
            # Always release the widget's typing indicator, even on LLM errors.
            await manager.send_to_visitor(key, {"type": "ai_done"})
        answer = "".join(parts)
        amsg = crud.add_conversation_message(db, conv, "ai", answer)
        amsg_dict = _msg_dict(amsg)
        turn = crud.next_turn_number(db, chatbot_id, session_id)
        crud.log_turn(db, chatbot_id, session_id, text, answer, turn, usage)
        summary = crud.conversation_summary(db, conv)
    await manager.broadcast_to_org_agents(
        org_id,
        {"type": "message", "conversation_id": conv_id, "message": amsg_dict,
         "conversation": summary},
    )

    # No answer found: offer the phone + lead form right away.
    if usage.get("no_context"):
        with SessionLocal() as db:
            cb = db.get(Chatbot, chatbot_id)
            reply = rag.contact_message(cb)
        await _send_bot_message(key, conv_id, chatbot_id, reply)
        await _prompt_lead_now(key, conv_id, chatbot_id)
    else:
        # Otherwise, maybe show the lead form after enough messages.
        await _maybe_prompt_lead(key, conv_id, chatbot_id)


# ── Agent WebSocket ─────────────────────────────────────────────────────────
@router.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket, token: str = Query(...)):
    try:
        org_id = decode_access_token(token)
    except Exception:
        await websocket.close(code=4401)
        return
    with SessionLocal() as db:
        from app.db.models import Organization

        org = db.get(Organization, org_id)
        if org is None:
            await websocket.close(code=4401)
            return
        agent_name = org.name or "Agent"

    agent_id = uuid.uuid4().hex[:12]
    await manager.connect_agent(websocket, org_id, agent_id, agent_name)

    # Initial inbox.
    with SessionLocal() as db:
        inbox = crud.list_active_conversations(db, org_id)
    await websocket.send_json(
        {"type": "inbox", "agent_id": agent_id, "agent_name": agent_name,
         "conversations": inbox}
    )

    def _owns(db, conv: Conversation) -> bool:
        cb = db.get(Chatbot, conv.chatbot_id) if conv else None
        return bool(cb and cb.org_id == org_id)

    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")
            conv_id = data.get("conversation_id")

            if mtype == "subscribe" and conv_id:
                with SessionLocal() as db:
                    conv = db.get(Conversation, conv_id)
                    if not _owns(db, conv):
                        continue
                    conv.unread = 0  # agent is now viewing
                    db.commit()
                    msgs = [_msg_dict(m) for m in crud.conversation_messages(db, conv_id)]
                    summary = crud.conversation_summary(db, conv)
                await websocket.send_json(
                    {"type": "history", "conversation_id": conv_id,
                     "messages": msgs, "conversation": summary}
                )

            elif mtype == "take_over" and conv_id:
                with SessionLocal() as db:
                    conv = db.get(Conversation, conv_id)
                    if not _owns(db, conv):
                        continue
                    # Collision guard: someone else already handling.
                    if conv.mode == "human" and conv.assigned_agent_id not in (None, agent_id):
                        await websocket.send_json(
                            {"type": "error",
                             "message": f"Already handled by {conv.assigned_agent_name}."}
                        )
                        continue
                    conv.mode = "human"
                    conv.assigned_agent_id = agent_id
                    conv.assigned_agent_name = agent_name
                    conv.waiting_for_human = False
                    sys_msg = crud.add_conversation_message(
                        db, conv, "system", f"{agent_name} joined the chat."
                    )
                    cb = db.get(Chatbot, conv.chatbot_id)
                    vkey = visitor_key(cb.id, conv.session_id)
                    summary = crud.conversation_summary(db, conv)
                await manager.send_to_visitor(
                    vkey,
                    {"type": "mode", "mode": "human", "agent_name": agent_name,
                     "text": f"You're now chatting with {agent_name}."},
                )
                await manager.broadcast_to_org_agents(
                    org_id,
                    {"type": "mode", "conversation_id": conv_id, "mode": "human",
                     "agent_id": agent_id, "agent_name": agent_name,
                     "conversation": summary, "message": _msg_dict(sys_msg)},
                )

            elif mtype == "release" and conv_id:
                with SessionLocal() as db:
                    conv = db.get(Conversation, conv_id)
                    if not _owns(db, conv):
                        continue
                    conv.mode = "ai"
                    conv.assigned_agent_id = None
                    conv.assigned_agent_name = None
                    sys_msg = crud.add_conversation_message(
                        db, conv, "system", "Handed back to the AI assistant."
                    )
                    cb = db.get(Chatbot, conv.chatbot_id)
                    vkey = visitor_key(cb.id, conv.session_id)
                    summary = crud.conversation_summary(db, conv)
                await manager.send_to_visitor(
                    vkey,
                    {"type": "mode", "mode": "ai",
                     "text": "You're back with the AI assistant."},
                )
                await manager.broadcast_to_org_agents(
                    org_id,
                    {"type": "mode", "conversation_id": conv_id, "mode": "ai",
                     "conversation": summary, "message": _msg_dict(sys_msg)},
                )

            elif mtype == "message" and conv_id:
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                with SessionLocal() as db:
                    conv = db.get(Conversation, conv_id)
                    if not _owns(db, conv):
                        continue
                    amsg = crud.add_conversation_message(
                        db, conv, "agent", text, agent_id=agent_id, agent_name=agent_name
                    )
                    cb = db.get(Chatbot, conv.chatbot_id)
                    vkey = visitor_key(cb.id, conv.session_id)
                    summary = crud.conversation_summary(db, conv)
                await manager.send_to_visitor(
                    vkey,
                    {"type": "agent_message", "text": text, "agent_name": agent_name},
                )
                await manager.broadcast_to_org_agents(
                    org_id,
                    {"type": "message", "conversation_id": conv_id,
                     "message": _msg_dict(amsg), "conversation": summary},
                )
    except WebSocketDisconnect:
        manager.disconnect_agent(websocket)
    except Exception:
        logger.exception("Agent WS error for org %s", org_id)
        manager.disconnect_agent(websocket)
