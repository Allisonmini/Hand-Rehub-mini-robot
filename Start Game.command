#!/bin/bash
# ---------------------------------------------------------------
# Double-click this file in Finder to start the RPS camera game.
# A camera window opens - show your hand to play. No typing needed.
# To stop: press Q or Esc in the camera window (or close this window).
# ---------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

# Use the project's virtual environment if it's set up, else system python3.
if [ -x ".venv/bin/python3" ]; then
    PY=".venv/bin/python3"
else
    PY="python3"
fi

echo "Starting the RPS game..."
echo "A camera window will open - show your hand to play."
echo "Thumbs UP = start,  Thumbs DOWN = quit."
echo "To stop: press Q or Esc in the camera window, or close this window."
echo

# Force native arm64 so the camera/AI libraries load correctly.
exec arch -arm64 "$PY" game.py
