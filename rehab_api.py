# rehab_api.py
# ---------------------------------------------------------------
# Sends the recorded session stats to Claude and gets back a plain-English
# hand-rehab progress report. This is the "API model" that reads the play +
# hand-movement history and tells the patient how their recovery is going.
#
# Auth: needs Anthropic credentials. Either export ANTHROPIC_API_KEY, or run
# `ant auth login` once (the SDK picks up the stored profile automatically).
# ---------------------------------------------------------------
import json

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

import rehab_data

# Load ANTHROPIC_API_KEY from a local .env file if present (see .env.example).
load_dotenv()

MODEL = "claude-opus-4-8"

SYSTEM = (
    "You are a supportive hand-rehabilitation coach analysing data from a "
    "Rock-Paper-Scissors game used for hand-injury physical therapy. The "
    "patient forms Rock (a full fist / flexion), Paper (a fully open hand / "
    "extension), and Scissors with their hand in front of a webcam.\n\n"
    "Field meanings in the JSON:\n"
    "- openness: normalised range-of-motion measure; higher = more extended.\n"
    "- avg_open_paper / avg_open_rock: how open the hand was on those gestures.\n"
    "- range_of_motion: avg paper openness minus avg rock openness. Bigger "
    "means the patient can BOTH open and close their hand more fully — the "
    "single most important recovery signal.\n"
    "- accuracy: fraction of gestures that were cleanly formed.\n"
    "- avg_hold_time: seconds they held a steady gesture (control/endurance).\n"
    "- range_of_motion_change_pct: change in range of motion from the first "
    "session to the most recent one.\n\n"
    "Compare earlier sessions to recent ones to judge progress. Be warm, "
    "specific, and encouraging. Ground every claim in the numbers. You are a "
    "motivational coach, not a doctor — never give a medical diagnosis, and "
    "suggest gentle, general hand exercises only."
)


class RehabReport(BaseModel):
    summary: str                 # one short paragraph on how they're doing
    improvement: str             # assessment of the range-of-motion trend
    improvement_percent: float   # estimated % change in range of motion
    encouragement: str           # a warm, motivating line
    exercises: list[str]         # 2-4 gentle hand exercises to try next


def generate_report(stats=None):
    """Ask Claude for a rehab progress report. Returns a plain dict."""
    if stats is None:
        stats = rehab_data.build_stats()

    if not stats.get("sessions"):
        raise ValueError("No play history yet - play a few rounds first.")

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                "Here is the patient's session data as JSON:\n\n"
                + json.dumps(stats, indent=2)
                + "\n\nWrite their hand-rehab progress report."
            ),
        }],
        output_format=RehabReport,
    )
    return response.parsed_output.model_dump()


if __name__ == "__main__":
    # Quick manual test: print a report for whatever history exists.
    print(json.dumps(generate_report(), indent=2))
