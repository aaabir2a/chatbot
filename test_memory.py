#!/usr/bin/env python3
"""Test multi-turn memory: a follow-up that refers to the previous turn.

Q1: "How much is the 6.6kw package?"  -> ~$3,300-3,700
Q2: "what about the 10kw one?"        -> must resolve to the 10kw package
                                         (~$5,400-5,800), NOT the no-answer fallback.

Usage: python test_memory.py
"""
import asyncio
import json
import sys
import uuid

import websockets


def p(*args):
    print(*[str(a).encode("ascii", "replace").decode() for a in args])

WS = "ws://127.0.0.1:8000"

with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]

failures = []


def check(c, m):
    p(("  ok  " if c else " FAIL ") + m)
    if not c:
        failures.append(m)


async def ask(ws, text, timeout=90):
    await ws.send(json.dumps({"type": "message", "text": text}))
    answer = ""
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") == "token":
            answer += d.get("token", "")
        elif d.get("type") == "ai_done":
            return answer


async def main():
    url = f"{WS}/ws/chat/mem-{uuid.uuid4().hex[:6]}?api_key={API_KEY}"
    async with websockets.connect(url) as v:
        # drain history
        await asyncio.wait_for(v.recv(), 10)

        a1 = await ask(v, "How much is the 6.6kw package?")
        p("Q1 6.6kw ->", a1[:120], "\n")
        check("3,3" in a1 or "3300" in a1 or "3,7" in a1, "Q1 answered with 6.6kw price")

        a2 = await ask(v, "what about the 10kw one?")
        p("Q2 (follow-up) ->", a2[:160], "\n")
        # Must resolve the follow-up to the 10kw package, not fall back.
        fallback = "don't have information" in a2.lower() or "rephrase" in a2.lower()
        check(not fallback, "follow-up did NOT hit the no-answer fallback")
        check("5,4" in a2 or "5400" in a2 or "5,8" in a2 or "10" in a2,
              "follow-up resolved to the 10kw package")

    p()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    p("PASSED: multi-turn follow-up uses prior context.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
