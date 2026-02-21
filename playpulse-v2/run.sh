#!/usr/bin/env bash
# PlayPulse v2 — Run Script (bash)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== PlayPulse v2 ==="

# ── Install desktop dependencies if needed ───────────
if [ -f "$DIR/desktop/requirements.txt" ]; then
  echo "[0/4] Installing desktop capture dependencies..."
  pip install -q -r "$DIR/desktop/requirements.txt" 2>/dev/null || true
fi

echo "[1/4] Starting backend on :8000..."
(cd "$DIR/backend" && python main.py) &

sleep 2

echo "[2/4] Starting frontend on :3000..."
(cd "$DIR/frontend" && npx vite --host) &

echo "[3/4] Starting game server on :8080..."
(cd "$DIR/game" && python -m http.server 8080) &

echo "[4/4] Launching AURA Desktop Capture Agent..."
(cd "$DIR/desktop" && python main.py) &

echo ""
echo "--- All services started ---"
echo "  Backend:   http://localhost:8000"
echo "  Frontend:  http://localhost:3000"
echo "  Game:      http://localhost:8080"
echo "  Desktop:   AURA Desktop Capture Agent (GUI)"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
wait
