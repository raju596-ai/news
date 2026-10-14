@echo off
title AI News Video Automated Daily Scheduler (8:30 AM & 5:00 PM)
cd /d "%~dp0"
echo ==============================================================================
echo NewsIntel Automated Daily Scheduler (8:30 AM & 5:00 PM)
echo ==============================================================================
echo Activating virtual environment...
call .venv\Scripts\activate
echo Starting continuous scheduler...
uv run python -m news.scheduler %*
pause
