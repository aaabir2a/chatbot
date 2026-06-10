#!/usr/bin/env python3
"""Test the lead-capture flow end to end.

- set lead_after_messages=2 on the chatbot (via JWT)
- visitor sends 2 messages -> backend emits lead_form
- visitor submits {name, phone} -> lead_saved + Lead stored
- GET /leads shows it

Usage: python test_lead.py
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"

with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]
CHATBOT_ID = FX["chatbotId"]
SESSION = "lead-test-1"

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


async def drain_answer(ws):
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), 60))
        if d.get("type") == "ai_done":
            return


async def main():
    async with httpx.AsyncClient() as c:
        tok = c.post if False else None
        r = await c.post(f"{BASE}/auth/login",
                         json={"email": "demo@example.com", "password": "supersecret1"})
        r.raise_for_status()
        token = r.json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}
        # enable lead capture, trigger after 2 messages
        r = await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                          json={"lead_enabled": True, "lead_after_messages": 2})
        r.raise_for_status()
        check(r.json()["lead_after_messages"] == 2, "chatbot lead_after_messages set to 2")

    async with websockets.connect(f"{WS}/ws/chat/{SESSION}?api_key={API_KEY}") as v:
        await recv_until(v, "history")

        # message 1
        await v.send(json.dumps({"type": "message", "text": "What is the return policy?"}))
        await drain_answer(v)

        # message 2 -> should trigger lead_form after the answer
        await v.send(json.dumps({"type": "message", "text": "How long does shipping take?"}))
        await drain_answer(v)

        lf = await recv_until(v, "lead_form", timeout=10)
        check(lf.get("type") == "lead_form", "lead_form shown after 2 messages")
        check("name" in (lf.get("fields") or []) and "phone" in (lf.get("fields") or []),
              "lead_form requests name + phone")

        # submit the lead
        await v.send(json.dumps({"type": "lead", "name": "Test User", "phone": "1300089547"}))
        saved = await recv_until(v, "lead_saved", timeout=10)
        check(saved.get("type") == "lead_saved", "lead_saved acknowledgement received")

    # confirm it persisted
    await asyncio.sleep(0.5)
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login",
                         json={"email": "demo@example.com", "password": "supersecret1"})
        token = r.json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}
        leads = (await c.get(f"{BASE}/leads?chatbot_id={CHATBOT_ID}", headers=H)).json()
        mine = [l for l in leads if l["name"] == "Test User" and l["phone"] == "1300089547"]
        check(len(mine) >= 1, "lead stored and listed via /leads")
        if mine:
            check(mine[0]["status"] == "new", "new lead has status 'new'")
        # reset chatbot trigger back to 3
        await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                      json={"lead_after_messages": 3})

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: lead capture flow works end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
