# CRM Integration API

Pull chatbot **conversations, transcripts, and leads** into any external CRM
using a single API key — **no login required**.

- **Auth**: header `X-CRM-Key: crm_...` (generate in the dashboard → Integrations).
- **Scope**: a CRM key is **org-wide** and **read-only** — it sees every chatbot
  in your organization, but cannot chat, ingest, or change anything.
- **Multiple keys**: generate one per CRM/integration; revoke any independently.
- Base URL = your backend, e.g. `https://api.ambrosianuk.com`.

## Get a key
Dashboard → **Integrations** → **Generate CRM key** → copy it (shown once).

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/crm/chatbots` | your chatbots `[{id,name,model}]` |
| GET | `/crm/conversations` | conversations (paginated) |
| GET | `/crm/conversations/{id}/messages` | full transcript |
| GET | `/crm/leads` | leads from the callback form |

### Query params
- `/crm/conversations`: `chatbot_id`, `since` (ISO 8601), `limit` (1–200, default 50), `offset`
- `/crm/leads`: `chatbot_id`, `status` (`new`|`contacted`), `since`, `limit`, `offset`

`since` enables incremental sync — poll with the timestamp of your last pull.

## Examples

```bash
KEY="crm_your_key"
BASE="https://api.ambrosianuk.com"

# New leads only
curl -H "X-CRM-Key: $KEY" "$BASE/crm/leads?status=new"

# Conversations updated since a timestamp (incremental sync)
curl -H "X-CRM-Key: $KEY" "$BASE/crm/conversations?since=2026-06-14T00:00:00Z&limit=100"

# Full transcript of one conversation
curl -H "X-CRM-Key: $KEY" "$BASE/crm/conversations/<id>/messages"
```

### Sample lead response
```json
{
  "leads": [
    {
      "id": "…", "chatbot_id": "…", "conversation_id": "…",
      "name": "Jane Doe", "phone": "1300089547", "email": "jane@x.com",
      "status": "new", "created_at": "2026-06-14T10:31:51+00:00"
    }
  ],
  "count": 1, "limit": 50, "offset": 0
}
```

### Message senders
Transcript messages have `sender` ∈ `visitor` | `ai` | `agent` | `system`.

## Security
- The key is SHA-256 hashed in the DB (plaintext shown once).
- Revoke instantly from the dashboard — the key returns `401` immediately after.
- A chatbot widget key (`sk_…`) can **not** access `/crm` (returns `401`), and a
  CRM key can **not** chat/ingest — the two scopes are separate.
- Serve over HTTPS only; treat the CRM key like a password.
