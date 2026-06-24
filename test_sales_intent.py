#!/usr/bin/env python3
"""Test sales-intent + no-answer triggers for the phone + lead form.

A) Sales intent ("can I get a free quote?") -> bot gives phone + lead form
   immediately (no waiting for N messages).
B) No-answer question (off-topic) -> bot offers phone + lead form.
C) A normal answerable question does NOT force the form early.

Usage: python test_sales_intent.py
"""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"
PHONE = "1300 089 547"

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


async def ask(ws, text, timeout=90):
    """Send a message, collect answer text until ai_done."""
    await ws.send(json.dumps({"type": "message", "text": text}))
    answer = ""
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") == "token":
            answer += d.get("token", "")
        elif d.get("type") == "ai_done":
            return answer


async def login_headers(c):
    r = await c.post(f"{BASE}/auth/login",
                     json={"email": "demo@example.com", "password": "supersecret1"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def saw_lead_form(ws, timeout=6):
    try:
        await recv_until(ws, "lead_form", timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def main():
    # Configure: lead on, threshold high (5) so only the triggers force the form;
    # set a sales phone.
    async with httpx.AsyncClient() as c:
        H = await login_headers(c)
        r = await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H, json={
            "lead_enabled": True, "lead_after_messages": 5, "sales_phone": PHONE,
        })
        r.raise_for_status()
        check(r.json()["sales_phone"] == PHONE, "sales_phone saved")

    # A) sales intent on first message
    print("\n[A] sales intent -> phone + form")
    async with websockets.connect(f"{WS}/ws/chat/sales-a-{uuid.uuid4().hex[:6]}?api_key={API_KEY}") as v:
        await recv_until(v, "history")
        ans = await ask(v, "Can I get a free quote?")
        print("    bot:", ans[:90])
        check(PHONE in ans, "bot reply shows the sales phone")
        check(await saw_lead_form(v), "lead form shown immediately on sales intent")

    # B) no-answer question
    print("\n[B] no answer -> phone + form")
    async with websockets.connect(f"{WS}/ws/chat/sales-b-{uuid.uuid4().hex[:6]}?api_key={API_KEY}") as v:
        await recv_until(v, "history")
        ans = await ask(v, "What is the capital of Brazil?")
        print("    bot:", ans[:90])
        check(await saw_lead_form(v), "lead form shown when bot has no answer")

    # C) normal answerable question does NOT force form early
    print("\n[C] normal question -> no early form")
    async with websockets.connect(f"{WS}/ws/chat/sales-c-{uuid.uuid4().hex[:6]}?api_key={API_KEY}") as v:
        await recv_until(v, "history")
        ans = await ask(v, "How long do solar panels last?")
        print("    bot:", ans[:90])
        forced = await saw_lead_form(v, timeout=4)
        check(not forced, "no lead form forced on a normal answerable question")

    # reset
    async with httpx.AsyncClient() as c:
        H = await login_headers(c)
        await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                      json={"lead_after_messages": 3})

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: sales-intent + no-answer trigger the phone + lead form.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
