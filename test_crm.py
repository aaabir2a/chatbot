#!/usr/bin/env python3
"""Test the CRM integration API (X-CRM-Key, no login).

- generate a CRM key via the dashboard (JWT)
- use ONLY the CRM key to read chatbots, conversations, transcript, leads
- verify auth: no key -> 401, revoked key -> 401
- verify a chatbot API key can NOT access /crm

Usage: python test_crm.py
"""
import sys

import httpx

BASE = "http://127.0.0.1:8000"
failures = []


def check(c, m):
    print(("  ok  " if c else " FAIL ") + m)
    if not c:
        failures.append(m)


def main() -> int:
    with httpx.Client(timeout=60) as c:
        tok = c.post(f"{BASE}/auth/login",
                     json={"email": "demo@example.com", "password": "supersecret1"}).json()
        H = {"Authorization": f"Bearer {tok['access_token']}"}

        # generate a CRM key
        created = c.post(f"{BASE}/crm-keys", headers=H, json={"name": "my-crm"}).json()
        crm_key = created["api_key"]
        check(crm_key.startswith("crm_"), "CRM key generated with crm_ prefix")
        CRM = {"X-CRM-Key": crm_key}

        # no key -> 401
        check(c.get(f"{BASE}/crm/leads").status_code == 401, "no CRM key -> 401")

        # chatbots
        bots = c.get(f"{BASE}/crm/chatbots", headers=CRM)
        check(bots.status_code == 200, "GET /crm/chatbots works with CRM key")
        blist = bots.json()["chatbots"]
        check(len(blist) >= 1, "CRM sees at least one chatbot")

        # conversations
        convs = c.get(f"{BASE}/crm/conversations?limit=5", headers=CRM).json()
        print(f"    conversations: {convs['count']}")
        check("conversations" in convs, "GET /crm/conversations returns a list")

        # transcript of the first conversation (if any)
        if convs["conversations"]:
            cid = convs["conversations"][0]["id"]
            tr = c.get(f"{BASE}/crm/conversations/{cid}/messages", headers=CRM).json()
            check("messages" in tr and "conversation" in tr,
                  "GET /crm/conversations/{id}/messages returns transcript")

        # leads
        leads = c.get(f"{BASE}/crm/leads?limit=10", headers=CRM).json()
        print(f"    leads: {leads['count']}")
        check("leads" in leads, "GET /crm/leads returns a list")
        # filter by status
        newleads = c.get(f"{BASE}/crm/leads?status=new", headers=CRM)
        check(newleads.status_code == 200, "leads filter by status works")

        # a chatbot API key must NOT access /crm
        import json
        fx = json.load(open("widget/.demo-fixture.json", encoding="utf-8-sig"))
        bad = c.get(f"{BASE}/crm/leads", headers={"X-CRM-Key": fx["apiKey"]})
        check(bad.status_code == 401, "chatbot API key rejected on /crm (401)")

        # revoke -> 401
        keys = c.get(f"{BASE}/crm-keys", headers=H).json()
        c.delete(f"{BASE}/crm-keys/{keys[0]['id']}", headers=H)
        check(c.get(f"{BASE}/crm/chatbots", headers=CRM).status_code == 401,
              "revoked CRM key -> 401")

    print()
    if failures:
        for f in failures:
            print("FAILED:", f)
        return 1
    print("PASSED: CRM integration API works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
