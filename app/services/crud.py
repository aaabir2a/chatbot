"""Small DB helpers for conversation history and turn logging."""
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ChatLog, Chatbot, Conversation, Message

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_recent_messages(
    db: Session, chatbot_id: str, session_id: str, max_turns: int | None = None
) -> list[dict]:
    """Reconstruct recent chat history (oldest-first) from ChatLog rows.

    Strictly scoped to (chatbot_id, session_id) — no cross-tenant leakage.
    """
    limit = max_turns or settings.history_max_turns
    rows = (
        db.query(ChatLog)
        .filter(ChatLog.chatbot_id == chatbot_id, ChatLog.session_id == session_id)
        .order_by(ChatLog.id.desc())
        .limit(limit)
        .all()
    )
    messages: list[dict] = []
    for row in reversed(rows):  # oldest-first
        messages.append({"role": "user", "content": row.user_message})
        messages.append({"role": "assistant", "content": row.assistant_message})
    return messages


def next_turn_number(db: Session, chatbot_id: str, session_id: str) -> int:
    count = (
        db.query(func.count(ChatLog.id))
        .filter(ChatLog.chatbot_id == chatbot_id, ChatLog.session_id == session_id)
        .scalar()
    )
    return int(count or 0) + 1


def log_turn(
    db: Session,
    chatbot_id: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
    message_count: int,
    usage: dict,
) -> None:
    entry = ChatLog(
        chatbot_id=chatbot_id,
        session_id=session_id,
        user_message=user_message,
        assistant_message=assistant_message,
        message_count=message_count,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to log chat turn for chatbot %s", chatbot_id)


# ── Conversations & messages (human-agent handoff) ──────────────────────────

_SENDER_TO_ROLE = {"visitor": "user", "ai": "assistant", "agent": "assistant"}


def get_or_create_conversation(
    db: Session, chatbot_id: str, session_id: str
) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.chatbot_id == chatbot_id,
            Conversation.session_id == session_id,
        )
        .first()
    )
    if conv is None:
        conv = Conversation(chatbot_id=chatbot_id, session_id=session_id, mode="ai")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def add_conversation_message(
    db: Session,
    conv: Conversation,
    sender: str,
    content: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv.id,
        sender=sender,
        content=content,
        agent_id=agent_id,
        agent_name=agent_name,
    )
    db.add(msg)
    conv.last_message_at = _now()
    if sender == "visitor":
        conv.unread = (conv.unread or 0) + 1
    db.commit()
    db.refresh(msg)
    return msg


def conversation_messages(db: Session, conversation_id: str, limit: int = 200) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .limit(limit)
        .all()
    )


def history_for_llm(db: Session, conversation_id: str, max_turns: int | None = None) -> list[dict]:
    """Build recent {role,content} history from the Message table.

    Includes agent messages (mapped to 'assistant') so the AI has continuity
    if a chat is handed back from a human.
    """
    limit = (max_turns or settings.history_max_turns) * 2
    rows = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.sender.in_(("visitor", "ai", "agent")),
        )
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for m in reversed(rows):
        out.append({"role": _SENDER_TO_ROLE.get(m.sender, "user"), "content": m.content})
    return out


def list_active_conversations(db: Session, org_id: str, limit: int = 100) -> list[dict]:
    """Conversations for an org's chatbots, newest activity first, with indicators."""
    rows = (
        db.query(Conversation, Chatbot.name)
        .join(Chatbot, Conversation.chatbot_id == Chatbot.id)
        .filter(Chatbot.org_id == org_id)
        .order_by(Conversation.last_message_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for conv, chatbot_name in rows:
        last = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .first()
        )
        result.append(
            {
                "id": conv.id,
                "chatbot_id": conv.chatbot_id,
                "chatbot_name": chatbot_name,
                "session_id": conv.session_id,
                "mode": conv.mode,
                "waiting_for_human": conv.waiting_for_human,
                "assigned_agent_id": conv.assigned_agent_id,
                "assigned_agent_name": conv.assigned_agent_name,
                "unread": conv.unread or 0,
                "last_message": last.content[:120] if last else "",
                "last_sender": last.sender if last else None,
                "last_message_at": conv.last_message_at.isoformat()
                if conv.last_message_at
                else None,
            }
        )
    return result


def conversation_summary(db: Session, conv: Conversation) -> dict:
    chatbot = db.get(Chatbot, conv.chatbot_id)
    last = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.id.desc())
        .first()
    )
    return {
        "id": conv.id,
        "chatbot_id": conv.chatbot_id,
        "chatbot_name": chatbot.name if chatbot else "",
        "session_id": conv.session_id,
        "mode": conv.mode,
        "waiting_for_human": conv.waiting_for_human,
        "assigned_agent_id": conv.assigned_agent_id,
        "assigned_agent_name": conv.assigned_agent_name,
        "unread": conv.unread or 0,
        "last_message": last.content[:120] if last else "",
        "last_sender": last.sender if last else None,
        "last_message_at": conv.last_message_at.isoformat()
        if conv.last_message_at
        else None,
    }
