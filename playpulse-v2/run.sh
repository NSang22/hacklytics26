#!/usr/bin/env bash
# PlayPulse v2 — Run Script (bash)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== PlayPulse v2 ==="

echo "[1/3] Starting backend on :8000..."
(cd "$DIR/backend" && python main.py) &

sleep 2

echo "[2/3] Starting frontend on :3000..."
(cd "$DIR/frontend" && npx vite --host) &

echo "[3/3] Starting game server on :8080..."
(cd "$DIR/game" && python -m http.server 8080) &

echo ""
echo "--- All services started ---"
echo "  Backend:   http://localhost:8000"
echo "  Frontend:  http://localhost:3000"
echo "  Game:      http://localhost:8080"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
wait
