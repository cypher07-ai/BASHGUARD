#!/usr/bin/env bash
set -e

echo ""
echo "============================================================"
echo "  BashGuard -- Simulate Before You Execute"
echo "============================================================"
echo ""

# ---- Backend Setup ----
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt -q
echo "[1/4] Done."

# ---- Frontend Setup ----
echo "[2/4] Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..
echo "[2/4] Done."

# ---- Start Backend ----
echo "[3/4] Starting BashGuard API server on port 8000..."
uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
sleep 2

# ---- Start Frontend ----
echo "[4/4] Starting React frontend on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
sleep 2

echo ""
echo "============================================================"
echo "  BashGuard is running!"
echo "  Frontend : http://localhost:5173"
echo "  API      : http://localhost:8000"
echo "  API Docs : http://localhost:8000/docs"
echo "============================================================"
echo ""
echo "Press Ctrl+C to stop all servers."

# Open browser
if command -v open &>/dev/null; then
    open http://localhost:5173
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:5173
fi

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
