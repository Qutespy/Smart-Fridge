#!/bin/bash
# Smart Fridge — start both backend and frontend

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/SmartFridge-main-2/smart_fridge_core"
FRONTEND_DIR="$SCRIPT_DIR/gui-files"

echo "=== Smart Fridge ==="

# Seed demo data
echo "[1/3] Seeding demo data..."
cd "$BACKEND_DIR" && python3 seed.py 2>&1

# Start backend (FastAPI on port 8000)
echo "[2/3] Starting FastAPI backend on :8000..."
cd "$BACKEND_DIR" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2

# Start frontend (Flask on port 5000)
echo "[3/3] Starting Flask frontend on :5000..."
cd "$FRONTEND_DIR" && python3 app.py &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000  (API docs: http://localhost:8000/docs)"
echo "Frontend: http://localhost:5000"
echo "Login:    demo@smartfridge.com / demo123"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
