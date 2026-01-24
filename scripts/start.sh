#!/bin/bash
# Start both backend and frontend servers

set -e

SCRIPT_DIR="$(dirname "$0")"

echo "🚀 Starting Polymarket News Tracker..."
echo ""
echo "Starting backend on http://localhost:8000"
echo "Starting frontend on http://localhost:5173"
echo ""

# Start backend in background
"$SCRIPT_DIR/start_backend.sh" &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 3

# Start frontend in background  
"$SCRIPT_DIR/start_frontend.sh" &
FRONTEND_PID=$!

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for either process to exit
wait
