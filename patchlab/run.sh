#!/usr/bin/env bash
# PatchLab — Launch everything with one command (macOS/Linux)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

# ── Colors ────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== PatchLab ===${NC}"
echo ""

# ── Ensure venv exists ────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo -e "${YELLOW}[setup] Creating Python virtual environment...${NC}"
  python3 -m venv "$VENV"
fi

# Find the correct Python executable in venv
if [ -f "$VENV/bin/python3.13" ]; then
  PYTHON="$VENV/bin/python3.13"
elif [ -f "$VENV/bin/python3" ]; then
  PYTHON="$VENV/bin/python3"
elif [ -f "$VENV/bin/python" ]; then
  PYTHON="$VENV/bin/python"
else
  echo -e "${YELLOW}[warning] No python found in venv, using system python3${NC}"
  PYTHON=$(which python3.13 || which python3)
fi
PIP="$PYTHON -m pip"

# ── Install backend deps if needed ────────────────────
if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
  echo -e "${YELLOW}[setup] Installing backend dependencies...${NC}"
  "$PIP" install -q -r "$DIR/backend/requirements.txt"
fi

# ── Install desktop deps if needed ────────────────────
if ! "$PYTHON" -c "import mss" 2>/dev/null; then
  echo -e "${YELLOW}[setup] Installing desktop capture dependencies...${NC}"
  "$PIP" install -q -r "$DIR/desktop/requirements.txt" 2>/dev/null || true
fi

# ── Install frontend deps if needed ───────────────────
if [ ! -d "$DIR/frontend/node_modules" ]; then
  echo -e "${YELLOW}[setup] Installing frontend dependencies...${NC}"
  (cd "$DIR/frontend" && npm install)
fi

# ── Trap Ctrl+C to kill all children ──────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down all services...${NC}"
  kill 0 2>/dev/null
  wait 2>/dev/null
  echo -e "${GREEN}All services stopped.${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Start services ────────────────────────────────────
echo -e "${BLUE}[1/4]${NC} Starting backend on :8000..."
(cd "$DIR/backend" && "$PYTHON" main.py) &
BACKEND_PID=$!

sleep 2

echo -e "${BLUE}[2/4]${NC} Starting frontend on :3000..."
(cd "$DIR/frontend" && npx vite --host --port 3000) &
FRONTEND_PID=$!

echo -e "${BLUE}[3/4]${NC} Starting game server on :8080..."
(cd "$DIR/game" && "$PYTHON" -m http.server 8080) &
GAME_PID=$!

sleep 1

echo -e "${BLUE}[4/4]${NC} Launching PatchLab Desktop Capture Agent..."
(cd "$DIR/desktop" && "$PYTHON" main.py) &
DESKTOP_PID=$!

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       All services running                ║${NC}"
echo -e "${GREEN}╠═══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Backend:   ${BLUE}http://localhost:8000${NC}        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Frontend:  ${BLUE}http://localhost:3000${NC}        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Game:      ${BLUE}http://localhost:8080${NC}        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Desktop:   PatchLab Capture Agent (GUI)  ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  API docs:  ${BLUE}http://localhost:8000/docs${NC}   ${GREEN}║${NC}"
echo -e "${GREEN}╠═══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Press ${YELLOW}Ctrl+C${NC} to stop all services      ${GREEN}║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
wait
