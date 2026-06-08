FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

WORKDIR /code

# System deps occasionally needed by sentence-transformers / pypdf wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Pre-download the embedding model into the image so first boot is fast and
# works offline. Cached under HF_HOME (/models).
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
