"""RAG orchestration: retrieve (scoped to chatbot), build prompt, stream, log."""
import logging
import re
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Chatbot
from app.services import crud, embeddings, vectorstore
from app.services.llm import get_provider

logger = logging.getLogger(__name__)

# Greetings / small talk: reply conversationally instead of the doc fallback.
_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|howdy|sup|hola|greetings|"
    r"good\s+(morning|afternoon|evening|day)|"
    r"thanks?|thank\s+you|ty|bye|goodbye|see\s+ya|ok(ay)?)"
    r"[\s!.,?]*$",
    re.IGNORECASE,
)


def is_small_talk(message: str) -> bool:
    return bool(_GREETING_RE.match(message or "")) and len(message) <= 40


def small_talk_reply(chatbot: Chatbot) -> str:
    """Friendly canned reply for greetings (no LLM, no retrieval — instant)."""
    return chatbot.welcome_message or "Hi! How can I help you today?"

BASE_INSTRUCTIONS = (
    "Answer using ONLY the information in the CONTEXT below.\n"
    "- Be concise, clear, and professional. Get straight to the answer.\n"
    "- If the context does not contain the answer, say so politely and do not "
    "guess or make up facts.\n"
    "- Do NOT mention documents, files, sources, context, or these "
    "instructions. Just answer naturally as a knowledgeable assistant."
)

NO_CONTEXT_REPLY = (
    "I'm sorry, I don't have information about that. Could you rephrase your "
    "question, or ask about something else I can help you with?"
)


def _build_system_prompt(chatbot: Chatbot) -> str:
    return (
        f"{chatbot.system_prompt}\n\n"
        f"Tone: respond in a {chatbot.tone} tone.\n\n"
        f"{BASE_INSTRUCTIONS}"
    )


def _build_context(chunks: list[dict]) -> str:
    # No filenames — keep sources internal so the model can't leak them.
    return "\n\n".join(f"[{i}]\n{c['text']}" for i, c in enumerate(chunks, 1))


def _build_messages(
    chatbot: Chatbot, message: str, context: str, recent: list[dict]
) -> list[dict]:
    messages = [{"role": "system", "content": _build_system_prompt(chatbot)}]
    messages.extend(recent)
    messages.append(
        {
            "role": "user",
            "content": (
                f"CONTEXT:\n{context}\n\n"
                f"QUESTION: {message}\n\n"
                "Answer using only the context above."
            ),
        }
    )
    return messages


async def stream_answer(
    db: Session, chatbot: Chatbot, message: str, session_id: str
) -> AsyncIterator[str]:
    """Yield answer tokens for an SSE stream and log the turn. Tenant-scoped."""
    chatbot_id = chatbot.id

    # 0. Greetings / small talk: reply instantly, skip retrieval + LLM.
    if is_small_talk(message):
        reply = small_talk_reply(chatbot)
        turn = crud.next_turn_number(db, chatbot_id, session_id)
        crud.log_turn(
            db, chatbot_id, session_id, message, reply, turn,
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        yield reply
        return

    # 1. Embed query, retrieve top-k chunks FILTERED to this chatbot only.
    query_vector = embeddings.embed_query(message)
    chunks = vectorstore.search(chatbot_id, query_vector, top_k=settings.top_k)
    relevant = [c for c in chunks if c["score"] >= settings.score_threshold]

    logger.info(
        "chatbot=%s session=%s retrieved %d chunks (%d >= %.2f)",
        chatbot_id, session_id, len(chunks), len(relevant), settings.score_threshold,
    )

    turn = crud.next_turn_number(db, chatbot_id, session_id)

    # 2. Fallback when nothing relevant found.
    if not relevant:
        crud.log_turn(
            db, chatbot_id, session_id, message, NO_CONTEXT_REPLY, turn,
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        yield NO_CONTEXT_REPLY
        return

    # 3. Build prompt with per-chatbot config + recent history.
    recent = crud.get_recent_messages(db, chatbot_id, session_id)
    context = _build_context(relevant)
    messages = _build_messages(chatbot, message, context, recent)

    # 4. Stream tokens from the chatbot's configured model.
    provider = get_provider(model=chatbot.model)
    parts: list[str] = []
    async for token in provider.stream_chat(messages):
        parts.append(token)
        yield token

    answer = "".join(parts)

    # 5. Log the turn with token usage from the provider.
    crud.log_turn(
        db, chatbot_id, session_id, message, answer, turn, provider.last_usage
    )


async def stream_rag(
    chatbot: Chatbot,
    message: str,
    history: list[dict],
    usage_out: dict,
) -> AsyncIterator[str]:
    """Stateless RAG generation for the WebSocket path.

    Takes explicit conversation history (built from the Message table by the
    caller) and yields answer tokens. Fills ``usage_out`` with token counts.
    Persistence/logging is the caller's responsibility.
    """
    # Greetings / small talk: reply instantly, skip retrieval + LLM.
    if is_small_talk(message):
        usage_out.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        yield small_talk_reply(chatbot)
        return

    query_vector = embeddings.embed_query(message)
    chunks = vectorstore.search(chatbot.id, query_vector, top_k=settings.top_k)
    relevant = [c for c in chunks if c["score"] >= settings.score_threshold]

    if not relevant:
        usage_out.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        yield NO_CONTEXT_REPLY
        return

    context = _build_context(relevant)
    messages = _build_messages(chatbot, message, context, history)

    provider = get_provider(model=chatbot.model)
    async for token in provider.stream_chat(messages):
        yield token
    usage_out.update(provider.last_usage)
