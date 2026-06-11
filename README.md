# for fast vps deploy 
cd ~/chatbot && git pull
docker compose -f docker-compose.vps.yml --env-file .env.prod up -d --build


# Self-hosted Multi-tenant RAG Chatbot (backend)


Self-hosted Retrieval-Augmented-Generation engine that serves **many isolated
chatbots**, each reached by its own API key. Upload docs per chatbot → ask
questions → get streamed answers grounded in *that chatbot's* docs only.

- **API**: FastAPI (async, SSE streaming)
- **LLM**: Ollama, default `qwen2.5:3b` (per-chatbot override; provider swappable)
- **Embeddings**: sentence-transformers `all-MiniLM-L6-v2` (local, free)
- **Vector DB**: Qdrant — every vector tagged with `chatbot_id`, all I/O filtered
- **Relational DB**: PostgreSQL via SQLAlchemy + Alembic (SQLite for local dev)
- **Auth**: per-chatbot API keys, SHA-256 hashed (plaintext never stored)
- **Rate limiting**: per API key (slowapi)

Tuned for a CPU-only VPS (6 vCPU / 12 GB): small context, `top_k=4`, a 3B model.

---

## Tenant model

```
Organization 1───* Chatbot 1───* ApiKey
                      │
                      ├──* Document   (metadata; vectors live in Qdrant)
                      └──* ChatLog    (one row per turn: messages + token usage)
```

**Isolation**: every Qdrant vector carries `chatbot_id`. Ingest, search, and
delete *always* filter on it. An API key resolves to exactly one chatbot, so a
chatbot can never read another's documents or vectors.

```
app/
├── main.py            app + lifespan (DB, Qdrant collection, model warmup, limiter)
├── config.py          .env settings
├── schemas.py         pydantic models
├── db/                base (engine/session) · models (ORM)
├── routers/           admin · ingest · chat · documents
└── services/          auth · ratelimit · crud · extract · chunking
                       · embeddings · vectorstore · llm · rag
alembic/               migrations (0001_init)
```

---

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/admin/orgs` | admin* | create organization |
| POST | `/admin/orgs/{org_id}/chatbots` | admin* | create chatbot (name, system_prompt, tone, welcome_message, model) |
| GET/PATCH | `/admin/chatbots/{id}` | admin* | read / update chatbot config |
| DELETE | `/admin/chatbots/{id}` | admin* | delete chatbot + purge its vectors |
| POST | `/admin/chatbots/{id}/api-keys` | admin* | generate key (**plaintext returned once**) |
| GET | `/admin/chatbots/{id}/api-keys` | admin* | list keys (no secrets) |
| DELETE | `/admin/api-keys/{key_id}` | admin* | revoke key |
| POST | `/ingest` | **API key** | ingest a doc into the key's chatbot |
| POST | `/chat` | **API key** | streamed RAG answer (SSE) |
| GET | `/documents` | **API key** | list this chatbot's docs |
| DELETE | `/documents/{id}` | **API key** | delete a doc + its vectors |
| GET | `/health` | none | liveness |

\* `/admin/*` is open unless `ADMIN_TOKEN` is set, then it requires the
`X-Admin-Token` header. **Set `ADMIN_TOKEN` in production.**

End users send their key in the `X-API-Key` header (configurable).

---

## Quick start with Docker (VPS)

Runs FastAPI + Postgres + Qdrant + Ollama together; migrations run on boot.

```bash
git clone <your-repo> chatbot && cd chatbot
cp .env.example .env            # set ADMIN_TOKEN for prod; rest defaults are fine

docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:3b   # one-time, ~2 GB

curl http://localhost:8000/health
```

The `api` container runs `alembic upgrade head` before starting uvicorn.
Postgres, Qdrant, Ollama models and the embedding cache persist in volumes.

### Full flow with curl

```bash
ADMIN="-H 'X-Admin-Token: <your-admin-token>'"   # omit if ADMIN_TOKEN unset

# 1. Org
ORG=$(curl -s -X POST localhost:8000/admin/orgs \
  -H "Content-Type: application/json" -d '{"name":"My Company"}' | jq -r .id)

# 2. Chatbot
BOT=$(curl -s -X POST localhost:8000/admin/orgs/$ORG/chatbots \
  -H "Content-Type: application/json" \
  -d '{"name":"Support","system_prompt":"You are our support bot.","tone":"friendly"}' \
  | jq -r .id)

# 3. API key (copy the plaintext "api_key" — shown only once)
KEY=$(curl -s -X POST localhost:8000/admin/chatbots/$BOT/api-keys \
  -H "Content-Type: application/json" -d '{"name":"web"}' | jq -r .api_key)

# 4. Ingest a doc INTO this chatbot
curl -F "file=@/path/to/doc.pdf" -H "X-API-Key: $KEY" localhost:8000/ingest

# 5. Chat (streamed SSE). -N disables curl buffering.
curl -N -X POST localhost:8000/chat \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"message":"What is the refund policy?","session_id":"demo"}'

# 6. Manage docs (scoped to this chatbot)
curl -H "X-API-Key: $KEY" localhost:8000/documents
```

---

## Human-agent handoff (live takeover)

Every visitor session is a **Conversation** with a `mode`:

- `ai` (default) — the AI answers via RAG, streamed token-by-token.
- `human` — a live agent has taken over; **the AI is paused** and the agent
  chats directly with the visitor.

All messages (visitor / ai / agent / system) are persisted in the `messages`
table, so history is complete regardless of who answered.

### How takeover works

1. Visitor chats in the widget over `WS /ws/chat/{session_id}` (auth: API key as
   a query param, since browsers can't set WebSocket headers).
2. Agents open **Live Chats** in the dashboard, which connects to
   `WS /ws/agent?token={JWT}`. On connect they get the inbox of their org's
   conversations (with unread + "waiting for human" indicators).
3. Agent clicks **Take over** → `mode=human`, the agent is assigned, the visitor
   sees *"You're now chatting with {agent}"*. While `human`, visitor messages are
   relayed to the agent and the AI does **not** respond.
4. Agent clicks **Hand back to AI** → `mode=ai`, visitor sees *"You're back with
   the AI assistant."* and the AI resumes.
5. Visitor can press **Talk to a human** → flags the conversation `waiting` and
   notifies all of the org's connected agents.

### How an agent joins a live chat

Dashboard → **Live Chats** (sidebar). Pick a conversation from the inbox →
read the full history → **Take over** → type in the reply box. The header shows
*"Handled by {agent}"*; if another agent already took it, the take-over is
rejected (collision guard) so two agents don't reply at once.

### Tenant isolation

The agent socket resolves the org from its JWT and only ever receives/affects
conversations belonging to that org's chatbots. Every agent action re-checks
`chatbot.org_id == org_id`.

### Scaling note (single-server vs. multi-worker)

The connection manager (`app/services/ws_manager.py`) keeps connected sockets in
**process memory** — correct and sufficient for the target single-VPS, single
uvicorn-worker setup. To run multiple workers/servers, the in-process broadcast
must become **Redis pub/sub** (publish on send, each worker subscribes and
fans out to its local sockets). The send/broadcast call sites are the only
integration points; message persistence already lives in Postgres, so no other
changes are needed.

### Relevant endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| WS | `/ws/chat/{session_id}?api_key=` | API key | visitor live chat (AI stream + agent relay) |
| WS | `/ws/agent?token=` | JWT | agent dashboard socket |
| GET | `/conversations` | JWT | inbox: active conversations + indicators |
| GET | `/conversations/{id}/messages` | JWT | full transcript for a conversation |

---

## Frontend dashboard (Vite + React + TypeScript)

A professional SaaS console in `frontend/`: org signup/login (JWT), chatbot
CRUD, per-chatbot config, document upload with live ingestion status, API key
management (generate-once + copy), usage analytics, and a built-in test-chat
panel that streams answers.

```bash
cd frontend
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:5173
```

Build for production:

```bash
npm run build                 # outputs to frontend/dist (static, host anywhere)
npm run preview               # preview the production build locally
```

The backend already enables CORS for `http://localhost:5173` (configurable via
`CORS_ORIGINS` in the backend `.env`). Sign up to create an organization, then
create a chatbot, upload docs, generate a key, and try it in **Test Chat**.

Frontend structure:

```
frontend/src/
├── api/        client.ts (typed fetch + JWT, SSE streaming) · types.ts
├── auth/       AuthContext.tsx (session, login/signup/logout)
├── components/ Layout · Toast · ui.tsx (Button/Card/Modal/Confirm/Field/…)
└── pages/      Login · Signup · Chatbots · chatbot/{Config,Documents,ApiKeys,Usage,TestChat}
```

---

## Backend auth endpoints (JWT)

The dashboard authenticates the **organization** with JWT; chatbots are still
called externally with **API keys**.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | none | create org (name, email, password) → token |
| POST | `/auth/login` | none | email + password → token |
| GET | `/auth/me` | JWT | current org |
| GET/POST | `/chatbots` | JWT | list / create chatbots (org-scoped) |
| GET/PATCH/DELETE | `/chatbots/{id}` | JWT | read / update / delete chatbot |
| GET/POST | `/chatbots/{id}/api-keys` | JWT | list / generate keys |
| DELETE | `/api-keys/{id}` | JWT | revoke key |
| GET/POST | `/chatbots/{id}/documents` | JWT | list / upload (async, status-tracked) |
| DELETE | `/chatbots/{id}/documents/{doc}` | JWT | delete doc + vectors |
| GET | `/chatbots/{id}/usage` | JWT | message counts, token usage, recent convos |
| POST | `/chatbots/{id}/test-chat` | JWT | streamed RAG answer (dashboard panel) |

External per-chatbot API (`/ingest`, `/chat`, `/documents`) is unchanged and
still keyed by `X-API-Key`.

---

## End-to-end test (proves isolation)

Creates an org + two chatbots, ingests a different doc into each, then verifies
chatbot B *cannot* answer from chatbot A's document. Also checks scoped doc
listing and auth (missing/revoked key → 401).

```bash
pip install httpx
python test_e2e.py --base-url http://localhost:8000 [--admin-token <token>]
```

Expected tail: `PASSED: multi-tenant RAG + strict isolation + auth all work.`

---

## Local dev without Docker

Uses **embedded Qdrant** + **SQLite** — no Postgres/Qdrant servers needed.
Only Ollama is required.

```bash
# Ollama (host install) + model
ollama pull qwen2.5:3b

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Point .env at local stores:
#   QDRANT_PATH=data/qdrant
#   DATABASE_URL=sqlite:///data/app.db
# (AUTO_CREATE_TABLES=true builds the schema on startup — no Alembic needed locally)

uvicorn app.main:app --reload --port 8000
python test_e2e.py
```

---

## Migrations (Alembic)

```bash
alembic upgrade head                      # apply (run automatically in Docker)
alembic revision --autogenerate -m "msg"  # after editing app/db/models.py
alembic downgrade -1                       # roll back one
```

`alembic/env.py` reads `DATABASE_URL` from settings, so the same commands work
against SQLite or Postgres.

---

## Configuration reference (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/app.db` | SQLAlchemy URL (Postgres in prod) |
| `AUTO_CREATE_TABLES` | `true` | create tables on startup (dev) |
| `ADMIN_TOKEN` | _empty_ | guards `/admin/*` if set |
| `API_KEY_HEADER` | `X-API-Key` | header chatbots authenticate with |
| `RATE_LIMIT` | `30/minute` | per-API-key rate limit |
| `LLM_PROVIDER` / `LLM_MODEL` | `ollama` / `qwen2.5:3b` | default LLM (per-chatbot override) |
| `LLM_NUM_CTX` | `4096` | context window (small for CPU) |
| `QDRANT_URL` / `QDRANT_PATH` | server / _embedded_ | set PATH for embedded local mode |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `all-MiniLM-L6-v2` / `384` | local embeddings |
| `TOP_K` / `SCORE_THRESHOLD` | `4` / `0.30` | retrieval tuning |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `150` | chunking (chars) |
| `HISTORY_MAX_TURNS` | `6` | recent turns kept in the prompt |

---

## VPS / security notes (Contabo, 6 vCPU / 12 GB, no GPU)

- Expose only port `8000`. Keep `5432` / `6333` / `11434` internal (no auth).
- **Set `ADMIN_TOKEN`** so management endpoints aren't public.
- Put TLS (Caddy/nginx) in front for production.
- `qwen2.5:3b` is CPU-only here — a few tokens/sec. `OLLAMA_KEEP_ALIVE` keeps it
  warm; `OLLAMA_MAX_LOADED_MODELS=1` caps RAM.
- If you change `EMBEDDING_MODEL`, update `EMBEDDING_DIM` and re-ingest (vector
  size is fixed at collection creation).
"# chatbot" 
