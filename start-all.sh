#!/usr/bin/env bash
# start-all.sh — launch the whole stack locally (Linux/macOS).
#   Backend (8000) + Dashboard (5173) + Widget demo (3000) + cloudflared tunnel.
#   Ctrl-C stops everything.
#
# Usage: ./start-all.sh           (with tunnel)
#        NO_TUNNEL=1 ./start-all.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

pids=()
cleanup() { echo; echo "Stopping..."; kill "${pids[@]}" 2>/dev/null || true; exit 0; }
trap cleanup INT TERM

# Ollama check
curl -s http://localhost:11434/api/tags >/dev/null 2>&1 || \
  echo "WARNING: Ollama not running. Start it and 'ollama pull qwen2.5:3b'."

# Deps / widget build
[ -d frontend/node_modules ] || (cd frontend && npm install)
if [ ! -f widget/dist/widget.js ]; then
  [ -d widget/node_modules ] || (cd widget && npm install)
  (cd widget && npm run build)
fi

echo "[backend]  http://127.0.0.1:8000"
( python -m alembic upgrade head && \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ) & pids+=($!)

echo "[frontend] http://localhost:5173"
( cd frontend && npm run dev ) & pids+=($!)

echo "[widget]   http://localhost:3000/demo/embed.html"
( python -m http.server 3000 --directory widget ) & pids+=($!)

if [ "${NO_TUNNEL:-0}" != "1" ] && command -v cloudflared >/dev/null 2>&1; then
  echo "[tunnel]   starting cloudflared..."
  ( cloudflared tunnel --url http://localhost:8000 ) & pids+=($!)
fi

echo; echo "Stack running. Ctrl-C to stop."
wait
