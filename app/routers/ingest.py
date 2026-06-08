"""POST /ingest — synchronous ingest via API key (external clients)."""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Chatbot, Document
from app.schemas import IngestResponse
from app.services.auth import require_api_key
from app.services.ingestion import ingest_to_vectors
from app.services.ratelimit import RATE_LIMIT, limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(RATE_LIMIT)
async def ingest(
    request: Request,
    file: UploadFile = File(...),
    chatbot: Chatbot = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> IngestResponse:
    filename = file.filename or "upload"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    doc = Document(chatbot_id=chatbot.id, filename=filename, chunk_count=0, status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        count = ingest_to_vectors(chatbot.id, doc.id, filename, data)
        doc.chunk_count = count
        doc.status = "done"
        db.commit()
    except Exception as e:
        doc.status = "failed"
        doc.error = str(e)[:1000]
        db.commit()
        logger.exception("Ingestion failed for %s", filename)
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {e}")

    return IngestResponse(document_id=doc.id, filename=filename, chunk_count=count)
