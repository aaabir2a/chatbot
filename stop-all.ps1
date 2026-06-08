<#
  stop-all.ps1 — stop everything started by start-all.ps1.
  Kills the backend (uvicorn/python), dashboard + widget server (node/python http),
  and the cloudflared tunnel. Leaves Ollama running (it's a system service).
#>
Write-Host "Stopping RAG Console stack..." -ForegroundColor Yellow

# cloudflared tunnel
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Node (Vite dev server)
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Python (uvicorn backend + http.server widget demo)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Stopped. (Ollama left running.)" -ForegroundColor Green
Write-Host "Tip: close the leftover PowerShell windows if any remain." -ForegroundColor DarkGray
