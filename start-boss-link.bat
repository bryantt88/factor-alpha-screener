@echo off
title AI-Power Screener - Boss Link
cd /d "%~dp0"

echo ============================================================
echo   AI-Power Screener  -  starting your shareable link
echo ============================================================
echo.
echo [1/2] Starting the app (data + calculations) on port 8000...
start "AI-Power Screener app" /min cmd /c "python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000"

echo       waiting a few seconds for it to boot...
timeout /t 8 >nul

echo.
echo [2/2] Creating your public link.
echo       Look below for the  https://xxxxx.trycloudflare.com  address
echo       and send THAT link to your boss.
echo.
echo   *** Keep this window OPEN while your boss is using it. ***
echo   *** Close this window (and the minimized app window) to stop. ***
echo.
cloudflared tunnel --url http://localhost:8000 --no-autoupdate

echo.
echo Link stopped. You can close this window.
pause
