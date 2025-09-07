#!/bin/bash

# Script to run macOS monitor with proper Python environment
cd "$(dirname "$0")"

echo "Starting macOS System Monitor..."
echo "Using virtual environment for psutil dependency"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install psutil
    echo "✅ Virtual environment created and psutil installed"
else
    echo "✅ Using existing virtual environment"
fi

echo "Press 'q' to quit when the monitor starts"
echo ""

# Activate virtual environment and run monitor
source venv/bin/activate && python3 macos_monitor.py