#!/usr/bin/env bash
# Factor-Alpha Screener - one-command desktop launcher for macOS / Linux.
# First run creates a private virtualenv and installs dependencies; later runs just start the app.
set -e
cd "$(dirname "$0")"

# --- 1. Make sure Python is available ---------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] Python 3.12+ is required. Install it from https://www.python.org/downloads/"
  exit 1
fi

# --- 2. First run: create the environment + install dependencies ------------
if [ ! -x ".venv/bin/python" ]; then
  echo "[setup] First run detected - creating a private Python environment..."
  python3 -m venv .venv
  echo "[setup] Installing dependencies (one time)..."
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install -r requirements.txt
  echo "[setup] Done."
fi

# --- 3. Gentle hint if the optional AI key isn't set ------------------------
if [ ! -f ".env" ]; then
  echo "[note] AI features are OFF (everything else works). To turn them on:"
  echo "       copy .env.example to .env and paste your own Gemini API key."
fi

# --- 4. Open the browser shortly after, then run the server (blocks) --------
echo "[run] Starting the platform at http://localhost:8000  (press Ctrl+C to stop)"
(
  sleep 4
  if command -v open >/dev/null 2>&1; then open http://localhost:8000
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:8000
  fi
) &
exec ./.venv/bin/python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
