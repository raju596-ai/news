@echo off
title Link YouTube Channel (1-Time OAuth Consent)
cd /d "%~dp0"
echo ==============================================================================
echo  NewsIntel - YouTube Channel 1-Time Authorization
echo ==============================================================================
echo Opening browser for Google sign-in...
call .venv\Scripts\activate
uv run python -m news.tools.auth_youtube %*
pause
