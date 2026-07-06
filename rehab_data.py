# rehab_data.py
# ---------------------------------------------------------------
# Stores the history of every round the player makes and turns it into
# the numbers the dashboard and the Claude report need.
#
# Each round records what was played, the win/lose result, and the
# range-of-motion metrics from gesture.hand_metrics() (how fully the
# patient could open/close their hand). Everything is kept in
# data/history.json so it survives across sessions.
# ---------------------------------------------------------------
import json
import os
import time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# A gap longer than this (seconds) between rounds starts a new "session",
# so we can compare earlier therapy sessions to more recent ones.
SESSION_GAP = 600  # 10 minutes


def clear_history():
    """Erase all recorded rounds, backing the old data up to history.bak.json
    first so an accidental Clear Data can be recovered."""
    os.makedirs(DATA_DIR, exist_ok=True)
    existing = load_history()
    if existing:
        with open(os.path.join(DATA_DIR, "history.bak.json"), "w") as f:
            json.dump(existing, f, indent=2)
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)


def load_history():
    """Every round ever recorded, oldest first (empty list if none yet)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def record_round(player, ai, result, mode, gesture, metrics, hold_time, clear):
    """Append one round to the history file and return the stored record."""
    os.makedirs(DATA_DIR, exist_ok=True)
    history = load_history()
    metrics = metrics or {}
    history.append({
        "ts": time.time(),
        "time": datetime.now().isoformat(timespec="seconds"),
        "player": player,               # "R" / "P" / "S"
        "ai": ai,
        "result": result,               # "WIN" / "LOSE" / "TIE"
        "mode": mode,
        "gesture": gesture,             # "Rock" / "Paper" / "Scissors" / "Unknown"
        "openness": metrics.get("openness"),
        "finger_ext": metrics.get("finger_ext"),
        "spread": metrics.get("spread"),
        "hold_time": round(hold_time, 2),
        "clear": bool(clear),           # was the gesture cleanly formed?
    })
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    return history[-1]


# --- Analysis -----------------------------------------------------------

def split_sessions(history):
    """Group the flat history into sessions separated by idle gaps."""
    sessions = []
    current = []
    last_ts = None
    for r in history:
        if last_ts is not None and r["ts"] - last_ts > SESSION_GAP:
            sessions.append(current)
            current = []
        current.append(r)
        last_ts = r["ts"]
    if current:
        sessions.append(current)
    return sessions


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def session_stats(rounds):
    """Summarise one session: accuracy, hand openness, and range of motion."""
    n = len(rounds)
    clear = [r for r in rounds if r.get("clear")]
    paper = [r["openness"] for r in rounds
             if r.get("gesture") == "Paper" and r.get("openness") is not None]
    rock = [r["openness"] for r in rounds
            if r.get("gesture") == "Rock" and r.get("openness") is not None]
    holds = [r.get("hold_time") for r in rounds]

    avg_paper = _avg(paper)
    avg_rock = _avg(rock)
    # Range of motion = how much fuller "open" (paper) is than "closed" (rock).
    # A larger number means the patient can both extend and flex more fully.
    rom = round(avg_paper - avg_rock, 3) if (avg_paper is not None and avg_rock is not None) else None

    return {
        "rounds": n,
        "accuracy": round(len(clear) / n, 3) if n else None,
        "avg_open_paper": avg_paper,
        "avg_open_rock": avg_rock,
        "range_of_motion": rom,
        "avg_hold_time": _avg(holds),
        "start": rounds[0]["time"],
        "end": rounds[-1]["time"],
    }


def build_stats():
    """Everything the dashboard/report needs, computed from the history."""
    history = load_history()
    sessions = split_sessions(history)
    per_session = [session_stats(s) for s in sessions]

    improvement = None
    # Compare the first and most recent sessions that both have a ROM value.
    roms = [s for s in per_session if s["range_of_motion"] is not None]
    if len(roms) >= 2:
        first, last = roms[0]["range_of_motion"], roms[-1]["range_of_motion"]
        if first:
            improvement = round((last - first) / abs(first) * 100, 1)

    return {
        "total_rounds": len(history),
        "total_sessions": len(sessions),
        "range_of_motion_change_pct": improvement,
        "sessions": per_session,
    }
