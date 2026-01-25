#!/bin/bash
# Start the backend server

set -e

cd "$(dirname "$0")/.."

echo "🚀 Starting Polymarket News Tracker Backend..."
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed"
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Sync dependencies
echo "📦 Installing dependencies..."
uv sync

echo ""
echo "🔧 Starting FastAPI server on http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo ""

# Run the server
exec uv run uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8000
