# PlayPulse — local dev launcher (Windows PowerShell)
# Starts backend (:8000), frontend (:3000), and game server (:8080)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "▸ Starting PlayPulse backend on :8000" -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "$root\backend"

Write-Host "▸ Starting PlayPulse frontend on :3000" -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$root\frontend"

Write-Host "▸ Serving demo game on :8080" -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m http.server 8080" -WorkingDirectory "$root\game"

Write-Host ""
Write-Host "  Backend   -> http://localhost:8000"
Write-Host "  Frontend  -> http://localhost:3000"
Write-Host "  Game      -> http://localhost:8080/index.html"
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow

# Keep script alive so Ctrl+C can interrupt
while ($true) { Start-Sleep -Seconds 60 }
