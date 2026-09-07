@echo off
title Dental WhatsApp Growth Engine - Local Dashboard
cd /d "%~dp0"

echo ======================================================================
echo    🦷 DENTAL WHATSAPP GROWTH ENGINE & LEAD INTELLIGENCE DASHBOARD
echo ======================================================================
echo.
echo  Starting local dashboard server...
echo  Your browser will open automatically to: http://127.0.0.1:8000
echo.
echo  To close the app at any time, just close this black command window.
echo ======================================================================
echo.

".venv\Scripts\python.exe" app.py
pause
