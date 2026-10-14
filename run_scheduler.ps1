# PowerShell launcher for NewsIntel Automated Daily Scheduler (8:30 AM & 5:00 PM)
Set-Location -Path $PSScriptRoot

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " NewsIntel Automated Daily Scheduler (8:30 AM & 5:00 PM)" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\activate.ps1") {
    & ".venv\Scripts\activate.ps1"
}

uv run python -m news.scheduler $args
