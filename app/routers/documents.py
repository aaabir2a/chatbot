"""GET /documents and DELETE /documents/{id}. Scoped to the API key's chatbot."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Chatbot, Document
from app.schemas import DeleteResponse, DocumentList
from app.services import vectorstore
from app.services.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=DocumentList)
def list_documents(
    chatbot: Chatbot = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> DocumentList:
    docs = (
        db.query(Document)
        .filter(Document.chatbot_id == chatbot.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentList(documents=docs, count=len(docs))


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(
    document_id: str,
    chatbot: Chatbot = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    # Scope the lookup to the caller's chatbot — can't touch another tenant's doc.
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.chatbot_id == chatbot.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        deleted = vectorstore.delete_document(chatbot.id, document_id)
        db.delete(doc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Delete failed for %s", document_id)
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    return DeleteResponse(document_id=document_id, deleted_chunks=deleted)
