"""Pydantic models for request/response validation."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth / Organizations ────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class OrgInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org: OrgInfo


# ── Chatbots ───────────────────────────────────────────────────────────────
class ChatbotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None, max_length=8000)
    tone: str | None = Field(default=None, max_length=255)
    welcome_message: str | None = Field(default=None, max_length=2000)
    model: str | None = Field(default=None, max_length=255)
    lead_enabled: bool | None = None
    lead_after_messages: int | None = Field(default=None, ge=1, le=20)


class ChatbotUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = Field(default=None, max_length=8000)
    tone: str | None = Field(default=None, max_length=255)
    welcome_message: str | None = Field(default=None, max_length=2000)
    model: str | None = Field(default=None, max_length=255)
    lead_enabled: bool | None = None
    lead_after_messages: int | None = Field(default=None, ge=1, le=20)


class ChatbotInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    org_id: str
    name: str
    system_prompt: str
    tone: str
    welcome_message: str
    model: str
    lead_enabled: bool
    lead_after_messages: int
    created_at: datetime


# ── API keys ───────────────────────────────────────────────────────────────
class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", max_length=255)


class ApiKeyCreated(BaseModel):
    """Returned ONCE on creation — includes the plaintext key."""
    id: str
    chatbot_id: str
    name: str
    prefix: str
    api_key: str  # plaintext, shown only here
    created_at: datetime


class ApiKeyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chatbot_id: str
    name: str
    prefix: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None


# ── Ingestion ──────────────────────────────────────────────────────────────
class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


# ── Chat ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str = Field(..., min_length=1, max_length=128)


# ── Documents ──────────────────────────────────────────────────────────────
class DocumentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    chunk_count: int
    status: str
    error: str | None = None
    created_at: datetime


class DocumentList(BaseModel):
    documents: list[DocumentInfo]
    count: int


class DeleteResponse(BaseModel):
    document_id: str
    deleted_chunks: int


# ── Leads ────────────────────────────────────────────────────────────────────
class LeadInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chatbot_id: str
    conversation_id: str | None
    name: str
    phone: str
    status: str
    created_at: datetime


class LeadStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|contacted)$")


# ── Usage ────────────────────────────────────────────────────────────────────
class RecentConversation(BaseModel):
    session_id: str
    user_message: str
    assistant_message: str
    total_tokens: int
    created_at: datetime


class UsageResponse(BaseModel):
    chatbot_id: str
    total_messages: int          # number of turns logged
    total_sessions: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    recent: list[RecentConversation]


class ErrorResponse(BaseModel):
    detail: str
