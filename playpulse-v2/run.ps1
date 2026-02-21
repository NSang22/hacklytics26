# PlayPulse v2 — Run Script (PowerShell)
# Start backend + frontend + game server

Write-Host "=== PlayPulse v2 ===" -ForegroundColor Cyan

# Backend
Write-Host "`n[1/3] Starting backend on :8000..." -ForegroundColor Yellow
$backendDir = Join-Path $PSScriptRoot "backend"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$backendDir'; python main.py" -PassThru | Out-Null

Start-Sleep 2

# Frontend (dev server)
Write-Host "[2/3] Starting frontend on :3000..." -ForegroundColor Yellow
$frontendDir = Join-Path $PSScriptRoot "frontend"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$frontendDir'; npx vite --host" -PassThru | Out-Null

# Game (simple HTTP server)
Write-Host "[3/3] Starting game server on :8080..." -ForegroundColor Yellow
$gameDir = Join-Path $PSScriptRoot "game"
Start-Process -NoNewWindow powershell -ArgumentList "-Command cd '$gameDir'; python -m http.server 8080" -PassThru | Out-Null

Write-Host "`n--- All services started ---" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:8000"
Write-Host "  Frontend:  http://localhost:3000"
Write-Host "  Game:      http://localhost:8080"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host "`nPress Ctrl+C to stop." -ForegroundColor DarkGray
Wait-Process -Id $PID 2>$null
