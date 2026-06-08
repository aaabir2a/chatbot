# Live deployment record — ambrosianuk.com

Snapshot of the production setup so it can be reproduced or maintained.
**Secrets are NOT here** — they live only in `~/chatbot/.env.prod` on the VPS
(gitignored). Treat this file as documentation, not config.

## Host
- Contabo VPS, IP `75.119.149.137`, Ubuntu, 6 vCPU / 12 GB, no GPU
- Docker + compose plugin installed
- **Host nginx** already serves other sites (ambrosianuk.com, banglafest.co.uk…)
  on 80/443 and manages TLS via certbot. The chatbot runs **behind** it.

## Domains
| Subdomain | Serves | Container (localhost) |
|---|---|---|
| `api.ambrosianuk.com` | FastAPI backend + `/widget.js` + WebSockets | `127.0.0.1:8001` |
| `chat.ambrosianuk.com` | React dashboard (static) | `127.0.0.1:8081` |

Both are A records → `75.119.149.137`.

## Stack
- Compose file: **`docker-compose.vps.yml`** (no Caddy; binds to localhost)
- Env file: `~/chatbot/.env.prod` (server-only; from `.env.prod.example`)
- Containers: postgres · qdrant · ollama · api · web
- Model: `qwen2.5:3b` (pulled into the `ollama` volume)
- Reverse proxy: host nginx site `/etc/nginx/sites-available/chatbot`
  (from `deploy/nginx-chatbot.conf`, domains substituted)
- TLS: `certbot --nginx -d api.ambrosianuk.com -d chat.ambrosianuk.com`

## How it was deployed (summary)
```bash
cd ~/chatbot && git pull
# create .env.prod with generated secrets (API_DOMAIN, APP_DOMAIN, secrets…)
docker compose -f docker-compose.vps.yml --env-file .env.prod up -d --build
sudo cp deploy/nginx-chatbot.conf /etc/nginx/sites-available/chatbot
sudo sed -i 's/__API_DOMAIN__/api.ambrosianuk.com/; s/__APP_DOMAIN__/chat.ambrosianuk.com/' /etc/nginx/sites-available/chatbot
sudo ln -sf /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.ambrosianuk.com -d chat.ambrosianuk.com
docker compose -f docker-compose.vps.yml exec ollama ollama pull qwen2.5:3b
```

## Update after pushing new code
```bash
cd ~/chatbot && git pull
docker compose -f docker-compose.vps.yml --env-file .env.prod up -d --build
```

## Embed snippet for other sites
```html
<script
  src="https://api.ambrosianuk.com/widget.js"
  data-api-url="https://api.ambrosianuk.com"
  data-api-key="sk_..."          <!-- from dashboard > chatbot > API Keys -->
  data-chatbot-id="..."
  data-title="Support"
  data-position="bottom-right"></script>
```

## Local dev is unaffected
Local still uses `.env` (SQLite + embedded Qdrant + localhost) and
`frontend/.env` (`VITE_API_URL=http://localhost:8000`). Run with `start-all.ps1`.
The live values above are recorded only as commented references in
`.env.example`, `.env.prod.example`, and `frontend/.env.example`.
