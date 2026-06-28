#!/bin/bash
# SOUL · Vietlott Deterministic Universe — Startup Script (Linux/macOS)
set -e

# Change directory to the repository root
cd "$(dirname "$0")"

echo "============================================================"
# Clean color outputs
cyan() { echo -e "\e[36m$1\e[0m"; }
green() { echo -e "\e[32m$1\e[0m"; }
yellow() { echo -e "\e[33m$1\e[0m"; }

cyan "🎱 SOUL — Starting Pipeline Server..."
echo "============================================================"

# 1. Virtual Environment Setup
if [ ! -d ".venv" ]; then
    yellow "⚠️ Virtual environment (.venv) not found. Setting up..."
    if command -v uv &> /dev/null; then
        uv venv
        uv pip install -r requirements.txt
    elif command -v python3 &> /dev/null; then
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt
    else
        echo "❌ Python 3 or uv is required to set up the environment."
        exit 1
    fi
    green "✅ Environment created."
fi

# Activate virtualenv
source .venv/bin/activate

# 2. Extract Features if missing
if [ ! -f "data/features.jsonl" ]; then
    yellow "⚠️ Data features not found. Extracting mathematical features..."
    python scripts/run_analyzer.py
    green "✅ Feature extraction complete."
fi

# 3. Start Frontend Dashboard
cyan "🌐 Starting Dashboard on http://localhost:5000..."
python scripts/run_frontend.py
