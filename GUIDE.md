# RAG Console — Project Guide

A self-hosted, multi-tenant **RAG chatbot platform** with a management
dashboard, an embeddable chat widget, and **live human-agent handoff**.

This guide covers: what each piece does, how a question becomes an answer, how
takeover works, how to start everything, and the database design.

---

## 1. What it is (components)

| Component | Tech | Role |
|---|---|---|
| **Backend** | FastAPI (async, WebSockets) | API, RAG pipeline, auth, real-time messaging |
| **LLM** | Ollama (`qwen2.5:3b`) | generates answers (swappable via config) |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` | turns text into 384-dim vectors (local, free) |
| **Vector DB** | Qdrant | stores document chunk vectors, filtered per chatbot |
| **Relational DB** | PostgreSQL (SQLite for local dev) | orgs, chatbots, keys, docs, conversations, messages |
| **Dashboard** | React + Vite + TypeScript | manage chatbots/docs/keys, view usage, **Live Chats** |
| **Widget** | Vanilla TS core + React wrapper | embeddable chat bubble for any website |

### Two authentication planes
- **Organizations** log into the dashboard with email + password → **JWT**.
- **Chatbots** are called externally (widget, API) with a per-chatbot **API key**
  (`sk_…`), SHA-256 hashed in the DB (plaintext shown only once).

### Tenant isolation (strict)
Every Qdrant vector is tagged with `chatbot_id`; all search/ingest/delete filter
on it. An API key maps to exactly one chatbot; a JWT maps to one org. No chatbot
or org can ever read another's data.

---

## 2. How the chatbot answers a question (RAG flow)

```mermaid
flowchart TD
    A[Visitor asks a question] --> B[Embed query<br/>all-MiniLM-L6-v2]
    B --> C[Search Qdrant<br/>filter: chatbot_id, top_k=4]
    C --> D{Relevant chunks<br/>score >= threshold?}
    D -- No --> E[Graceful fallback:<br/>'not in the documents']
    D -- Yes --> F[Build prompt:<br/>system + tone + context + recent history]
    F --> G[Ollama streams answer<br/>token by token]
    G --> H[Stream to visitor over WebSocket/SSE]
    H --> I[Persist messages + token usage]
```

**Ingestion** (how docs get searchable) runs once per upload:
`extract text (PDF/DOCX/TXT/MD) → chunk with overlap → embed → store in Qdrant`
with `chatbot_id` + `document_id` on every vector. Dashboard uploads run in the
background and show `processing → done | failed`.

---

## 3. How live human-agent handoff works

Each visitor session is a **Conversation** with a `mode`:

- `ai` (default) — the AI answers via RAG.
- `human` — a live agent answers; **the AI is paused**.

```mermaid
sequenceDiagram
    participant V as Visitor (widget)
    participant B as Backend (WS)
    participant A as Agent (dashboard)

    V->>B: message (mode=ai)
    B-->>V: AI streams answer
    B-->>A: inbox updated (unread+1)

    V->>B: "Talk to a human"
    B-->>A: conversation flagged "waiting"

    A->>B: take_over
    B-->>V: "You're now chatting with {agent}"
    Note over B: mode = human (AI paused)

    V->>B: message
    B-->>A: relayed (AI does NOT respond)
    A->>B: reply
    B-->>V: agent_message

    A->>B: release
    B-->>V: "You're back with the AI assistant"
    Note over B: mode = ai (AI resumes)
```

- Real-time transport: visitors use `WS /ws/chat/{session_id}` (auth: API key in
  query), agents use `WS /ws/agent` (auth: JWT in query).
- A **connection manager** (`app/services/ws_manager.py`) tracks sockets and
  broadcasts between a visitor and the agents of its org.
- **Collision guard**: if one agent already took a chat, another's take-over is
  rejected so two agents never reply at once.
- **Everything is persisted** to the `messages` table (visitor / ai / agent /
  system) so history is complete regardless of who answered.

> **Scaling note:** the connection manager holds sockets in process memory —
> correct for a single VPS / single uvicorn worker. For multiple workers, swap
> the in-process broadcast for **Redis pub/sub** (only the send/broadcast call
> sites change; persistence already lives in Postgres).

---

## 4. Database diagram

Relational schema (Postgres / SQLite). Vectors live separately in Qdrant.

```mermaid
erDiagram
    organizations ||--o{ chatbots : owns
    chatbots      ||--o{ api_keys : has
    chatbots      ||--o{ documents : has
    chatbots      ||--o{ chat_logs : logs
    chatbots      ||--o{ conversations : has
    conversations ||--o{ messages : contains

    organizations {
        string   id PK
        string   name
        string   email "unique (login)"
        string   password_hash "bcrypt"
        datetime created_at
    }
    chatbots {
        string   id PK
        string   org_id FK
        string   name
        text     system_prompt
        string   tone
        text     welcome_message
        string   model "e.g. qwen2.5:3b"
        datetime created_at
    }
    api_keys {
        string   id PK
        string   chatbot_id FK
        string   name
        string   prefix "sk_ab12cd34"
        string   key_hash "sha256, unique"
        bool     revoked
        datetime created_at
        datetime last_used_at
    }
    documents {
        string   id PK
        string   chatbot_id FK
        string   filename
        int      chunk_count
        string   status "processing|done|failed"
        text     error
        datetime created_at
    }
    chat_logs {
        int      id PK
        string   chatbot_id FK
        string   session_id
        text     user_message
        text     assistant_message
        int      message_count
        int      prompt_tokens
        int      completion_tokens
        int      total_tokens
        datetime created_at
    }
    conversations {
        string   id PK
        string   chatbot_id FK
        string   session_id "unique with chatbot_id"
        string   mode "ai|human"
        bool     waiting_for_human
        string   assigned_agent_id
        string   assigned_agent_name
        int      unread
        datetime created_at
        datetime last_message_at
    }
    messages {
        int      id PK
        string   conversation_id FK
        string   sender "visitor|ai|agent|system"
        text     content
        string   agent_id
        string   agent_name
        datetime created_at
    }
```

**Outside Postgres — Qdrant collection `documents`:** one point per chunk,
`vector` (384-dim) + payload `{ chatbot_id, document_id, filename, chunk_index,
text }`. `chatbot_id` and `document_id` are indexed for fast tenant-scoped
filtering and deletes.

**Two history stores, on purpose:** `chat_logs` is turn-based analytics (token
usage, counts); `conversations`/`messages` is the full per-message transcript
(source of truth for the dashboard and handoff).

---

## 5. How to start the project

### Prerequisites (one time)
- **Python 3.11+**, **Node 18+**
- **Ollama** installed + model pulled:
  ```bash
  ollama pull qwen2.5:3b
  ```
- Python deps: `pip install -r requirements.txt`
- (Optional, for a public URL) **cloudflared**:
  `winget install Cloudflare.cloudflared`

### Start everything with one command

**Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

**Linux / macOS:**
```bash
chmod +x start-all.sh && ./start-all.sh
```

This launches, each in its own window/process:

| Service | URL |
|---|---|
| Backend (API + `/docs`) | http://127.0.0.1:8000 |
| Dashboard | http://localhost:5173 |
| Widget demo | http://localhost:3000/demo/embed.html |
| Public tunnel | `https://<random>.trycloudflare.com` (printed on start) |

Flags: `-NoTunnel` (skip public URL), `-NoFrontend` (backend + widget only).
Bash: `NO_TUNNEL=1 ./start-all.sh`.

**Stop everything (Windows):**
```powershell
.\stop-all.ps1
```

### First run
1. Open the dashboard → **Sign up** (creates your org).
2. **New chatbot** → set name / system prompt / tone.
3. **Documents** → upload a PDF/DOCX/TXT/MD (wait for `done`).
4. **API Keys** → Generate → copy the key and the **embed snippet**.
5. **Test Chat** → ask something from your docs.
6. **Live Chats** → take over a conversation to chat as a human.

### Add the widget to another site
Paste the embed snippet (from API Keys) into any site:
```html
<script
  src="https://<your-backend-or-tunnel>/widget.js"
  data-api-url="https://<your-backend-or-tunnel>"
  data-api-key="sk_..."
  data-chatbot-id="..."
  data-title="Support"
  data-position="bottom-right"></script>
```
The backend serves `widget.js` itself, so no file copying is needed. For local
testing against other sites, use the cloudflared URL from `start-all`.

---

## 6. Project layout

```
chatbot/
├── app/                 FastAPI backend
│   ├── routers/         auth · manage · conversations · ws · ingest · chat · documents
│   ├── services/        rag · embeddings · vectorstore · llm · ingestion
│   │                    · auth · security · crud · ratelimit · ws_manager
│   └── db/              base (engine/session) · models (ORM)
├── alembic/             migrations (0001..0003)
├── frontend/            React dashboard (Vite + TS)
├── widget/              embeddable chat widget (npm lib + script embed)
├── docker-compose.yml   Postgres + Qdrant + Ollama + API (for the VPS)
├── start-all.ps1 / .sh  one-command local launcher
├── test_e2e.py          multi-tenant + isolation test
└── test_handoff.py      live human-agent handoff test
```

For production deployment (Docker on a VPS), see **README.md**.
