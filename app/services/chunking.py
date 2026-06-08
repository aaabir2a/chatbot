"""Split text into overlapping chunks for embedding."""
from app.config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Character-based sliding window chunking with overlap.

    Tries to break on paragraph/sentence boundaries near the window edge so
    chunks stay semantically coherent for a small model.
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        # Prefer a clean break (paragraph, then sentence, then space) in the
        # last 20% of the window so we don't cut mid-word/sentence.
        if end < n:
            window_start = start + int(chunk_size * 0.8)
            break_at = -1
            for sep in ("\n\n", "\n", ". ", " "):
                idx = text.rfind(sep, window_start, end)
                if idx != -1:
                    break_at = idx + len(sep)
                    break
            if break_at != -1:
                end = break_at

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks
