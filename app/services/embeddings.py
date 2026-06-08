"""Local embeddings via sentence-transformers (lazy-loaded singleton)."""
import logging
import threading

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                logger.info("Loading embedding model: %s", settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Normalized for cosine similarity."""
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def warmup() -> None:
    """Force model load at startup so the first request isn't slow."""
    _get_model()
