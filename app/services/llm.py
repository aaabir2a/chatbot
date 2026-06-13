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


# Default OpenAI-compatible endpoints. Gemini, Groq, DeepSeek and OpenAI all
# speak the same /chat/completions wire format, so one class covers them all.
_OPENAI_COMPAT_BASES = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "openai_compat": "",  # must set LLM_API_BASE
}


def _estimate_tokens(text: str) -> int:
    return max(0, len(text) // 4)  # ~4 chars/token heuristic


class OpenAICompatProvider:
    """Streams from any OpenAI-compatible chat API (Gemini/Groq/OpenAI/DeepSeek).

    Auth: `Authorization: Bearer <LLM_API_KEY>`. Messages are already in the
    OpenAI format (system/user/assistant), so they pass straight through.
    """

    def __init__(self, model: str | None = None) -> None:
        base = (settings.llm_api_base or _OPENAI_COMPAT_BASES.get(settings.llm_provider, "")).rstrip("/")
        if not base:
            raise ValueError(
                f"LLM_API_BASE is required for provider '{settings.llm_provider}'."
            )
        if not settings.llm_api_key:
            raise ValueError(f"LLM_API_KEY is required for provider '{settings.llm_provider}'.")
        self.base = base
        self.key = settings.llm_api_key
        # A per-chatbot Ollama tag (e.g. "qwen2.5:1.5b") is meaningless to a
        # hosted API — fall back to the configured remote model name.
        self.model = model if (model and ":" not in model) else settings.llm_model
        self.last_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": settings.llm_temperature,
        }
        headers = {"Authorization": f"Bearer {self.key}"}
        timeout = httpx.Timeout(settings.llm_timeout, connect=10.0)
        prompt_est = _estimate_tokens(
            "".join(m.get("content", "") for m in messages)
        )
        completion_chars = 0
        usage_seen = False

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{self.base}/chat/completions", json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for raw in resp.aiter_lines():
                    line = raw.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if choices:
                        token = (choices[0].get("delta") or {}).get("content") or ""
                        if token:
                            completion_chars += len(token)
                            yield token
                    usage = obj.get("usage")
                    if usage:
                        usage_seen = True
                        pt = usage.get("prompt_tokens", 0) or 0
                        ct = usage.get("completion_tokens", 0) or 0
                        self.last_usage = {
                            "prompt_tokens": pt,
                            "completion_tokens": ct,
                            "total_tokens": usage.get("total_tokens", pt + ct) or (pt + ct),
                        }

        if not usage_seen:  # provider didn't report usage → estimate
            ct = _estimate_tokens_from_chars(completion_chars)
            self.last_usage = {
                "prompt_tokens": prompt_est,
                "completion_tokens": ct,
                "total_tokens": prompt_est + ct,
            }


def _estimate_tokens_from_chars(chars: int) -> int:
    return max(0, chars // 4)


_PROVIDERS = {
    "ollama": OllamaProvider,
    "gemini": OpenAICompatProvider,
    "groq": OpenAICompatProvider,
    "openai": OpenAICompatProvider,
    "deepseek": OpenAICompatProvider,
    "openai_compat": OpenAICompatProvider,
}


def get_provider(model: str | None = None) -> LLMProvider:
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
            f"Available: {sorted(_PROVIDERS)}"
        )
    return provider_cls(model=model)
