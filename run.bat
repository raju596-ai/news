@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo   Starting AI News Video Platform (1080p 5-Min Pipeline)
echo   Dashboard URL: http://127.0.0.1:8000
echo ========================================================

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    "%USERPROFILE%\.local\bin\uv.exe" run uvicorn news.api.main:app --host 127.0.0.1 --port 8000 --reload
) else (
    uv run uvicorn news.api.main:app --host 127.0.0.1 --port 8000 --reload
)

pause

