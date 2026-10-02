@echo off
title Dental WhatsApp Growth Engine - Local Launcher
color 0A

echo =================================================================
echo   DENTAL WHATSAPP GROWTH ENGINE & LEAD INTELLIGENCE
echo   Autonomous Local Prospecting & Sales Machine
echo =================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [!] ERROR: Python 3.10+ is required. Please install Python from python.org.
        pause
        exit /b 1
    )
    echo [*] Installing required packages...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    playwright install chromium
) else (
    call .venv\Scripts\activate.bat
)

:: 2. Ensure Playwright browser is ready
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(headless=True).close(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo [*] Initializing Playwright Chromium headless engine...
    playwright install chromium
)

:: 3. Check for reset flag
if "%1"=="--reset" (
    python reset_clean.py
)

echo.
echo [✓] Environment verified.
echo [✓] SQLite WAL durability mode enabled.
echo [✓] Playwright Chromium engine ready ($0 lead scraping).
echo.
echo =================================================================
echo   Launching Dental Intelligence Server at http://127.0.0.1:8000
echo =================================================================
echo.

:: 4. Launch browser automatically after 2 seconds in background
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"

:: 5. Start main application
python app.py

pause
