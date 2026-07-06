#!/bin/bash
# ---------------------------------------------------------------
# Double-click this file in Finder to open the RPS Rehab dashboard.
# It starts the local web app and opens it in your browser for you.
# To stop the dashboard: close this window or press Control-C.
# ---------------------------------------------------------------

# Run from the folder this file lives in, wherever it was double-clicked.
cd "$(dirname "$0")" || exit 1

# Use the project's virtual environment if it's set up, else system python3.
if [ -x ".venv/bin/python3" ]; then
    PY=".venv/bin/python3"
else
    PY="python3"
fi

echo "Starting the RPS Rehab dashboard..."
echo "Your browser will open automatically in a moment."
echo "Keep this window open while you use the dashboard."
echo "To stop it: close this window or press Control-C."
echo

exec "$PY" dashboard.py
