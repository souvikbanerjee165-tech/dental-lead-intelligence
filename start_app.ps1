# Dental WhatsApp Growth Engine - PowerShell Launcher
$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  DENTAL WHATSAPP GROWTH ENGINE & LEAD INTELLIGENCE" -ForegroundColor Green
Write-Host "  Autonomous Local Prospecting & Sales Machine" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check .venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[*] Creating virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
    & .venv\Scripts\pip.exe install -r requirements.txt
    & .venv\Scripts\playwright.exe install chromium
}

# Optional clean reset
if ($args -contains "--reset") {
    Write-Host "[*] Performing clean slate reset..." -ForegroundColor Magenta
    & .venv\Scripts\python.exe reset_clean.py
}

Write-Host "[✓] Environment verified." -ForegroundColor Green
Write-Host "[✓] SQLite WAL durability mode enabled." -ForegroundColor Green
Write-Host "[✓] Server starting at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""

# Launch default browser after 2 seconds
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

# Run server
& .venv\Scripts\python.exe app.py
