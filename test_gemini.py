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
import os
import sys

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
        print("Check the key, the model name, and that the Gemini API is enabled.")
        return 1
    print(f"\n\nusage: {provider.last_usage}")
    if not text.strip():
        print("FAILED: empty response.")
        return 1
    print("PASSED: hosted LLM works. Put the same values in .env.prod on the VPS.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
