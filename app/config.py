"""Application configuration loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM (provider abstracted; swap by changing these two values) ---
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:3b"
    llm_temperature: float = 0.2
    # Small context window tuned for a 3B model on CPU.
    llm_num_ctx: int = 4096
    llm_timeout: float = 120.0

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384  # all-MiniLM-L6-v2 output size

    # --- Vector DB ---
    # If qdrant_path is set, run Qdrant embedded (in-process, on-disk) — no
    # server/Docker needed. Good for local dev/test. Leave empty to use a
    # Qdrant server at qdrant_url (production / docker-compose).
    qdrant_url: str = "http://localhost:6333"
    qdrant_path: str = ""
    qdrant_collection: str = "documents"

    # --- Retrieval / chunking ---
    top_k: int = 4
    score_threshold: float = 0.30  # below this, treat as "no relevant context"
    chunk_size: int = 800          # characters per chunk
    chunk_overlap: int = 150       # character overlap between chunks

    # --- Conversation history ---
    history_max_turns: int = 6  # recent turns kept in the prompt

    # --- Relational DB (Postgres in prod, SQLite for local test) ---
    # Examples:
    #   sqlite:///data/app.db
    #   postgresql+psycopg2://rag:rag@postgres:5432/rag
    database_url: str = "sqlite:///data/app.db"
    # Create tables on startup if missing (dev convenience). Use Alembic in prod.
    auto_create_tables: bool = True

    # --- Auth / tenancy ---
    api_key_header: str = "X-API-Key"
    # If set, management (admin) endpoints require this token via X-Admin-Token.
    # Empty = admin endpoints are open (self-hosted single-operator default).
    admin_token: str = ""

    # --- Rate limiting (per API key) ---
    rate_limit: str = "30/minute"

    # --- JWT (org dashboard auth) ---
    jwt_secret: str = "change-me-in-prod"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    # --- CORS (frontend dev origins, comma-separated) ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- App ---
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
