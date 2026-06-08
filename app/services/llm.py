"""LLM provider abstraction.

Callers use `stream_chat(...)` then read `.last_usage` for token counts. Swap
providers by changing `LLM_PROVIDER` in .env (and adding a class below).
"""
import json
import logging
from typing import AsyncIterator, Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    last_usage: dict

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        ...


class OllamaProvider:
    """Streams tokens from an Ollama server via /api/chat."""

    def __init__(self, model: str | None = None) -> None:
        self.url = settings.ollama_url.rstrip("/")
        self.model = model or settings.llm_model
        self.last_usage: dict = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": settings.llm_temperature,
                "num_ctx": settings.llm_num_ctx,
            },
        }
        timeout = httpx.Timeout(settings.llm_timeout, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{self.url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Non-JSON line from Ollama: %s", line[:120])
                        continue
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        prompt_tok = data.get("prompt_eval_count", 0) or 0
                        completion_tok = data.get("eval_count", 0) or 0
                        self.last_usage = {
                            "prompt_tokens": prompt_tok,
                            "completion_tokens": completion_tok,
                            "total_tokens": prompt_tok + completion_tok,
                        }
                        break


_PROVIDERS = {"ollama": OllamaProvider}


def get_provider(model: str | None = None) -> LLMProvider:
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
            f"Available: {sorted(_PROVIDERS)}"
        )
    return provider_cls(model=model)
