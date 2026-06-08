"""Qdrant vector store with strict per-chatbot tenant isolation.

Every vector carries a `chatbot_id` payload. All reads/writes/deletes filter on
it, so a chatbot can never see another chatbot's vectors.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.qdrant_path:
            # Embedded mode: in-process, on-disk store. No server needed.
            os.makedirs(settings.qdrant_path, exist_ok=True)
            logger.info("Using embedded Qdrant at %s", settings.qdrant_path)
            _client = QdrantClient(path=settings.qdrant_path)
        else:
            _client = QdrantClient(url=settings.qdrant_url, timeout=30.0)
    return _client


def ensure_collection() -> None:
    """Create the collection and tenant-isolation payload indexes if missing."""
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        logger.info("Creating Qdrant collection: %s", settings.qdrant_collection)
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(
                size=settings.embedding_dim,
                distance=qm.Distance.COSINE,
            ),
        )
    # Idempotent: ensure both filter fields are indexed.
    for field in ("chatbot_id", "document_id"):
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # already exists


def _tenant_filter(chatbot_id: str, document_id: str | None = None) -> qm.Filter:
    must = [
        qm.FieldCondition(key="chatbot_id", match=qm.MatchValue(value=chatbot_id))
    ]
    if document_id is not None:
        must.append(
            qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))
        )
    return qm.Filter(must=must)


def upsert_chunks(
    chatbot_id: str,
    document_id: str,
    filename: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> int:
    """Store chunk vectors tagged with chatbot_id + document_id."""
    client = get_client()
    ingested_at = datetime.now(timezone.utc).isoformat()
    points = [
        qm.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "chatbot_id": chatbot_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "text": chunk,
                "ingested_at": ingested_at,
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)
    logger.info(
        "Upserted %d chunks for chatbot=%s document=%s",
        len(points), chatbot_id, document_id,
    )
    return len(points)


def search(
    chatbot_id: str, query_vector: list[float], top_k: int | None = None
) -> list[dict]:
    """Top-k matching chunks WITHIN one chatbot's vectors only."""
    client = get_client()
    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=_tenant_filter(chatbot_id),
        limit=top_k or settings.top_k,
        with_payload=True,
    ).points
    return [
        {
            "text": r.payload.get("text", ""),
            "filename": r.payload.get("filename", ""),
            "document_id": r.payload.get("document_id", ""),
            "score": r.score,
        }
        for r in results
    ]


def delete_document(chatbot_id: str, document_id: str) -> int:
    """Delete a document's vectors, scoped to the owning chatbot."""
    client = get_client()
    flt = _tenant_filter(chatbot_id, document_id)
    count = client.count(
        collection_name=settings.qdrant_collection, count_filter=flt, exact=True
    ).count
    if count:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qm.FilterSelector(filter=flt),
            wait=True,
        )
        logger.info(
            "Deleted %d chunks for chatbot=%s document=%s",
            count, chatbot_id, document_id,
        )
    return count


def delete_chatbot(chatbot_id: str) -> int:
    """Purge all vectors belonging to a chatbot."""
    client = get_client()
    flt = _tenant_filter(chatbot_id)
    count = client.count(
        collection_name=settings.qdrant_collection, count_filter=flt, exact=True
    ).count
    if count:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qm.FilterSelector(filter=flt),
            wait=True,
        )
    return count
