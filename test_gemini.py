#!/usr/bin/env python3
"""Verify a hosted LLM key + model work via the OpenAI-compatible provider.

Your key is read from the environment or argv — NEVER hardcode it.

Windows (PowerShell):
    $env:LLM_API_KEY="AIza..."; python test_gemini.py
    # or a different model:
    $env:LLM_API_KEY="AIza..."; $env:LLM_MODEL="gemini-2.5-flash"; python test_gemini.py

Linux/Mac:
    LLM_API_KEY=AIza... python test_gemini.py
"""
import asyncio
import json
import os
import sys

import httpx

# Configure the provider via env BEFORE importing the app (env > .env file).
KEY = os.environ.get("LLM_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not KEY:
    print("Provide the key: $env:LLM_API_KEY='AIza...'; python test_gemini.py")
    sys.exit(2)

os.environ["LLM_PROVIDER"] = os.environ.get("LLM_PROVIDER", "gemini")
os.environ["LLM_API_KEY"] = KEY
os.environ["LLM_MODEL"] = os.environ.get("LLM_MODEL", "gemini-2.0-flash")

from app.services.llm import get_provider  # noqa: E402
from app.config import settings  # noqa: E402


async def _diagnose() -> None:
    """Direct non-streaming call to surface the exact API error body."""
    base = "https://generativelanguage.googleapis.com/v1beta/openai"
    url = f"{base}/chat/completions"
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": "hi"}],
    }
    print("\n--- diagnostic (non-streaming) ---")
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=body,
                             headers={"Authorization": f"Bearer {settings.llm_api_key}"})
        print(f"status: {r.status_code}")
        try:
            err = r.json()
            print(json.dumps(err, indent=2)[:1500])
        except Exception:
            print(r.text[:1500])
    except Exception as e:
        print(f"diagnostic call failed: {e}")
    # List models the key can actually use.
    print("\n--- models available to this key ---")
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": settings.llm_api_key},
            )
        if r.status_code == 200:
            names = [m["name"].replace("models/", "")
                     for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
            print(", ".join(names) or "(none)")
        else:
            print(f"status {r.status_code}: {r.text[:400]}")
    except Exception as e:
        print(f"model list failed: {e}")


async def main() -> int:
    print(f"provider={settings.llm_provider}  model={settings.llm_model}")
    provider = get_provider()
    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "In one sentence, what is solar energy?"},
    ]
    print("streaming reply:\n  ", end="", flush=True)
    text = ""
    try:
        async for token in provider.stream_chat(messages):
            text += token
            print(token, end="", flush=True)
    except Exception as e:
        print(f"\n\nFAILED: {type(e).__name__}: {e}")
        # Make a direct non-streaming call to read the full error body.
        await _diagnose()
        return 1
    print(f"\n\nusage: {provider.last_usage}")
    if not text.strip():
        print("FAILED: empty response.")
        return 1
    print("PASSED: hosted LLM works. Put the same values in .env.prod on the VPS.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
