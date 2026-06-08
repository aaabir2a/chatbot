#!/usr/bin/env python3
"""End-to-end test: JWT auth + multi-tenant RAG + strict isolation.

Proves:
  1. Org signup -> JWT; create two chatbots; generate per-chatbot API keys.
  2. Scoped ingest + RAG chat answers from the chatbot's own document.
  3. TENANT ISOLATION: chatbot B cannot answer from chatbot A's document.
  4. Auth: missing key -> 401; revoked key -> 401; no JWT on /chatbots -> 401.

Usage:
    python test_e2e.py [--base-url http://localhost:8000]
"""
import argparse
import json
import sys
import uuid

import httpx

ACME_DOC = (
    "Acme Robotics Handbook. The flagship product is the Zephyr-7 autonomous "
    "warehouse drone. The Zephyr-7 has a maximum payload of 4.5 kilograms and a "
    "flight time of 38 minutes on a single charge."
)
GLOBEX_DOC = (
    "Globex Foods Handbook. Our signature product is the Nimbus-9 espresso "
    "machine. The Nimbus-9 brews at 9 bars of pressure and holds 1.8 liters."
)
Q = "What is the payload and flight time of the Zephyr-7?"


def stream_chat(client, base, api_key, message) -> str:
    answer = ""
    with client.stream(
        "POST", f"{base}/chat",
        headers={"X-API-Key": api_key},
        json={"message": message, "session_id": "s1"},
    ) as resp:
        resp.raise_for_status()
        event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                event = line[7:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if event == "token":
                    answer += data.get("token", "")
                elif event == "error":
                    raise RuntimeError(data)
    return answer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    tag = uuid.uuid4().hex[:6]
    failures = []

    with httpx.Client(timeout=300.0) as c:
        print(f"[health] {c.get(f'{base}/health').json()}\n")

        # 1. Signup -> JWT.
        tok = c.post(f"{base}/auth/signup", json={
            "name": f"Org-{tag}", "email": f"{tag}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        print(f"[signup] token={tok[:24]}...")

        # 2. Two chatbots + keys.
        acme = c.post(f"{base}/chatbots", headers=H, json={
            "name": "Acme", "system_prompt": "You are Acme support.",
            "tone": "concise and technical",
        }).json()
        globex = c.post(f"{base}/chatbots", headers=H, json={"name": "Globex"}).json()
        print(f"[chatbots] acme={acme['id']} globex={globex['id']}")

        acme_key = c.post(
            f"{base}/chatbots/{acme['id']}/api-keys", headers=H, json={"name": "k"}
        ).json()["api_key"]
        globex_key = c.post(
            f"{base}/chatbots/{globex['id']}/api-keys", headers=H, json={"name": "k"}
        ).json()["api_key"]
        print(f"[keys] acme={acme_key[:12]}... globex={globex_key[:12]}...\n")

        # 3. Ingest each doc with its own key.
        for key, name, doc in [
            (acme_key, "acme.md", ACME_DOC), (globex_key, "globex.md", GLOBEX_DOC)
        ]:
            r = c.post(f"{base}/ingest", headers={"X-API-Key": key},
                       files={"file": (name, doc.encode(), "text/markdown")})
            r.raise_for_status()
            print(f"[ingest {name}] {r.json()}")

        # 4. Acme answers from its own doc.
        ans = stream_chat(c, base, acme_key, Q)
        print(f"\n[chat acme] {ans}")
        if not ("4.5" in ans and "38" in ans):
            failures.append("Acme failed to answer from its own document.")

        # 5. ISOLATION: Globex must NOT know Acme's data.
        cross = stream_chat(c, base, globex_key, Q)
        print(f"[chat globex<-acme-q] {cross}")
        if "4.5" in cross or "38 minutes" in cross:
            failures.append("ISOLATION BREACH: Globex answered using Acme's data!")

        # 6. Auth checks.
        if c.post(f"{base}/chat", json={"message": "x", "session_id": "s"}).status_code != 401:
            failures.append("Missing-key /chat not rejected.")
        if c.get(f"{base}/chatbots").status_code != 401:
            failures.append("No-JWT /chatbots not rejected.")
        keys = c.get(f"{base}/chatbots/{acme['id']}/api-keys", headers=H).json()
        c.delete(f"{base}/api-keys/{keys[0]['id']}", headers=H)
        revoked = c.post(f"{base}/chat", headers={"X-API-Key": acme_key},
                         json={"message": "x", "session_id": "s"})
        print(f"\n[auth] no-key & no-jwt & revoked checked; revoked status={revoked.status_code}")
        if revoked.status_code != 401:
            failures.append("Revoked key still works.")

        # 7. Usage view populated.
        u = c.get(f"{base}/chatbots/{acme['id']}/usage", headers=H).json()
        print(f"[usage acme] messages={u['total_messages']} tokens={u['total_tokens']}")
        if u["total_messages"] < 1:
            failures.append("Usage not logged.")

        # 8. Cleanup.
        c.delete(f"{base}/chatbots/{acme['id']}", headers=H)
        c.delete(f"{base}/chatbots/{globex['id']}", headers=H)
        print("[cleanup] chatbots deleted")

    print()
    if failures:
        for f in failures:
            print(f"FAILED: {f}")
        return 1
    print("PASSED: JWT auth + multi-tenant RAG + isolation all work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
