#!/bin/bash

# Rosetta Zero Dashboard - Local Development Startup Script

echo "=========================================="
echo "🚀 Rosetta Zero Dashboard - Local Setup"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi

echo "✅ Python and Node.js are installed"
echo ""

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend-local
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
cd ..
echo "✅ Backend dependencies installed"
echo ""

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
cd ..
echo "✅ Frontend dependencies installed"
echo ""

# Start backend server in background
echo "🔧 Starting backend server..."
cd backend-local
source venv/bin/activate
python server.py &
BACKEND_PID=$!
cd ..
echo "✅ Backend server started (PID: $BACKEND_PID)"
echo ""

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 3
echo ""

# Start frontend server
echo "🌐 Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
echo "✅ Frontend server started (PID: $FRONTEND_PID)"
echo ""

echo "=========================================="
echo "✨ Dashboard is ready!"
echo "=========================================="
echo ""
echo "📡 Backend API:  http://localhost:5000"
echo "🌐 Frontend:     http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '✅ Servers stopped'; exit 0" INT

# Keep script running
wait
