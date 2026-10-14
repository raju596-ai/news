@echo off
title Stop NewsIntel Automated Scheduler
echo Stopping any running news.scheduler instances...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*news.scheduler*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo NewsIntel scheduler stopped.
pause
