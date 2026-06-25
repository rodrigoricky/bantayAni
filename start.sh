#!/bin/bash
# Start Bantay Ani backend (8000) and frontend (3000)

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}

trap cleanup SIGINT SIGTERM

# Free ports if already in use
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 1

echo "Starting backend on http://localhost:8000 ..."
cd "$ROOT/backend"
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "  Bantay Ani is running"
echo "  App:     http://localhost:3000"
echo "  API:     http://localhost:8000/api"
echo "  Login:   mao.naga@da.gov.ph / demo123"
echo "============================================"
echo "Press Ctrl+C to stop both servers"
echo ""

wait