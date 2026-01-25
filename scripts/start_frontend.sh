#!/bin/bash
# Start the frontend dev server

set -e

cd "$(dirname "$0")/../src/frontend"

echo "🚀 Starting Polymarket News Tracker Frontend..."
echo ""

# Check if node is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed"
    exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

echo ""
echo "🔧 Starting Vite dev server on http://localhost:5173"
echo ""

# Run the dev server
exec npm run dev
