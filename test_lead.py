#!/usr/bin/env python3
"""Test the lead-capture flow end to end, including chatting AFTER the form.

Scenario A (submit path):
  - set lead_after_messages=2
  - visitor sends 2 messages -> lead_form appears
  - visitor submits {name, phone} -> lead_saved + stored
  - REGRESSION: visitor keeps chatting -> AI must still reply

Scenario B (skip path, new session):
  - visitor sends 2 messages -> lead_form appears
  - visitor IGNORES the form (skip is client-side only)
  - REGRESSION: visitor keeps chatting -> AI must still reply

Usage: python test_lead.py
"""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"

with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]
CHATBOT_ID = FX["chatbotId"]

failures = []


def check(c, m):
    print(("  ok  " if c else " FAIL ") + m)
    if not c:
        failures.append(m)


async def recv_until(ws, types, timeout=60):
    want = {types} if isinstance(types, str) else set(types)
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") in want:
            return d


async def ask(ws, text, timeout=90) -> str:
    """Send a message and collect the streamed AI answer until ai_done."""
    await ws.send(json.dumps({"type": "message", "text": text}))
    answer = ""
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") == "token":
            answer += d.get("token", "")
        elif d.get("type") == "ai_done":
            return answer


async def login_headers(c) -> dict:
    r = await c.post(f"{BASE}/auth/login",
                     json={"email": "demo@example.com", "password": "supersecret1"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main():
    async with httpx.AsyncClient() as c:
        H = await login_headers(c)
        r = await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                          json={"lead_enabled": True, "lead_after_messages": 2})
        r.raise_for_status()
        check(r.json()["lead_after_messages"] == 2, "chatbot lead_after_messages set to 2")

    # ── Scenario A: submit, then keep chatting ──
    print("\n[A] submit path")
    session_a = f"lead-a-{uuid.uuid4().hex[:6]}"
    async with websockets.connect(f"{WS}/ws/chat/{session_a}?api_key={API_KEY}") as v:
        await recv_until(v, "history")
        a1 = await ask(v, "What is the return policy?")
        check("30" in a1, "msg1 answered from docs")
        await ask(v, "How long does shipping take?")
        lf = await recv_until(v, "lead_form", timeout=10)
        check(lf.get("type") == "lead_form", "lead_form shown after 2 messages")

        check("email" in (lf.get("fields") or []), "lead_form includes email field")
        await v.send(json.dumps({"type": "lead", "name": "Test User",
                                 "phone": "1300089547", "email": "test@example.com"}))
        saved = await recv_until(v, "lead_saved", timeout=10)
        check(saved.get("type") == "lead_saved", "lead_saved acknowledged")

        # THE BUG: chatting after submitting must still work on the SAME socket.
        a3 = await ask(v, "What is the return policy?")
        check("30" in a3, "REGRESSION: AI still replies after lead submit")

    # ── Scenario B: ignore the form (skip), keep chatting ──
    print("\n[B] skip path")
    session_b = f"lead-b-{uuid.uuid4().hex[:6]}"
    async with websockets.connect(f"{WS}/ws/chat/{session_b}?api_key={API_KEY}") as v:
        await recv_until(v, "history")
        await ask(v, "What is the return policy?")
        await ask(v, "How long does shipping take?")
        lf = await recv_until(v, "lead_form", timeout=10)
        check(lf.get("type") == "lead_form", "lead_form shown after 2 messages")

        # Skip notifies the server -> re-prompt scheduled after N more messages.
        await v.send(json.dumps({"type": "lead_skip"}))
        b3 = await ask(v, "What is the return policy?")
        check("30" in b3, "REGRESSION: AI still replies after skipping the form")

        # Not yet: only 1 message since the skip (threshold is 2 here).
        early = False
        try:
            await recv_until(v, "lead_form", timeout=3)
            early = True
        except asyncio.TimeoutError:
            pass
        check(not early, "form not re-shown before threshold")

        # 2nd message since skip -> form must re-appear.
        await ask(v, "Do you ship internationally?")
        lf2 = await recv_until(v, "lead_form", timeout=10)
        check(lf2.get("type") == "lead_form", "form RE-shown after N more messages post-skip")

    # ── Persistence ──
    async with httpx.AsyncClient() as c:
        H = await login_headers(c)
        leads = (await c.get(f"{BASE}/leads?chatbot_id={CHATBOT_ID}", headers=H)).json()
        mine = [l for l in leads if l["name"] == "Test User" and l["phone"] == "1300089547"]
        check(len(mine) >= 1, "lead stored and listed via /leads")
        if mine:
            check(mine[0].get("email") == "test@example.com", "lead email stored")
        # reset trigger back to 3
        await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                      json={"lead_after_messages": 3})

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: lead capture + post-form chat all work.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
