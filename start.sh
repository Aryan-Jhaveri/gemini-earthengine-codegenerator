#!/bin/bash
# Start both the backend and frontend

echo "🚀 Starting Orbital Insight..."

# Start backend
echo "Starting backend API on port 8000..."
cd "$(dirname "$0")"
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
echo "Starting frontend on port 3000..."
cd app
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Orbital Insight is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both services"

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

# Wait
wait
