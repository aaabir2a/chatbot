"""Document ingestion pipeline + background runner that tracks status."""
import logging

from app.db.base import SessionLocal
from app.db.models import Document
from app.services import embeddings, vectorstore
from app.services.chunking import chunk_text
from app.services.extract import extract_text

logger = logging.getLogger(__name__)


def ingest_to_vectors(chatbot_id: str, document_id: str, filename: str, data: bytes) -> int:
    """Extract -> chunk -> embed -> upsert. Returns chunk count. Raises on failure."""
    text = extract_text(filename, data)
    if not text:
        raise ValueError("No extractable text in document.")
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Document produced no chunks.")
    vectors = embeddings.embed_texts(chunks)
    return vectorstore.upsert_chunks(chatbot_id, document_id, filename, chunks, vectors)


def run_ingestion_background(
    chatbot_id: str, document_id: str, filename: str, data: bytes
) -> None:
    """Background task: ingest then mark the Document done/failed.

    Uses its own DB session (the request's session is already closed).
    """
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            count = ingest_to_vectors(chatbot_id, document_id, filename, data)
            doc.chunk_count = count
            doc.status = "done"
            doc.error = None
        except Exception as e:
            logger.exception("Background ingestion failed for %s", filename)
            doc.status = "failed"
            doc.error = str(e)[:1000]
        db.commit()
    finally:
        db.close()
