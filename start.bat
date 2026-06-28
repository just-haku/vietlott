@echo off
rem SOUL · Vietlott Deterministic Universe — Startup Script (Windows Batch)
title SOUL - Vietlott Deterministic Universe

cd /d "%~dp0"

echo ============================================================
echo 🎱 SOUL - Starting Pipeline Server...
echo ============================================================

rem 1. Virtual Environment Setup
if not exist ".venv" (
    echo [INFO] Virtual environment (.venv) not found. Setting up...
    where uv >nul 2>nul
    if %errorlevel% equ 0 (
        uv venv
        uv pip install -r requirements.txt
    ) else (
        where python >nul 2>nul
        if %errorlevel% equ 0 (
            python -m venv .venv
            .venv\Scripts\pip install -r requirements.txt
        ) else (
            echo [ERROR] Python or uv is required to set up the environment.
            pause
            exit /b 1
        )
    )
    echo [INFO] Environment created successfully.
)

rem Activate virtualenv
call .venv\Scripts\activate.bat

rem 2. Extract Features if missing
if not exist "data\features.jsonl" (
    echo [INFO] Data features not found. Extracting mathematical features...
    python scripts\run_analyzer.py
    echo [INFO] Feature extraction complete.
)

rem 3. Start Frontend Dashboard
echo [INFO] Starting Dashboard on http://localhost:5000...
python scripts/run_frontend.py
pause
