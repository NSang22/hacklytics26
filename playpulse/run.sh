#!/usr/bin/env bash
# PlayPulse — local dev launcher
# Starts backend (port 8000), frontend (port 3000), and game server (port 8080)

set -e

echo "▸ Starting PlayPulse backend on :8000"
cd "$(dirname "$0")/backend"
pip install -q -r requirements.txt
python main.py &
BACKEND_PID=$!

echo "▸ Starting PlayPulse frontend on :3000"
cd "$(dirname "$0")/frontend"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo "▸ Serving demo game on :8080"
cd "$(dirname "$0")/game"
python -m http.server 8080 &
GAME_PID=$!

echo ""
echo "  Backend   → http://localhost:8000"
echo "  Frontend  → http://localhost:3000"
echo "  Game      → http://localhost:8080/index.html"
echo ""
echo "Press Ctrl+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID $GAME_PID 2>/dev/null" EXIT
wait
