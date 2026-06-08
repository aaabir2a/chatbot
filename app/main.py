"""FastAPI application entrypoint."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db.base import Base, engine
from app.routers import auth, chat, conversations, documents, ingest, manage, ws
from app.services import embeddings, vectorstore
from app.services.ratelimit import limiter

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: DB, Qdrant collection, embedding model")
    if settings.auto_create_tables:
        # Import models so metadata is populated, then create missing tables.
        from app.db import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
    vectorstore.ensure_collection()
    embeddings.warmup()
    logger.info("Startup complete")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Self-hosted Multi-tenant RAG Chatbot",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for the dashboard frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (per API key — see services/ratelimit.py).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)          # /auth/* (JWT)
app.include_router(manage.router)        # dashboard management (JWT, org-scoped)
app.include_router(conversations.router) # /conversations (JWT, live chats inbox)
app.include_router(ws.router)            # /ws/chat/{session}, /ws/agent (WebSocket)
app.include_router(ingest.router)        # /ingest (API key)
app.include_router(chat.router)          # /chat (API key)
app.include_router(documents.router)     # /documents (API key)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "default_model": settings.llm_model,
    }


# Serve the built embeddable widget so the dashboard's embed snippet works
# out of the box: <script src="{backend}/widget.js" ...>.
@app.get("/widget.js", tags=["widget"])
async def widget_js() -> FileResponse:
    path = os.path.join(os.getcwd(), "widget", "dist", "widget.js")
    if not os.path.isfile(path):
        raise HTTPException(
            status_code=404,
            detail="widget.js not built. Run `npm run build` in ./widget.",
        )
    return FileResponse(
        path,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )
