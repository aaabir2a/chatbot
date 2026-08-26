# Session Handoff — Kratos Chatbot Platform

Paste-ready context for a fresh Claude Code session. Last updated 2026-08-26.

---

## 1. What this project is

Self-hosted **multi-tenant RAG chatbot SaaS**. One deployment runs many isolated
chatbots; each answers only from its own uploaded documents, captures leads, and
can be taken over by a human agent. Repo: https://github.com/aaabir2a/chatbot,
branch `main` = source of truth.

Local path: `D:\Kratos-office\chatbot` (Windows, PowerShell primary shell).

## 2. Stack

| Layer | Choice |
|---|---|
| API | FastAPI — async, SSE streaming, WebSockets |
| LLM | Provider abstraction in `app/services/llm.py`: Ollama (local) **or** OpenAI-compatible host (Groq / Gemini / OpenAI / DeepSeek). Model chosen **per chatbot in the dashboard**, not via env. |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2`, local |
| Vector DB | Qdrant — every vector tagged `chatbot_id`; ingest/search/delete always filter on it |
| Relational DB | PostgreSQL + SQLAlchemy + Alembic (SQLite for local dev). Local postgres port remapped to **5433**. |
| Dashboard | React + Vite + TypeScript in `frontend/` |
| Widget | Vanilla TS, Shadow DOM, WebSocket, markdown render, in `widget/` |
| Auth | Org JWT (dashboard) · SHA-256-hashed per-chatbot API keys (`X-API-Key`) · separate CRM keys (`X-CRM-Key`) · optional `ADMIN_TOKEN` |
| Ops | Docker Compose — `docker-compose.yml` (dev), `.prod.yml`, `.vps.yml`; Caddy or host-nginx variants |

Tuned for a CPU-only VPS (6 vCPU / 12 GB): small context, `top_k=4`, 3B model default.

## 3. Layout

```
app/
├── main.py            app + lifespan (DB, Qdrant collection, model warmup, limiter)
├── config.py          .env settings
├── schemas.py         pydantic models
├── db/                base (engine/session) · models (ORM)
├── routers/           auth · manage · chat · ingest · documents · conversations · crm · ws
└── services/          auth · ratelimit · crud · extract · chunking · ingestion
                       · embeddings · vectorstore · llm · rag · webhooks · ws_manager · security
alembic/versions/      0001_init … 0009_suggested_questions
frontend/src/          pages/ (Chatbots, Leads, LiveChats, Integrations, Login, Signup)
                       pages/chatbot/ (Config, Documents, ApiKeys, TestChat, Usage)
widget/src/            core · embed · stream · ws · md · styles · react · types
```

**Data model** (`app/db/models.py`):

```
Organization ─┬─* Chatbot ─┬─* ApiKey
              │            ├─* Document      (metadata; vectors live in Qdrant)
              │            ├─* ChatLog       (one row per turn + token usage)
              │            ├─* Conversation ─* Message
              │            └─* Lead
              └─* CrmKey
```

**Isolation guarantee:** an API key resolves to exactly one chatbot, and every
Qdrant operation is filtered by `chatbot_id`. No cross-tenant read is possible.

## 4. Surface area — 42 HTTP routes + 2 WebSockets

- `auth` — `/signup`, `/login`, `/me` (JWT)
- `manage` — chatbots CRUD, API keys, documents, usage, CRM keys, webhook config + rotate-secret + test, leads, test-chat
- `chat` — `POST /chat` (SSE streamed RAG), `GET /widget-config` (CORS-open; widget branding + suggested questions)
- `ingest` / `documents` — per-key upload, list, delete (+ vector purge)
- `conversations` — history for the dashboard
- `crm` — read chatbots/conversations/messages/leads · `PATCH /leads/{id}` write-back · live-agent `takeover` / `messages` / `release`
- `ws` — `WS /ws/chat/{session_id}` (end user) · `WS /ws/agent` (dashboard agent)

## 5. Features shipped (migrations 0001–0009)

Org signup + JWT · multi-chatbot dashboard · doc ingest → chunk → embed → Qdrant with
per-doc status · RAG chat over SSE **and** WebSocket · multi-turn memory with
contextualized retrieval (`HISTORY_MAX_TURNS` tunable) · greeting/small-talk shortcut ·
human live handoff (agent WS + Live Chats page with dates/timestamps) · lead capture
(name+phone+email) with re-prompt after N messages on skip · sales-intent + no-answer
triggers showing phone + form · per-chatbot `sales_phone` · widget markdown rendering ·
dashboard-managed suggested-question chips (top-center) · CRM read API, lead write-back,
HMAC-signed outbound webhooks (`lead.created`, `message.created`,
`conversation.human_requested`), CRM live-agent endpoints · `<think>` block stripping for
hosted models.

## 6. Deploy

Live on a VPS. Redeploy:

```bash
cd ~/chatbot && git pull
docker compose -f docker-compose.vps.yml --env-file .env.prod up -d --build
```

The `api` container runs `alembic upgrade head` before uvicorn. Postgres, Qdrant, Ollama
models and the embedding cache persist in named volumes. Production env lives in
`.env.prod` on the VPS (not in the repo — see `.env.prod.example`).

**Gotchas**
- Local Ollama is broken on this machine; use a hosted provider when testing locally.
- `git push` writes progress to stderr — a non-empty stderr does not mean failure.
- **Set `ADMIN_TOKEN` in production** — `/admin/*` is open without it.

## 7. Open items

1. **CRM WebSocket** — `WS /crm/ws?crm_key=...` so an external CRM gets live push of the
   same events the dashboard agent socket receives. Designed, not built. Current interim:
   poll `/crm/leads?since=` + `/crm/conversations?since=` every ~5s. **User has integrated
   the CRM and wants dashboard-like live updates — this is the top priority.**
2. **No CI test runner.** `test_e2e / handoff / lead / sales_intent / memory / crm /
   crm_live / webhook / gemini .py` are manual scripts run against a live instance, not a
   pytest suite.
3. **Widget `dist/` is committed** and must be rebuilt by hand whenever `widget/src/` changes.
4. Bangla replies — started 10 June, reverted same day, on hold.

## 8. Docs already in the repo

`README.md` (full API + curl walkthrough) · `GUIDE.md` · `DEPLOY.md` · `deploy/LIVE.md` ·
`CRM_API.md` · `CRM_DEVELOPER_GUIDE.md` · `PROJECT_REPORT.md` (technical summary) ·
`BUSINESS_REPORT.md` (non-technical, for the business owner).

Published business report artifact:
https://claude.ai/code/artifact/70bcb9ae-b7f0-4586-9e30-64d6adef56c8
(private; update by passing that URL as `url` when republishing)

## 9. Working preferences

- Caveman mode is on in these sessions — terse replies, full technical accuracy. Code,
  commits and security notes are written normally.
- Conventional Commits, subject ≤50 chars.
- Timeline: first commit 8 June 2026, latest 30 July 2026, 32 commits, ~8.3k LOC.
