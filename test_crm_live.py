#!/usr/bin/env python3
"""Test CRM live-agent flow: webhook events + takeover/reply/release.

Flow:
  1. visitor asks a question  -> webhook message.created (visitor + ai)
  2. visitor requests a human -> webhook conversation.human_requested
  3. CRM takes over           -> visitor widget gets mode=human
  4. visitor sends a message  -> webhook message.created (visitor); AI stays silent
  5. CRM replies              -> visitor widget gets agent_message
  6. CRM releases             -> visitor widget gets mode=ai

Usage: python test_crm_live.py
"""
import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"
RECV_PORT = 9098

with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]
CHATBOT_ID = FX["chatbotId"]

events = []  # webhook event payloads
failures = []


def check(c, m):
    print(("  ok  " if c else " FAIL ") + m)
    if not c:
        failures.append(m)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode()
        try:
            events.append(json.loads(body))
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def start_receiver():
    HTTPServer.allow_reuse_address = True
    srv = HTTPServer(("127.0.0.1", RECV_PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


async def recv_type(ws, t, timeout=90):
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if d.get("type") == t:
            return d


async def drain_answer(ws):
    while True:
        d = json.loads(await asyncio.wait_for(ws.recv(), 90))
        if d.get("type") == "ai_done":
            return


async def have_event(pred, timeout=15):
    for _ in range(timeout * 5):
        if any(pred(e) for e in events):
            return True
        await asyncio.sleep(0.2)
    return False


async def main() -> int:
    start_receiver()
    hook = f"http://127.0.0.1:{RECV_PORT}/hook"

    async with httpx.AsyncClient(timeout=30) as c:
        H = {"Authorization": f"Bearer {(await c.post(f'{BASE}/auth/login', json={'email':'demo@example.com','password':'supersecret1'})).json()['access_token']}"}
        await c.put(f"{BASE}/webhook", headers=H, json={"url": hook, "enabled": True})
        crm_key = (await c.post(f"{BASE}/crm-keys", headers=H, json={"name": "live"})).json()["api_key"]
    CRM = {"X-CRM-Key": crm_key}
    session = f"live-{uuid.uuid4().hex[:6]}"

    async with websockets.connect(f"{WS}/ws/chat/{session}?api_key={API_KEY}") as v:
        await recv_type(v, "history", 10)

        # 1. AI turn -> webhook message.created (visitor + ai).
        # Off-topic question => no-context fallback (no LLM needed), still an ai msg.
        await v.send(json.dumps({"type": "message", "text": "What is the capital of France?"}))
        await drain_answer(v)
        check(await have_event(lambda e: e["event"] == "message.created" and e["data"]["sender"] == "visitor"),
              "webhook: message.created (visitor)")
        check(await have_event(lambda e: e["event"] == "message.created" and e["data"]["sender"] == "ai"),
              "webhook: message.created (ai)")

        # 2. request human -> webhook conversation.human_requested
        events.clear()
        await v.send(json.dumps({"type": "request_human"}))
        await recv_type(v, "system", 10)
        check(await have_event(lambda e: e["event"] == "conversation.human_requested"),
              "webhook: conversation.human_requested")
        conv_id = None
        for e in events:
            if e["event"] == "conversation.human_requested":
                conv_id = e["data"]["conversation_id"]
        check(conv_id is not None, "got conversation_id from webhook")

        # 3. CRM takes over -> visitor sees mode=human
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/crm/conversations/{conv_id}/takeover",
                             headers=CRM, json={"agent_name": "Alex (CRM)"})
            check(r.status_code == 200 and r.json()["mode"] == "human", "CRM takeover -> mode human")
        m = await recv_type(v, "mode", 10)
        check(m.get("mode") == "human" and m.get("agent_name") == "Alex (CRM)",
              "visitor notified: chatting with Alex (CRM)")

        # 4. visitor message in human mode -> webhook, AI silent
        events.clear()
        await v.send(json.dumps({"type": "message", "text": "Yes please call me"}))
        check(await have_event(lambda e: e["event"] == "message.created" and e["data"]["sender"] == "visitor"),
              "webhook: visitor message during human mode")
        ai_silent = True
        try:
            await recv_type(v, "token", 4)
            ai_silent = False
        except asyncio.TimeoutError:
            pass
        check(ai_silent, "AI stayed silent while CRM handles it")

        # 5. CRM replies -> visitor gets agent_message
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/crm/conversations/{conv_id}/messages",
                             headers=CRM, json={"text": "Sure, calling you now.", "agent_name": "Alex (CRM)"})
            check(r.status_code == 200, "CRM send message -> 200")
        am = await recv_type(v, "agent_message", 10)
        check("calling you now" in am.get("text", "") and am.get("agent_name") == "Alex (CRM)",
              "visitor received the CRM agent reply live")

        # 6. CRM releases -> visitor back to AI
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/crm/conversations/{conv_id}/release", headers=CRM)
            check(r.status_code == 200 and r.json()["mode"] == "ai", "CRM release -> mode ai")
        m2 = await recv_type(v, "mode", 10)
        check(m2.get("mode") == "ai", "visitor notified: back with the AI")

    # cleanup
    async with httpx.AsyncClient(timeout=30) as c:
        H = {"Authorization": f"Bearer {(await c.post(f'{BASE}/auth/login', json={'email':'demo@example.com','password':'supersecret1'})).json()['access_token']}"}
        await c.put(f"{BASE}/webhook", headers=H, json={"enabled": False})

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: CRM live-agent (webhooks + takeover/reply/release) works.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
