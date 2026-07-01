# Chatbot → CRM Integration — Developer Guide

This guide is for the developer integrating our chatbot platform with your CRM.
It's a simple **REST API, authenticated by one key, no login/OAuth**. You can
read conversations, full transcripts, and leads, and write a lead's status back.

---

## 1. What you get

- **Leads** captured by the chatbot's callback form (name, phone, email).
- **Conversations** (each website visitor session) with metadata.
- **Transcripts** — every message (visitor / AI / live agent / system).
- **Write-back** — mark a lead `new` → `contacted` from your CRM.

Everything is **organization-scoped**: one CRM key covers all chatbots in the
org. It is **read-only except** the lead-status write-back.

---

## 2. Auth

Send the CRM key in a header on **every** request:

```
X-CRM-Key: crm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- No login, no token refresh. The key is long-lived until revoked.
- The client (org admin) generates it in the dashboard → **Integrations**, and
  gives it to you. It's shown once; store it as a secret in your CRM.
- Invalid/missing/revoked key → `401 Unauthorized`.

**Base URL** (ask the client for theirs), e.g.:
```
https://api.ambrosianuk.com
```

> Do not hardcode the key in client-side code. Keep it server-side in your CRM.

---

## 3. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/crm/chatbots` | list the org's chatbots |
| GET | `/crm/conversations` | list conversations (paginated, `since`) |
| GET | `/crm/conversations/{id}/messages` | full transcript of one conversation |
| GET | `/crm/leads` | list leads (filter by `status`, `since`, paginated) |
| PATCH | `/crm/leads/{id}` | update a lead's status (`new`/`contacted`) |

### 3.1 GET /crm/chatbots
```json
{ "chatbots": [ { "id": "…", "name": "Support", "model": "llama-3.1-8b-instant" } ], "count": 1 }
```

### 3.2 GET /crm/conversations
Query params:
- `chatbot_id` (optional) — filter to one chatbot
- `since` (optional) — ISO 8601; only conversations active since then
- `limit` (default 50, max 200), `offset` (default 0)

```json
{
  "conversations": [
    {
      "id": "…",
      "chatbot_id": "…",
      "chatbot_name": "Support",
      "session_id": "abc123",
      "mode": "ai",                    // "ai" | "human" (live agent took over)
      "waiting_for_human": false,
      "assigned_agent_name": null,
      "lead_captured": true,
      "message_count": 8,
      "last_message": "Thanks!",
      "last_sender": "visitor",        // visitor | ai | agent | system
      "last_message_at": "2026-06-14T10:31:51+00:00",
      "created_at": "2026-06-14T10:20:00+00:00"
    }
  ],
  "count": 1, "limit": 50, "offset": 0
}
```

### 3.3 GET /crm/conversations/{id}/messages
```json
{
  "conversation": { /* same shape as a conversations[] item */ },
  "messages": [
    { "id": 1, "sender": "visitor", "content": "How much is 6.6kW?", "agent_name": null, "created_at": "…" },
    { "id": 2, "sender": "ai",      "content": "Around $3,300–$3,700 …",   "agent_name": null, "created_at": "…" },
    { "id": 3, "sender": "agent",   "content": "Hi, this is Sam …",        "agent_name": "Sam", "created_at": "…" }
  ]
}
```
`sender` values: `visitor` (end user), `ai` (bot), `agent` (human takeover),
`system` (e.g. "Lead captured", "Agent joined").

### 3.4 GET /crm/leads
Query params: `chatbot_id`, `status` (`new`|`contacted`), `since`, `limit`, `offset`.
```json
{
  "leads": [
    {
      "id": "…",
      "chatbot_id": "…",
      "conversation_id": "…",          // links back to the chat that produced it
      "name": "Jane Doe",
      "phone": "1300089547",
      "email": "jane@example.com",     // may be null
      "status": "new",                 // "new" | "contacted"
      "created_at": "2026-06-14T10:31:51+00:00"
    }
  ],
  "count": 1, "limit": 50, "offset": 0
}
```

### 3.5 PATCH /crm/leads/{id}  (write-back)
Body:
```json
{ "status": "contacted" }
```
Response:
```json
{ "id": "…", "status": "contacted" }
```
Use this when your sales team actions a lead — it updates the status shown in
the client's dashboard too. `status` must be `new` or `contacted`.

---

## 4. Recommended sync strategy

**Incremental polling** (simple + reliable). Store the timestamp of your last
successful pull and pass it as `since`:

1. **New leads** (most important — do this frequently, e.g. every 1–2 min):
   ```
   GET /crm/leads?status=new&since={last_pull}&limit=200
   ```
   Create a CRM record per lead. Then optionally `PATCH` it to `contacted` once
   your team picks it up (or leave the client's team to do it in the dashboard).

2. **Conversations / transcripts** (for context, e.g. every 5–15 min):
   ```
   GET /crm/conversations?since={last_pull}&limit=200
   ```
   For each returned conversation, if you want the full thread:
   ```
   GET /crm/conversations/{id}/messages
   ```

3. Advance `{last_pull}` to the newest `created_at` / `last_message_at` you saw.

**Pagination**: increase `offset` in steps of `limit` until you get fewer than
`limit` items back. Times are ISO 8601 UTC.

**Dedupe**: use the returned `id` fields (lead id, conversation id, message id)
as idempotency keys so re-polling never creates duplicates.

---

## 5. Errors

| Status | Meaning | Action |
|---|---|---|
| 200 | OK | — |
| 400 | bad `since` (not ISO 8601) | fix the timestamp format |
| 401 | missing / invalid / revoked key | check the `X-CRM-Key` header |
| 404 | conversation/lead not found or not in this org | ignore/skip |

All responses are JSON. Errors: `{ "detail": "…" }`.

---

## 6. Minimal example (Python)

```python
import requests

BASE = "https://api.ambrosianuk.com"
KEY = "crm_xxx"                      # store as a secret
H = {"X-CRM-Key": KEY}

# pull new leads since last run
r = requests.get(f"{BASE}/crm/leads", headers=H,
                 params={"status": "new", "since": last_pull_iso, "limit": 200})
for lead in r.json()["leads"]:
    crm_create_contact(lead)         # your CRM logic
    # optional: mark contacted after your team is assigned
    # requests.patch(f"{BASE}/crm/leads/{lead['id']}", headers=H,
    #                json={"status": "contacted"})
```

```bash
# same thing with curl
curl -H "X-CRM-Key: crm_xxx" \
  "https://api.ambrosianuk.com/crm/leads?status=new&since=2026-06-14T00:00:00Z"
```

---

## 7. Webhooks (real-time push) — optional, recommended for leads

Instead of (or alongside) polling `/crm/leads`, we can **POST each new lead to
your endpoint the instant it's captured**. This is the reverse direction of the
API: *we* call *you*.

### Setup (one-time)
1. You build an HTTPS endpoint that accepts `POST` with a JSON body.
2. The client enters that URL in the dashboard → Integrations → Webhook, enables
   it, and gives you the **signing secret** (`whsec_…`).
3. Optionally the client clicks **Send test event** — you should receive a
   `ping`.

### Request we send
- Method: `POST`, `Content-Type: application/json`
- Headers:
  - `X-Webhook-Event: lead.created` (or `ping`)
  - `X-Webhook-Signature: sha256=<hmac>`
- Body:
```json
{
  "event": "lead.created",
  "created_at": "2026-06-15T09:00:00+00:00",
  "data": {
    "id": "…",
    "chatbot_id": "…",
    "conversation_id": "…",
    "name": "Jane Doe",
    "phone": "1300089547",
    "email": "jane@example.com",
    "status": "new"
  }
}
```

### Verify the signature (IMPORTANT — do this before trusting the payload)
The signature is `sha256=` + HMAC-SHA256 of the **raw request body** using the
signing secret. Compare with a constant-time check.

**Python (FastAPI/Flask):**
```python
import hmac, hashlib

def verify(raw_body: bytes, header_sig: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig or "")
```

**Node (Express):**
```js
const crypto = require("crypto");
function verify(rawBody, headerSig, secret) {
  const expected = "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(headerSig || ""));
}
// use express.raw({type: "application/json"}) so you get the exact bytes
```
Reject with `401` if it doesn't match. Never process an unverified payload.

### How you should respond
- Return **HTTP 2xx quickly** (do heavy work async). Any non-2xx or timeout is a
  failure.
- On failure we **retry up to 3 times** (after 0s, 3s, 10s). If all fail, the
  event is dropped — so **also run the polling sync** (§4) as a safety net to
  catch anything missed while your endpoint was down.
- **Idempotency**: dedupe on `data.id` — a retried delivery has the same id.

### Events
- `lead.created` — a visitor submitted the callback form.
- `ping` — sent by the dashboard "Send test event" button.

> Webhooks are for **real-time new leads**. Use the **REST API** for history,
> transcripts, backfill, and recovery — they complement each other.

---

## 8. Notes

- **Scope**: this CRM key can only read data + set lead status. It cannot chat,
  ingest documents, or change chatbot settings. A separate widget key (`sk_…`)
  handles chat — don't use it here (and this key won't work for chat).
- **Security**: HTTPS only; treat the key like a password; the client can revoke
  it instantly from the dashboard (then it returns `401`).
- **Rate**: be reasonable — polling every 1–2 minutes for leads and every
  5–15 minutes for transcripts is plenty. Use `since` to keep payloads small.
- **Timezones**: all timestamps are UTC ISO 8601 (`…+00:00` / `…Z`).

Questions or a field you need that isn't exposed? Ask the platform owner.
