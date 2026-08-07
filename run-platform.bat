@echo off
title Factor-Alpha Screener
cd /d "%~dp0"

echo ============================================================
echo   Factor-Alpha Screener  -  running on your computer
echo ============================================================
echo.

REM --- 1. Make sure Python is available ------------------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on this PC.
  echo         Install Python 3.12+ from  https://www.python.org/downloads/
  echo         During install, TICK the box "Add python.exe to PATH".
  echo         Then double-click this file again.
  echo.
  pause
  exit /b 1
)

REM --- 2. First run: create a private environment + install dependencies ----
if not exist ".venv\Scripts\python.exe" (
  echo [setup] First run detected - creating a private Python environment...
  python -m venv .venv
  echo [setup] Installing dependencies ^(one time, about 1-2 minutes^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  echo [setup] Done.
  echo.
)

REM --- 3. Start the app and open the browser --------------------------------
echo [run] Starting the platform at  http://localhost:8000
echo       Keep this window OPEN while you use it.  Close it to stop the app.
echo.
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000

echo.
echo App stopped. You can close this window.
pause
