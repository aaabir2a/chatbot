#!/usr/bin/env python3
"""Test outbound webhooks: config, signed delivery, and a real lead.created.

Spins up a local receiver, points the org webhook at it, then:
  1. POST /webhook/test  -> receiver gets a signed 'ping'
  2. submit a lead over WS -> receiver gets a signed 'lead.created'
Verifies the HMAC-SHA256 signature both times.

Usage: python test_webhook.py
"""
import asyncio
import hashlib
import hmac
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"
RECV_PORT = 9099

with open("widget/.demo-fixture.json", encoding="utf-8-sig") as f:
    FX = json.load(f)
API_KEY = FX["apiKey"]
CHATBOT_ID = FX["chatbotId"]

received = []  # list of (headers, body)
failures = []


def check(c, m):
    print(("  ok  " if c else " FAIL ") + m)
    if not c:
        failures.append(m)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode()
        received.append((dict(self.headers), body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def start_receiver():
    srv = HTTPServer(("127.0.0.1", RECV_PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def verify_sig(secret, headers, body) -> bool:
    got = headers.get("X-Webhook-Signature") or headers.get("x-webhook-signature")
    want = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return got == want


async def wait_for(pred, timeout=15):
    for _ in range(timeout * 5):
        if pred():
            return True
        await asyncio.sleep(0.2)
    return False


async def main() -> int:
    start_receiver()
    hook_url = f"http://127.0.0.1:{RECV_PORT}/hook"

    async with httpx.AsyncClient(timeout=30) as c:
        tok = (await c.post(f"{BASE}/auth/login",
               json={"email": "demo@example.com", "password": "supersecret1"})).json()
        H = {"Authorization": f"Bearer {tok['access_token']}"}

        # configure webhook
        cfg = (await c.put(f"{BASE}/webhook", headers=H,
               json={"url": hook_url, "enabled": True})).json()
        secret = cfg["secret"]
        check(bool(secret) and secret.startswith("whsec_"), "webhook secret generated")
        check(cfg["enabled"] and cfg["url"] == hook_url, "webhook url + enabled saved")

        # 1. test ping
        received.clear()
        r = (await c.post(f"{BASE}/webhook/test", headers=H)).json()
        check(r.get("delivered") is True, "POST /webhook/test reports delivered")
        got = await wait_for(lambda: len(received) >= 1)
        check(got, "receiver got the ping")
        if received:
            headers, body = received[-1]
            check(headers.get("X-Webhook-Event") == "ping", "ping event header correct")
            check(verify_sig(secret, headers, body), "ping signature valid (HMAC-SHA256)")

        # make sure the lead form triggers quickly
        await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                      json={"lead_enabled": True, "lead_after_messages": 1})

    # 2. real lead.created via WS
    received.clear()
    async with websockets.connect(f"{WS}/ws/chat/wh-{uuid.uuid4().hex[:6]}?api_key={API_KEY}") as v:
        await asyncio.wait_for(v.recv(), 10)  # history
        await v.send(json.dumps({"type": "message", "text": "hello"}))
        # submit a lead directly
        await v.send(json.dumps({"type": "lead", "name": "Hook Test",
                                 "phone": "1300111222", "email": "hook@test.com"}))

    got = await wait_for(lambda: any(
        json.loads(b).get("event") == "lead.created" for _, b in received), timeout=15)
    check(got, "receiver got lead.created webhook")
    lead_evt = next((b for _, b in received if json.loads(b).get("event") == "lead.created"), None)
    if lead_evt:
        headers = next(h for h, b in received if b == lead_evt)
        data = json.loads(lead_evt)["data"]
        check(data["name"] == "Hook Test" and data["phone"] == "1300111222",
              "lead.created payload has the lead data")
        check(verify_sig(secret, headers, lead_evt), "lead.created signature valid")

    # cleanup: disable webhook + reset trigger
    async with httpx.AsyncClient(timeout=30) as c:
        tok = (await c.post(f"{BASE}/auth/login",
               json={"email": "demo@example.com", "password": "supersecret1"})).json()
        H = {"Authorization": f"Bearer {tok['access_token']}"}
        await c.put(f"{BASE}/webhook", headers=H, json={"enabled": False})
        await c.patch(f"{BASE}/chatbots/{CHATBOT_ID}", headers=H,
                      json={"lead_after_messages": 3})

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: webhooks deliver signed events (ping + lead.created).")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
