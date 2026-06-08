# Deploy to a VPS (Contabo) — Turnkey Docker

Brings up the full stack behind **automatic HTTPS**:

```
                         ┌── https://app.yourdomain.com ──> web (nginx, React dashboard)
internet ──> Caddy(TLS) ─┤
   80/443                └── https://api.yourdomain.com ──> api (FastAPI) ──> Postgres
                                                                          ├─> Qdrant
                                                                          └─> Ollama
```

Only Caddy is exposed (80/443). Postgres, Qdrant, Ollama, API, and the frontend
are all internal to the Docker network.

---

## 0. Prerequisites

- A domain you control.
- The repo pushed to GitHub (done): `https://github.com/aaabir2a/chatbot.git`
- Contabo VPS (6 vCPU / 12 GB / no GPU is fine).

---

## 1. DNS — point two subdomains at the VPS

In your domain's DNS, add two **A records** to your VPS's public IP:

| Type | Name | Value |
|---|---|---|
| A | `api` | `YOUR.VPS.IP` |
| A | `app` | `YOUR.VPS.IP` |

(Result: `api.yourdomain.com` and `app.yourdomain.com`.) DNS can take a few
minutes to propagate. Verify: `ping api.yourdomain.com` returns your VPS IP.

---

## 2. SSH in and install Docker

```bash
ssh deploy@YOUR.VPS.IP

# Install Docker Engine + compose plugin (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker     # apply group now without re-login
docker --version && docker compose version
```

---

## 3. Open the firewall (ports 80 + 443)

```bash
# If ufw is active:
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow OpenSSH
sudo ufw status
```

> If another app (your existing `ambrosian`) already uses port 80/443, Caddy
> can't bind them. Free those ports first, or run this stack on a second IP.

---

## 4. Clone the project

```bash
cd ~
git clone https://github.com/aaabir2a/chatbot.git
cd chatbot
```

---

## 5. Configure secrets

```bash
cp .env.prod.example .env.prod

# Generate two strong secrets:
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo "ADMIN_TOKEN=$(openssl rand -hex 32)"

nano .env.prod
```

Fill in `.env.prod`:
- `API_DOMAIN=api.yourdomain.com`
- `APP_DOMAIN=app.yourdomain.com`
- `ACME_EMAIL=you@yourdomain.com`
- `POSTGRES_PASSWORD=` a strong password
- `JWT_SECRET=` / `ADMIN_TOKEN=` the values you generated above

Save (Ctrl-O, Enter, Ctrl-X).

---

## 6. Build and start everything

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

First build takes a few minutes (installs deps, pre-downloads the embedding
model, builds the widget + frontend). Watch progress:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Caddy fetches Let's Encrypt certs automatically once DNS resolves to the VPS.

---

## 7. Pull the LLM model (one time, ~2 GB)

```bash
docker compose -f docker-compose.prod.yml exec ollama ollama pull qwen2.5:3b
```

---

## 8. Verify

```bash
curl https://api.yourdomain.com/health
# {"status":"ok","provider":"ollama","default_model":"qwen2.5:3b"}
```

Open **https://app.yourdomain.com** → Sign up → create a chatbot → upload a doc
→ generate an API key → copy the embed snippet.

The embed snippet now points at your live backend:

```html
<script
  src="https://api.yourdomain.com/widget.js"
  data-api-url="https://api.yourdomain.com"
  data-api-key="sk_..."
  data-chatbot-id="..."
  data-title="Support"
  data-position="bottom-right"></script>
```

Paste it into any site (including your Vercel React app). HTTPS + `wss` work, so
the widget loads on https sites and live agent handoff streams in real time.

---

## Day-2 operations

**Update after pushing new code:**
```bash
cd ~/chatbot
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

**Logs / status:**
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

**Stop / start:**
```bash
docker compose -f docker-compose.prod.yml down        # stop (keeps data volumes)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

**Backup the database:**
```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U rag rag > backup_$(date +%F).sql
```

**Data persists** in named volumes (`postgres_data`, `qdrant_data`,
`ollama_data`, `model_cache`). `down` keeps them; `down -v` deletes them.

---

## Notes / gotchas

- **CPU inference**: `qwen2.5:3b` runs on CPU — expect a few tokens/sec. Keep
  `top_k` small (default 4). Fine for a 12 GB box.
- **Secrets**: `.env.prod` is gitignored — keep it only on the server.
- **Rotate** `ADMIN_TOKEN` / `JWT_SECRET` if ever exposed (changing `JWT_SECRET`
  logs everyone out).
- **CORS** is auto-set to `https://app.yourdomain.com`. If you serve the
  dashboard elsewhere too, add origins via the `CORS_ORIGINS` env (comma list).
- **More RAM headroom**: only one Ollama model loads at a time
  (`OLLAMA_MAX_LOADED_MODELS=1`).
