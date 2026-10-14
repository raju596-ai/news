# Run the News Intelligence FastAPI backend and frontend dashboard
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Check user local bin first, then system PATH
$uvBin = if (Test-Path "$env:USERPROFILE\.local\bin\uv.exe") {
    "$env:USERPROFILE\.local\bin\uv.exe"
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    "uv"
} else {
    "uv"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Starting AI News Video Platform (1080p 5-Min Pipeline)" -ForegroundColor Green
Write-Host "  Dashboard URL: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

& $uvBin run uvicorn news.api.main:app --host 127.0.0.1 --port 8000 --reload
