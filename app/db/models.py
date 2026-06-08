"""ORM models. Generic column types so they run on both Postgres and SQLite."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Auth: an org logs into the dashboard with email + password.
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chatbots: Mapped[list["Chatbot"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Chatbot(Base):
    __tablename__ = "chatbots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(
        Text, default="You are a helpful assistant.", nullable=False
    )
    tone: Mapped[str] = mapped_column(
        String(255), default="friendly and professional", nullable=False
    )
    welcome_message: Mapped[str] = mapped_column(
        Text, default="Hi! How can I help you today?", nullable=False
    )
    model: Mapped[str] = mapped_column(
        String(255), default=settings.llm_model, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped["Organization"] = relationship(back_populates="chatbots")
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="chatbot", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="chatbot", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="chatbot", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    chatbot_id: Mapped[str] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), default="default")
    # Non-secret prefix for display/identification (e.g. "sk_ab12cd34").
    prefix: Mapped[str] = mapped_column(String(20), index=True)
    # SHA-256 hex of the full key. Plaintext is NEVER stored.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chatbot: Mapped["Chatbot"] = relationship(back_populates="api_keys")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    chatbot_id: Mapped[str] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # Ingestion lifecycle: processing -> done | failed
    status: Mapped[str] = mapped_column(String(20), default="done", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chatbot: Mapped["Chatbot"] = relationship(back_populates="documents")


class ChatLog(Base):
    """One row per conversation turn. Doubles as analytics + history source."""

    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[str] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    user_message: Mapped[str] = mapped_column(Text)
    assistant_message: Mapped[str] = mapped_column(Text)
    # Turn number within the session (1-based).
    message_count: Mapped[int] = mapped_column(Integer, default=1)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Conversation(Base):
    """A visitor session. Mode decides whether AI or a live agent answers."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("chatbot_id", "session_id", name="uq_conv_chatbot_session"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    chatbot_id: Mapped[str] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    # "ai" (default) or "human" (a live agent has taken over; AI is paused).
    mode: Mapped[str] = mapped_column(String(10), default="ai", nullable=False)
    # Visitor explicitly asked for a human (shows in the inbox as waiting).
    waiting_for_human: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ephemeral agent identity currently handling (avoids collisions).
    assigned_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Visitor messages not yet seen by an agent.
    unread: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    chatbot: Mapped["Chatbot"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Every message, regardless of who sent it (visitor / ai / agent / system)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # "visitor" | "ai" | "agent" | "system"
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
