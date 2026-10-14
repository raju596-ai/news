@echo off
title Install Production Windows Task Scheduler (Daily 2 Times)
cd /d "%~dp0"
echo ==============================================================================
echo Installing Windows Task Scheduler Jobs (Daily 8:30 AM & 5:00 PM)
echo ==============================================================================
powershell -ExecutionPolicy Bypass -File "%~dp0setup_windows_task_scheduler.ps1"
pause
