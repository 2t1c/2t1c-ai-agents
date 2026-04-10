"""
Habits Tracker — Daily non-negotiables for Toản.

Stores daily completion data in a JSON file.
The CEO bot uses this to send reminders and track streaks.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

HABITS_FILE = Path(__file__).resolve().parent / "habits_log.json"

NON_NEGOTIABLES = [
    {"id": "posts", "name": "Schedule 3 high-performing posts for GeniusGTX", "short": "3 posts scheduled"},
    {"id": "write", "name": "Write 1000 words", "short": "1000 words written"},
    {"id": "read", "name": "Read 30 minutes", "short": "30 min reading"},
    {"id": "cardio", "name": "Any form of cardio for at least 30 minutes", "short": "30 min cardio"},
    {"id": "study", "name": "1-2 hours dedicated to studying something difficult", "short": "1-2hr deep study"},
    {"id": "strength", "name": "Strength training >30 minutes", "short": "30+ min strength"},
]


def _load_log() -> dict:
    if HABITS_FILE.exists():
        return json.loads(HABITS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_log(log: dict):
    HABITS_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_today_status() -> dict:
    """Get today's completion status. Returns dict of habit_id -> bool."""
    log = _load_log()
    today = _today()
    if today not in log:
        log[today] = {h["id"]: False for h in NON_NEGOTIABLES}
        _save_log(log)
    return log[today]


def mark_complete(habit_id: str) -> bool:
    """Mark a habit as complete for today. Returns True if found."""
    log = _load_log()
    today = _today()
    if today not in log:
        log[today] = {h["id"]: False for h in NON_NEGOTIABLES}

    if habit_id in log[today]:
        log[today][habit_id] = True
        _save_log(log)
        return True
    return False


def mark_incomplete(habit_id: str) -> bool:
    """Undo a habit completion."""
    log = _load_log()
    today = _today()
    if today in log and habit_id in log[today]:
        log[today][habit_id] = False
        _save_log(log)
        return True
    return False


def get_today_score() -> tuple[int, int]:
    """Returns (completed, total) for today."""
    status = get_today_status()
    completed = sum(1 for v in status.values() if v)
    return completed, len(NON_NEGOTIABLES)


def get_streak() -> int:
    """How many consecutive days all 6 were completed (not counting today)."""
    log = _load_log()
    streak = 0
    date = datetime.now() - timedelta(days=1)

    while True:
        key = date.strftime("%Y-%m-%d")
        if key not in log:
            break
        day_data = log[key]
        if all(day_data.get(h["id"], False) for h in NON_NEGOTIABLES):
            streak += 1
            date -= timedelta(days=1)
        else:
            break

    return streak


def get_week_summary() -> dict:
    """Get the last 7 days of habit data."""
    log = _load_log()
    summary = {"days": [], "avg_score": 0, "weakest": "", "strongest": ""}

    totals = {h["id"]: 0 for h in NON_NEGOTIABLES}
    days_counted = 0

    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        if date in log:
            day = log[date]
            completed = sum(1 for v in day.values() if v)
            summary["days"].append({"date": date, "score": completed, "total": len(NON_NEGOTIABLES)})
            for h in NON_NEGOTIABLES:
                if day.get(h["id"], False):
                    totals[h["id"]] += 1
            days_counted += 1

    if days_counted > 0:
        total_score = sum(d["score"] for d in summary["days"])
        summary["avg_score"] = round(total_score / days_counted, 1)

        # Weakest and strongest
        sorted_habits = sorted(totals.items(), key=lambda x: x[1])
        summary["weakest"] = next(h["short"] for h in NON_NEGOTIABLES if h["id"] == sorted_habits[0][0])
        summary["strongest"] = next(h["short"] for h in NON_NEGOTIABLES if h["id"] == sorted_habits[-1][0])

    return summary


def format_morning_reminder() -> str:
    """Format the morning non-negotiables reminder."""
    streak = get_streak()
    streak_text = f"Current streak: {streak} day{'s' if streak != 1 else ''}." if streak > 0 else ""

    lines = [
        "6 non-negotiables. No zeros today.",
        "",
    ]
    for i, h in enumerate(NON_NEGOTIABLES, 1):
        lines.append(f"  {i}. {h['name']}")

    lines.append("")
    if streak_text:
        lines.append(streak_text)
    lines.append("")
    lines.append("Reply anytime to check off completed items.")

    return "\n".join(lines)


def format_midday_checkin() -> str:
    """Format the mid-day check-in."""
    status = get_today_status()
    done, total = get_today_score()

    lines = [f"Halfway check — {done}/{total} done so far.", ""]

    for h in NON_NEGOTIABLES:
        check = "done" if status.get(h["id"], False) else "    "
        lines.append(f"  [{check}] {h['short']}")

    remaining = total - done
    if remaining > 0:
        lines.append(f"\n{remaining} left. You got this.")
    else:
        lines.append("\nAll 6 done before 2pm. Monster day.")

    return "\n".join(lines)


def format_evening_scorecard() -> str:
    """Format the end-of-day scorecard."""
    status = get_today_status()
    done, total = get_today_score()
    streak = get_streak()

    lines = [f"End of day — {done}/{total}.", ""]

    for h in NON_NEGOTIABLES:
        check = "done" if status.get(h["id"], False) else "miss"
        lines.append(f"  [{check}] {h['short']}")

    lines.append("")

    if done == total:
        new_streak = streak + 1
        lines.append(f"Perfect day. Streak: {new_streak} days.")
    elif done >= 4:
        lines.append(f"Solid day. {total - done} missed — note what blocked you.")
    else:
        lines.append(f"Rough one. Reset tomorrow. No compounding guilt.")

    lines.append("\nAnything you want to log or adjust?")

    return "\n".join(lines)


def format_weekly_summary() -> str:
    """Format the weekly summary."""
    summary = get_week_summary()

    if not summary["days"]:
        return "No habit data this week yet."

    lines = [
        f"Weekly habits — {summary['avg_score']}/{len(NON_NEGOTIABLES)} avg",
        "",
    ]

    for day in reversed(summary["days"]):
        lines.append(f"  {day['date']}: {day['score']}/{day['total']}")

    lines.append("")
    lines.append(f"Strongest: {summary['strongest']}")
    lines.append(f"Weakest: {summary['weakest']}")
    lines.append("\nAdjust anything for next week?")

    return "\n".join(lines)
