#!/bin/bash
# Launch local admin GUI for editing song/alias data.

set -e

# Move to project root
cd "$(dirname "$0")/.."

PORT=5757
URL="http://localhost:$PORT"

# Ensure venv
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

# Ensure deps (use python -m pip to match the active interpreter)
if ! python -c "import flask" >/dev/null 2>&1; then
  echo "Installing Flask..."
  python -m pip install -q flask
fi

# Ensure project deps (for normalizer etc.)
if ! python -c "import dotenv" >/dev/null 2>&1; then
  echo "Installing project requirements..."
  python -m pip install -q -r scripts/requirements.txt
fi

# Start server in background
python scripts/admin.py --port "$PORT" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT INT TERM

# Wait briefly for server, then open browser
sleep 1
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
else
  echo "Open $URL in your browser."
fi

echo ""
echo "Admin UI running at $URL"
echo "Press Ctrl+C to stop."
wait $SERVER_PID
