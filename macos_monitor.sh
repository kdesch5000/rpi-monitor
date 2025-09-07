#!/bin/bash

# Script to run macOS monitor with proper Python environment
cd "$(dirname "$0")"

echo "macOS System Monitor Setup"
echo "=========================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Setting up Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install psutil
    echo "✅ Virtual environment created and dependencies installed"
    echo ""
else
    echo "✅ Virtual environment found"
fi

echo "Note: The monitor will ask for sudo access for accurate temperature readings."
echo "      This is optional - you can decline and use temperature estimation instead."
echo ""

# Activate virtual environment and run monitor
source venv/bin/activate && python3 macos_monitor.py