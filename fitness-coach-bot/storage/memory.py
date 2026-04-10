"""
Long-term memory for the fitness coach bot.
Claude reads this at every session start and writes to it when it learns something new.
Stored as JSON — simple, human-readable, editable.
"""

import json
import os
import logging
import datetime

logger = logging.getLogger(__name__)

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "long_term_memory.json")

DEFAULT_MEMORY = {
    "athlete": {
        "name": "Toan",
        "age": 20,
        "height_cm": 170,
        "starting_weight_kg": 69.0,
        "current_weight_kg": None,
        "goal": "V-taper, smaller waist, bigger chest/upper body, bench + pull-up progression, stamina"
    },
    "personal_records": {
        "bench_press_kg": 40,
        "bench_press_reps": 5,
        "pull_ups": 8,
        "overhead_press_kg": None,
        "barbell_row_kg": 49,
        "dips_bw_reps": None
    },
    "current_program_week": 1,
    "phase": "4-week aggressive (date deadline end of April 2026)",
    "measurements": {
        "waist_cm": None,
        "chest_cm": None,
        "last_measured": None
    },
    "coaching_notes": [],
    "patterns": [],
    "sleep_notes": "Goes to bed 1-2am, needs to shift to 11pm. Night calls and late work are the obstacle.",
    "nutrition_notes": "Uses meal prep service. Target 1700-1900 cal, 130-140g protein.",
    "injuries_flags": [],
    "milestones": [],
    "preferences": [
        "Dislikes walls of text — keep responses short",
        "Responds well to data-backed feedback",
        "Swimming for cardio + stamina",
        "Football occasionally (treats as HIIT)",
        "Has resistance bands, ab wheel, chalk"
    ],
    "conversation_log": []
}


def load_memory():
    """Load long-term memory from disk. Creates defaults if not exists."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                # Merge with defaults to handle new keys added over time
                for key, val in DEFAULT_MEMORY.items():
                    if key not in data:
                        data[key] = val
                    elif isinstance(val, dict) and isinstance(data.get(key), dict):
                        for subkey, subval in val.items():
                            if subkey not in data[key]:
                                data[key][subkey] = subval
                return data
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
    # First run — create defaults
    save_memory(DEFAULT_MEMORY)
    return DEFAULT_MEMORY.copy()


def save_memory(memory):
    """Save long-term memory to disk."""
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")


def update_memory(updates: dict):
    """
    Apply updates to memory. Supports nested keys.
    updates = {
        "personal_records.bench_press_kg": 42.5,
        "coaching_notes": ["append", "struggles with elbow flare on bench"],
        "milestones": ["append", "First 3x8 pull-ups on 2026-04-06"],
    }
    The special value ["append", item] appends to a list instead of replacing.
    """
    memory = load_memory()

    for key, value in updates.items():
        if "." in key:
            # Nested key e.g. "personal_records.bench_press_kg"
            parts = key.split(".", 1)
            parent, child = parts[0], parts[1]
            if parent not in memory:
                memory[parent] = {}
            if isinstance(value, list) and len(value) == 2 and value[0] == "append":
                if not isinstance(memory[parent].get(child), list):
                    memory[parent][child] = []
                memory[parent][child].append(value[1])
            else:
                memory[parent][child] = value
        else:
            if isinstance(value, list) and len(value) == 2 and value[0] == "append":
                if not isinstance(memory.get(key), list):
                    memory[key] = []
                memory[key].append(value[1])
            else:
                memory[key] = value

    save_memory(memory)
    return memory


def log_conversation_turn(role: str, content: str):
    """Append a conversation turn to the log (capped at 200 entries)."""
    memory = load_memory()
    if "conversation_log" not in memory:
        memory["conversation_log"] = []

    memory["conversation_log"].append({
        "ts": datetime.datetime.now().isoformat(),
        "role": role,
        "content": content[:500] if isinstance(content, str) else "[image/media]"
    })

    # Keep last 200 turns
    memory["conversation_log"] = memory["conversation_log"][-200:]
    save_memory(memory)


def get_memory_as_context() -> str:
    """Format memory as a readable context string for the system prompt."""
    mem = load_memory()
    lines = []

    # PRs
    pr = mem.get("personal_records", {})
    pr_parts = []
    if pr.get("bench_press_kg"):
        pr_parts.append(f"Bench {pr['bench_press_kg']}kg x {pr.get('bench_press_reps', '?')}")
    if pr.get("pull_ups"):
        pr_parts.append(f"Pull-ups {pr['pull_ups']} reps")
    if pr.get("overhead_press_kg"):
        pr_parts.append(f"OHP {pr['overhead_press_kg']}kg")
    if pr.get("barbell_row_kg"):
        pr_parts.append(f"Row {pr['barbell_row_kg']}kg")
    if pr_parts:
        lines.append("**Current PRs:** " + " | ".join(pr_parts))

    # Weight & measurements
    athlete = mem.get("athlete", {})
    if athlete.get("current_weight_kg"):
        lines.append(f"**Current weight:** {athlete['current_weight_kg']}kg")
    meas = mem.get("measurements", {})
    if meas.get("waist_cm") or meas.get("chest_cm"):
        parts = []
        if meas.get("waist_cm"): parts.append(f"Waist {meas['waist_cm']}cm")
        if meas.get("chest_cm"): parts.append(f"Chest {meas['chest_cm']}cm")
        lines.append("**Measurements:** " + " | ".join(parts))

    # Program state
    lines.append(f"**Program week:** {mem.get('current_program_week', 1)} — {mem.get('phase', '')}")

    # Coaching notes (last 5)
    notes = mem.get("coaching_notes", [])
    if notes:
        lines.append("**Coaching notes:**")
        for n in notes[-5:]:
            lines.append(f"  - {n}")

    # Patterns (last 5)
    patterns = mem.get("patterns", [])
    if patterns:
        lines.append("**Observed patterns:**")
        for p in patterns[-5:]:
            lines.append(f"  - {p}")

    # Milestones (last 5)
    milestones = mem.get("milestones", [])
    if milestones:
        lines.append("**Milestones:**")
        for m in milestones[-5:]:
            lines.append(f"  - {m}")

    # Injuries/flags
    flags = mem.get("injuries_flags", [])
    if flags:
        lines.append("**Active flags/injuries:** " + "; ".join(flags))

    # Recent conversation log (last 20 turns)
    log = mem.get("conversation_log", [])
    if log:
        lines.append("\n**Recent conversation history:**")
        for entry in log[-20:]:
            role = entry.get("role", "?")
            content = entry.get("content", "")
            ts = entry.get("ts", "")[:16]  # Just date + hour:min
            lines.append(f"  [{ts}] {role}: {content[:200]}")

    return "\n".join(lines)
