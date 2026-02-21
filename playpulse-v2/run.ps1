# PlayPulse v2 — Run Script (PowerShell)
# Start backend + frontend + game server + desktop capture agent

Write-Host "=== PlayPulse v2 ===" -ForegroundColor Cyan

# Install desktop dependencies
$desktopReq = Join-Path $PSScriptRoot "desktop\requirements.txt"
if (Test-Path $desktopReq) {
    Write-Host "`n[0/4] Installing desktop capture dependencies..." -ForegroundColor Yellow
    pip install -q -r $desktopReq 2>$null
}

# Backend
Write-Host "`n[1/4] Starting backend on :8000..." -ForegroundColor Yellow
$backendDir = Join-Path $PSScriptRoot "backend"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$backendDir'; python main.py" -PassThru | Out-Null

Start-Sleep 2

# Frontend (dev server)
Write-Host "[2/4] Starting frontend on :3000..." -ForegroundColor Yellow
$frontendDir = Join-Path $PSScriptRoot "frontend"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$frontendDir'; npx vite --host" -PassThru | Out-Null

# Game (simple HTTP server)
Write-Host "[3/4] Starting game server on :8080..." -ForegroundColor Yellow
$gameDir = Join-Path $PSScriptRoot "game"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$gameDir'; python -m http.server 8080" -PassThru | Out-Null

# Desktop Capture Agent
Write-Host "[4/4] Launching AURA Desktop Capture Agent..." -ForegroundColor Yellow
$desktopDir = Join-Path $PSScriptRoot "desktop"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$desktopDir'; python main.py" -PassThru | Out-Null

Write-Host "`n--- All services started ---" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:8000"
Write-Host "  Frontend:  http://localhost:3000"
Write-Host "  Game:      http://localhost:8080"
Write-Host "  Desktop:   AURA Desktop Capture Agent (GUI)"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host "`nPress Ctrl+C to stop." -ForegroundColor DarkGray
Wait-Process -Id $PID 2>$null
