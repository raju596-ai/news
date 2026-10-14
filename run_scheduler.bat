@echo off
title AI News Video Automated Daily Scheduler (8:30 AM & 5:00 PM)
cd /d "%~dp0"

echo ==============================================================================
echo NewsIntel Automated Daily Scheduler (8:30 AM & 5:00 PM)
echo ==============================================================================

if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
)

REM Check for uv in PATH or local directory
set "UV_BIN="
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "UV_BIN=uv"
) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_BIN=%USERPROFILE%\.local\bin\uv.exe"
)

if defined UV_BIN (
    "%UV_BIN%" run python -m news.scheduler %*
) else if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m news.scheduler %*
) else (
    python -m news.scheduler %*
)

if "%1"=="" (
    pause
)
