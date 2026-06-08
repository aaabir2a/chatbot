"""Org-scoped management API (JWT). Powers the dashboard.

Everything here is scoped to the logged-in organization via require_org, and
chatbot-level routes enforce ownership via owned_chatbot().
"""
import json
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy import func
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.db.base import get_db
from app.db.models import ApiKey, ChatLog, Chatbot, Document, Organization
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyInfo,
    ChatbotCreate,
    ChatbotInfo,
    ChatbotUpdate,
    ChatRequest,
    DocumentInfo,
    DocumentList,
    IngestResponse,
    RecentConversation,
    UsageResponse,
)
from app.services import rag, vectorstore
from app.services.auth import generate_api_key, owned_chatbot, require_org
from app.services.ingestion import run_ingestion_background

logger = logging.getLogger(__name__)
router = APIRouter(tags=["manage"], dependencies=[Depends(require_org)])


# ── Chatbots ───────────────────────────────────────────────────────────────
@router.get("/chatbots", response_model=list[ChatbotInfo])
def list_chatbots(
    org: Organization = Depends(require_org), db: Session = Depends(get_db)
) -> list[Chatbot]:
    return (
        db.query(Chatbot)
        .filter(Chatbot.org_id == org.id)
        .order_by(Chatbot.created_at.desc())
        .all()
    )


@router.post("/chatbots", response_model=ChatbotInfo, status_code=201)
def create_chatbot(
    body: ChatbotCreate,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> Chatbot:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    chatbot = Chatbot(org_id=org.id, **fields)
    db.add(chatbot)
    db.commit()
    db.refresh(chatbot)
    return chatbot


@router.get("/chatbots/{chatbot_id}", response_model=ChatbotInfo)
def get_chatbot(
    chatbot_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> Chatbot:
    return owned_chatbot(db, org, chatbot_id)


@router.patch("/chatbots/{chatbot_id}", response_model=ChatbotInfo)
def update_chatbot(
    chatbot_id: str,
    body: ChatbotUpdate,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> Chatbot:
    chatbot = owned_chatbot(db, org, chatbot_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(chatbot, k, v)
    db.commit()
    db.refresh(chatbot)
    return chatbot


@router.delete("/chatbots/{chatbot_id}", status_code=204)
def delete_chatbot(
    chatbot_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> None:
    chatbot = owned_chatbot(db, org, chatbot_id)
    vectorstore.delete_chatbot(chatbot_id)
    db.delete(chatbot)
    db.commit()


# ── API keys ───────────────────────────────────────────────────────────────
@router.get("/chatbots/{chatbot_id}/api-keys", response_model=list[ApiKeyInfo])
def list_api_keys(
    chatbot_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    owned_chatbot(db, org, chatbot_id)
    return (
        db.query(ApiKey)
        .filter(ApiKey.chatbot_id == chatbot_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post(
    "/chatbots/{chatbot_id}/api-keys", response_model=ApiKeyCreated, status_code=201
)
def create_api_key(
    chatbot_id: str,
    body: ApiKeyCreate,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    owned_chatbot(db, org, chatbot_id)
    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        chatbot_id=chatbot_id, name=body.name, prefix=prefix, key_hash=key_hash
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreated(
        id=api_key.id,
        chatbot_id=chatbot_id,
        name=api_key.name,
        prefix=prefix,
        api_key=full_key,  # shown only once
        created_at=api_key.created_at,
    )


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> dict:
    api_key = db.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found.")
    owned_chatbot(db, org, api_key.chatbot_id)  # ownership check
    api_key.revoked = True
    db.commit()
    return {"id": key_id, "revoked": True}


# ── Documents (dashboard-managed, async ingest with status) ─────────────────
@router.get("/chatbots/{chatbot_id}/documents", response_model=DocumentList)
def list_documents(
    chatbot_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> DocumentList:
    owned_chatbot(db, org, chatbot_id)
    docs = (
        db.query(Document)
        .filter(Document.chatbot_id == chatbot_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentList(documents=docs, count=len(docs))


@router.post("/chatbots/{chatbot_id}/documents", response_model=DocumentInfo, status_code=202)
async def upload_document(
    chatbot_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> Document:
    owned_chatbot(db, org, chatbot_id)
    filename = file.filename or "upload"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Create the row as 'processing' and ingest in the background.
    doc = Document(
        chatbot_id=chatbot_id, filename=filename, chunk_count=0, status="processing"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background.add_task(run_ingestion_background, chatbot_id, doc.id, filename, data)
    return doc


@router.delete(
    "/chatbots/{chatbot_id}/documents/{document_id}", response_model=IngestResponse
)
def delete_document(
    chatbot_id: str,
    document_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> IngestResponse:
    owned_chatbot(db, org, chatbot_id)
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.chatbot_id == chatbot_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    deleted = vectorstore.delete_document(chatbot_id, document_id)
    db.delete(doc)
    db.commit()
    return IngestResponse(
        document_id=document_id, filename=doc.filename, chunk_count=deleted
    )


# ── Usage ───────────────────────────────────────────────────────────────────
@router.get("/chatbots/{chatbot_id}/usage", response_model=UsageResponse)
def usage(
    chatbot_id: str,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> UsageResponse:
    owned_chatbot(db, org, chatbot_id)
    agg = (
        db.query(
            func.count(ChatLog.id),
            func.count(func.distinct(ChatLog.session_id)),
            func.coalesce(func.sum(ChatLog.prompt_tokens), 0),
            func.coalesce(func.sum(ChatLog.completion_tokens), 0),
            func.coalesce(func.sum(ChatLog.total_tokens), 0),
        )
        .filter(ChatLog.chatbot_id == chatbot_id)
        .one()
    )
    recent_rows = (
        db.query(ChatLog)
        .filter(ChatLog.chatbot_id == chatbot_id)
        .order_by(ChatLog.id.desc())
        .limit(10)
        .all()
    )
    return UsageResponse(
        chatbot_id=chatbot_id,
        total_messages=int(agg[0] or 0),
        total_sessions=int(agg[1] or 0),
        prompt_tokens=int(agg[2] or 0),
        completion_tokens=int(agg[3] or 0),
        total_tokens=int(agg[4] or 0),
        recent=[
            RecentConversation(
                session_id=r.session_id,
                user_message=r.user_message,
                assistant_message=r.assistant_message,
                total_tokens=r.total_tokens,
                created_at=r.created_at,
            )
            for r in recent_rows
        ],
    )


# ── Test chat (dashboard, JWT-scoped, streamed) ─────────────────────────────
@router.post("/chatbots/{chatbot_id}/test-chat")
def test_chat(
    chatbot_id: str,
    body: ChatRequest,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    chatbot = owned_chatbot(db, org, chatbot_id)

    async def event_generator():
        try:
            async for token in rag.stream_answer(
                db, chatbot, body.message, body.session_id
            ):
                yield {"event": "token", "data": json.dumps({"token": token})}
            yield {"event": "done", "data": json.dumps({"done": True})}
        except Exception as e:
            logger.exception("Test chat failed for chatbot=%s", chatbot_id)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
