# Project Report — Self-Hosted Multi-Tenant RAG Chatbot Platform

_Generated 2026-08-12 · repo `D:\Kratos-office\chatbot` · branch `main` (clean) · 32 commits, last 2026-07-30 · ~8.3k LOC of app/frontend/widget source_

## 1. What it is

A self-hostable SaaS-style chatbot platform. One deployment serves many isolated
chatbots, each with its own documents, API keys, branding and LLM config. End
users chat through an embeddable widget; the answers are grounded (RAG) only in
that chatbot's own documents. Human agents can take over any live conversation,
and an external CRM can read and act on the same data.

## 2. Stack

| Layer | Choice |
|---|---|
| API | FastAPI — async, SSE streaming, WebSockets |
| LLM | Provider abstraction in `app/services/llm.py`: Ollama (local) or any OpenAI-compatible host (Groq / Gemini / OpenAI / DeepSeek) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2`, local, free |
| Vector DB | Qdrant — every vector tagged with `chatbot_id`; ingest/search/delete always filter on it |
| Relational DB | PostgreSQL + SQLAlchemy + Alembic (SQLite for local dev) |
| Dashboard | React + Vite + TypeScript (`frontend/`) |
| Widget | Vanilla TS, Shadow DOM, WebSocket, markdown rendering (`widget/`) |
| Auth | Org JWT for the dashboard; SHA-256-hashed per-chatbot API keys; separate CRM keys; optional `ADMIN_TOKEN` |
| Ops | Docker Compose (dev / prod / vps variants), Caddy, migrations run on boot |

Tuned for a CPU-only VPS (6 vCPU / 12 GB): small context window, `top_k=4`, 3B model by default.

## 3. Data model (`app/db/models.py`)

```
Organization ─┬─* Chatbot ─┬─* ApiKey
              │            ├─* Document      (metadata; vectors live in Qdrant)
              │            ├─* ChatLog       (one row per turn + token usage)
              │            ├─* Conversation ─* Message
              │            └─* Lead
              └─* CrmKey
```

Isolation guarantee: an API key resolves to exactly one chatbot, and every
Qdrant operation is filtered by `chatbot_id`, so no cross-tenant read is possible.

## 4. Surface area

**42 HTTP routes + 2 WebSocket endpoints**, grouped as:

- `auth` — signup / login / me (JWT)
- `manage` — chatbots CRUD, API keys, documents, usage stats, CRM keys, webhook config + test, leads, test-chat
- `chat` — `POST /chat` (SSE streamed RAG), `GET /widget-config` (CORS-open, widget branding + suggested questions)
- `ingest` / `documents` — per-key document upload, list, delete (+ vector purge)
- `conversations` — history for the dashboard
- `crm` — read API for chatbots/conversations/messages/leads, lead status write-back, and live-agent takeover / reply / release
- `ws` — `WS /ws/chat/{session_id}` (end user), `WS /ws/agent` (dashboard agent)

## 5. Features shipped (migrations 0001–0009)

- Org signup + JWT auth; multi-chatbot management dashboard
- Document ingest → chunking → embedding → Qdrant, with per-doc status
- RAG chat over SSE **and** WebSocket
- Multi-turn memory with contextualized retrieval
- Greeting / small-talk shortcut (skips retrieval)
- Human live handoff: agent WS + Live Chats dashboard page
- Lead capture (name + phone + email), re-prompt on skip, triggered by sales intent or by a no-answer
- Per-chatbot `sales_phone` shown alongside the lead form
- Embeddable widget: Shadow DOM isolation, markdown rendering, clickable suggested-question chips (dashboard-managed, rendered top-center)
- CRM integration: read API via `X-CRM-Key`, lead status write-back, HMAC-signed outbound webhooks (`lead.created`, `message.created`, `conversation.human_requested`), and live-agent endpoints

## 6. Docs and tests

Docs: `README.md`, `GUIDE.md`, `DEPLOY.md`, `deploy/LIVE.md`, `CRM_API.md`, `CRM_DEVELOPER_GUIDE.md`.

Tests (script-style, run against a live instance): `test_e2e`, `test_handoff`,
`test_lead`, `test_sales_intent`, `test_memory`, `test_crm`, `test_crm_live`,
`test_webhook`, `test_gemini`.

## 7. Deployment

Live on a VPS. Redeploy is:

```bash
cd ~/chatbot && git pull
docker compose -f docker-compose.vps.yml --env-file .env.prod up -d --build
```

The `api` container runs `alembic upgrade head` before uvicorn. Postgres, Qdrant,
Ollama models and the embedding cache all persist in named volumes.

## 8. Open items

- **CRM WebSocket** — `WS /crm/ws?crm_key=...` so an external CRM gets live push
  of the same events the dashboard agent socket receives, replacing manual
  "Sync now" polling. Proposed but not yet built; current interim advice is to
  poll `/crm/leads?since=` and `/crm/conversations?since=` every ~5s.
- No automated test runner — the `test_*.py` files are manual scripts against a
  running instance rather than a `pytest` suite wired into CI.
- Widget ships a committed `widget/dist/` build; that build must be regenerated
  by hand whenever `widget/src/` changes.

## 9. Assessment

The platform is feature-complete for its stated scope: multi-tenant RAG, live
handoff, lead capture and CRM integration all exist end to end, with tenant
isolation enforced at the vector layer rather than only at the application
layer. The main gaps are operational rather than functional — CI-runnable tests,
an automated widget build step, and the outstanding CRM push channel.
