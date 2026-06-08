<#
  start-all.ps1 - launch the whole stack locally in one go.

  Starts (each in its own window):
    1. Backend   - FastAPI on http://127.0.0.1:8000 (runs migrations first)
    2. Frontend  - dashboard (Vite) on http://localhost:5173
    3. Widget    - static demo server on http://localhost:3000
    4. Tunnel    - cloudflared public URL -> backend (so other sites can connect)

  Usage:
    powershell -ExecutionPolicy Bypass -File .\start-all.ps1
    .\start-all.ps1 -NoTunnel      # skip the public tunnel
    .\start-all.ps1 -NoFrontend    # backend + widget + tunnel only

  Stop everything with: .\stop-all.ps1
#>
param(
  [switch]$NoTunnel,
  [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Write-Host "RAG Console - starting stack from $root`n" -ForegroundColor Cyan

# Resolve external tools -------------------------------------------------------
function Find-Exe([string[]]$names, [string[]]$paths) {
  foreach ($n in $names) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
  }
  foreach ($p in $paths) { if (Test-Path $p) { return $p } }
  return $null
}

$ollama = Find-Exe @("ollama") @("$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")
$cf = Find-Exe @("cloudflared") @(
  "C:\Program Files (x86)\cloudflared\cloudflared.exe",
  "C:\Program Files\cloudflared\cloudflared.exe",
  "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe"
)

# Pre-flight: Ollama -----------------------------------------------------------
Write-Host "[1/5] Checking Ollama..." -ForegroundColor Yellow
try {
  $null = Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 3
  Write-Host "      Ollama is running." -ForegroundColor Green
} catch {
  if ($ollama) {
    Write-Host "      Ollama not responding - launching it." -ForegroundColor DarkYellow
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
  } else {
    Write-Host "      WARNING: Ollama not found. Install it and run 'ollama pull qwen2.5:3b'." -ForegroundColor Red
  }
}

# Pre-flight: deps + widget build ----------------------------------------------
Write-Host "[2/5] Checking dependencies..." -ForegroundColor Yellow
if (-not $NoFrontend -and -not (Test-Path "$root\frontend\node_modules")) {
  Write-Host "      Installing frontend deps..." -ForegroundColor DarkYellow
  Push-Location "$root\frontend"; npm install | Out-Null; Pop-Location
}
if (-not (Test-Path "$root\widget\dist\widget.js")) {
  Write-Host "      Building widget..." -ForegroundColor DarkYellow
  if (-not (Test-Path "$root\widget\node_modules")) {
    Push-Location "$root\widget"; npm install | Out-Null; Pop-Location
  }
  Push-Location "$root\widget"; npm run build | Out-Null; Pop-Location
}

# Backend ----------------------------------------------------------------------
Write-Host "[3/5] Starting backend (http://127.0.0.1:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root'; Write-Host 'BACKEND' -ForegroundColor Cyan; python -m alembic upgrade head; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

# Frontend ---------------------------------------------------------------------
if (-not $NoFrontend) {
  Write-Host "[4/5] Starting dashboard (http://localhost:5173)..." -ForegroundColor Yellow
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\frontend'; Write-Host 'FRONTEND' -ForegroundColor Cyan; npm run dev"
  )
} else {
  Write-Host "[4/5] Skipping frontend (-NoFrontend)." -ForegroundColor DarkGray
}

# Widget demo server -----------------------------------------------------------
Write-Host "[5/5] Starting widget demo (http://localhost:3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root'; Write-Host 'WIDGET DEMO' -ForegroundColor Cyan; python -m http.server 3000 --directory widget"
)

# Cloudflare tunnel ------------------------------------------------------------
$publicUrl = $null
if (-not $NoTunnel) {
  if ($cf) {
    Write-Host "`nStarting cloudflared tunnel..." -ForegroundColor Yellow
    $log = Join-Path $env:TEMP "rag-cf-tunnel.log"
    Remove-Item $log -ErrorAction SilentlyContinue
    Start-Process -FilePath $cf -ArgumentList @("tunnel", "--url", "http://localhost:8000") -RedirectStandardError $log -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
      Start-Sleep -Seconds 1
      if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m) { $publicUrl = $m.Matches[0].Value; break }
      }
    }
  } else {
    Write-Host "`nWARNING: cloudflared not found - skipping tunnel." -ForegroundColor Red
    Write-Host "Install: winget install Cloudflare.cloudflared" -ForegroundColor DarkGray
  }
}

# Summary ----------------------------------------------------------------------
Start-Sleep -Seconds 2
Write-Host "`n========================================================" -ForegroundColor Green
Write-Host " RAG Console is starting up" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host " Backend  : http://127.0.0.1:8000  (/docs for API)"
if (-not $NoFrontend) { Write-Host " Dashboard: http://localhost:5173" }
Write-Host " Widget   : http://localhost:3000/demo/embed.html"
if ($publicUrl) {
  Write-Host " Public   : $publicUrl" -ForegroundColor Cyan
  Write-Host "            ^ use this as data-api-url / src in the embed snippet"
} elseif (-not $NoTunnel) {
  Write-Host " Public   : (tunnel starting - check the cloudflared output)" -ForegroundColor DarkYellow
}
Write-Host "========================================================" -ForegroundColor Green
Write-Host " Stop everything:  .\stop-all.ps1`n" -ForegroundColor DarkGray
