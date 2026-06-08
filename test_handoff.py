#!/usr/bin/env python3
"""Live end-to-end test of human-agent handoff over WebSockets.

Simulates a visitor socket and an agent socket and verifies:
  1. AI mode: visitor message -> AI streams a reply.
  2. Visitor "talk to a human" -> agent inbox shows the conversation waiting.
  3. Agent take_over -> visitor notified mode=human.
  4. mode=human: visitor message relayed to agent; AI stays silent.
  5. Agent reply -> visitor receives agent_message.
  6. Agent release -> visitor notified mode=ai; AI answers again.

Requires the backend running with the fixture key/chatbot from earlier setup.

Usage: python test_handoff.py
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"

# Fixture from widget setup.
with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]
CHATBOT_ID = FX["chatbotId"]
SESSION = "handoff-test-1"

failures: list[str] = []


def check(cond: bool, msg: str):
    if not cond:
        failures.append(msg)
    print(("  ok  " if cond else " FAIL ") + msg)


async def recv_until(ws, want_type, timeout=60.0):
    """Collect events until one of `want_type` (str|set) arrives. Returns it."""
    want = {want_type} if isinstance(want_type, str) else set(want_type)
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout)
        d = json.loads(raw)
        if d.get("type") in want:
            return d


async def drain_ai_stream(ws, timeout=60.0):
    """Read token* then ai_done; return concatenated text."""
    text = ""
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") == "token":
            text += d.get("token", "")
        elif d.get("type") == "ai_done":
            return text


async def main():
    # Agent JWT.
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login",
                         json={"email": "demo@example.com", "password": "supersecret1"})
        r.raise_for_status()
        token = r.json()["access_token"]

    visitor_url = f"{WS}/ws/chat/{SESSION}?api_key={API_KEY}"
    agent_url = f"{WS}/ws/agent?token={token}"

    async with websockets.connect(visitor_url) as v, websockets.connect(agent_url) as a:
        # Handshakes
        vh = await recv_until(v, "history")
        check(vh.get("mode") == "ai", "visitor starts in AI mode")
        ainbox = await recv_until(a, "inbox")
        check("agent_id" in ainbox, "agent receives inbox on connect")

        # 1. AI answers
        print("\n[1] AI mode reply")
        await v.send(json.dumps({"type": "message", "text": "What is the return policy?"}))
        ai_text = await drain_ai_stream(v)
        print("    AI:", ai_text[:80])
        check("30" in ai_text, "AI answered from docs (mentions 30 days)")
        # agent should see visitor + ai messages
        await recv_until(a, "message")  # visitor msg
        await recv_until(a, "message")  # ai msg

        # 2. Visitor requests a human
        print("\n[2] Visitor requests human")
        await v.send(json.dumps({"type": "request_human"}))
        await recv_until(v, "system")
        upd = await recv_until(a, "conversation_updated")
        conv_id = upd["conversation"]["id"]
        check(upd["conversation"]["waiting_for_human"] is True, "agent sees waiting_for_human flag")

        # 3. Agent takes over
        print("\n[3] Agent take over")
        await a.send(json.dumps({"type": "take_over", "conversation_id": conv_id}))
        vmode = await recv_until(v, "mode")
        check(vmode.get("mode") == "human", "visitor notified mode=human")
        check(bool(vmode.get("agent_name")), "visitor told the agent name")
        await recv_until(a, "mode")

        # 4. Visitor message in human mode -> relayed, AI silent
        print("\n[4] Human mode: visitor -> agent, AI silent")
        await v.send(json.dumps({"type": "message", "text": "Can you help me with a refund?"}))
        relayed = await recv_until(a, "message")
        check(relayed["message"]["sender"] == "visitor", "agent receives relayed visitor message")
        # ensure NO ai token arrives for the visitor within a short window
        ai_silent = False
        try:
            await asyncio.wait_for(recv_until(v, {"token", "ai_done"}), timeout=4.0)
        except asyncio.TimeoutError:
            ai_silent = True
        check(ai_silent, "AI did NOT respond while in human mode")

        # 5. Agent replies -> visitor receives
        print("\n[5] Agent reply -> visitor")
        await a.send(json.dumps({"type": "message", "conversation_id": conv_id,
                                 "text": "Sure! I can process that refund for you."}))
        am = await recv_until(v, "agent_message")
        check("refund" in am.get("text", "").lower(), "visitor receives agent message")

        # 6. Agent releases -> AI resumes
        print("\n[6] Release -> back to AI")
        await a.send(json.dumps({"type": "release", "conversation_id": conv_id}))
        vmode2 = await recv_until(v, "mode")
        check(vmode2.get("mode") == "ai", "visitor notified mode=ai")
        await recv_until(a, "mode")
        await v.send(json.dumps({"type": "message", "text": "What is the return policy?"}))
        ai_text2 = await drain_ai_stream(v)
        check("30" in ai_text2, "AI answers again after release")

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: human-agent handoff works end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
