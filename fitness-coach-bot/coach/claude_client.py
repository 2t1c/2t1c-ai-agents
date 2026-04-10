"""
Claude API client for the fitness coach bot.
- tool_use: Claude logs data to Notion and updates long-term memory itself
- Conversation persists to disk (short-term buffer)
- Long-term memory: PRs, patterns, milestones, coaching notes
"""

import json
import os
import logging
import datetime
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL
from coach.system_prompt import get_system_prompt
from storage.notion_client import (
    log_workout, log_meal, log_measurement, log_sleep,
    create_workout_page, append_actual_entry, finish_workout_page,
    read_notion_query,
)
from coach.session_plans import SESSION_PLANS
from storage.memory import (
    load_memory, update_memory, log_conversation_turn, get_memory_as_context
)

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Short-term conversation buffer (current session, survives restarts via disk)
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "conversation_history.json")
MAX_BUFFER = 30

# Active workout session
active_session = {"type": None, "exercises_done": [], "started_at": None, "notion_page_id": None}


# ── Tool Definitions ──────────────────────────────────────────────────

TOOLS = [
    {
        "name": "log_workout",
        "description": (
            "Log a completed workout session to Notion. Call whenever Toan reports finishing "
            "exercises. Extract exercises, sets, reps, weights from the conversation. "
            "Log even partial sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_type": {
                    "type": "string",
                    "enum": ["Push A", "Push B", "Pull A", "Pull B", "Swimming", "Football", "Active Recovery"],
                },
                "exercises": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "sets": {"type": "string"},
                            "reps": {"type": "string"},
                            "weight": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
                "notes": {"type": "string"},
            },
            "required": ["session_type", "exercises"],
        },
    },
    {
        "name": "log_meal",
        "description": "Log a meal to Notion. Call when Toan shares what he ate. Estimate calories and protein.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "calories": {"type": "integer"},
                "protein": {"type": "integer"},
                "meal_type": {
                    "type": "string",
                    "enum": ["Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"],
                },
            },
            "required": ["description", "calories", "protein", "meal_type"],
        },
    },
    {
        "name": "log_measurement",
        "description": "Log body measurements to Notion when Toan shares them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "weight": {"type": "number"},
                "waist": {"type": "number"},
                "chest": {"type": "number"},
                "shoulders": {"type": "number"},
                "arms": {"type": "number"},
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "log_sleep",
        "description": "Log sleep data to Notion when Toan mentions sleep times or quality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bedtime": {"type": "string"},
                "wake_time": {"type": "string"},
                "hours": {"type": "number"},
                "quality": {"type": "string", "enum": ["Great", "Good", "OK", "Poor", "Terrible"]},
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "set_active_session",
        "description": (
            "Start or end a workout session. Call when Toan says he's starting a workout — "
            "this immediately creates the Notion page with the planned exercises so tracking "
            "begins right away. Use 'none' to end the session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_type": {
                    "type": "string",
                    "enum": ["Push A", "Push B", "Pull A", "Pull B", "Swimming", "Football", "Active Recovery", "none"],
                },
                "session_notes": {
                    "type": "string",
                    "description": "Optional opening notes (energy level, how he's feeling, etc.)",
                },
            },
            "required": ["session_type"],
        },
    },
    {
        "name": "log_set",
        "description": (
            "Log an actual set or exercise result to the active workout's Notion page in real-time. "
            "Call this IMMEDIATELY whenever Toan reports finishing a set or exercise — don't batch. "
            "If no active session page exists, call set_active_session first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "exercise": {"type": "string", "description": "Exercise name"},
                "set_number": {"type": "integer", "description": "Which set (1, 2, 3...)"},
                "reps": {"type": "integer", "description": "Reps completed"},
                "weight": {"type": "string", "description": "Weight used, e.g. '40kg' or 'BW'"},
                "notes": {"type": "string", "description": "Optional notes (form, RPE, how it felt)"},
            },
            "required": ["exercise", "reps", "weight"],
        },
    },
    {
        "name": "update_memory",
        "description": (
            "Update long-term memory. Call when you learn something important about Toan — "
            "a new PR, a pattern, a coaching insight, a milestone, an injury flag, measurements, "
            "or current weight. This persists across all future sessions. "
            "Use dot notation for nested keys (e.g. 'personal_records.bench_press_kg'). "
            "For lists (coaching_notes, patterns, milestones, injuries_flags), use "
            "the format: {key: ['append', 'your note here']}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "object",
                    "description": (
                        "Key-value pairs to update. Examples:\n"
                        "- 'personal_records.bench_press_kg': 42.5\n"
                        "- 'personal_records.pull_ups': 10\n"
                        "- 'athlete.current_weight_kg': 68.5\n"
                        "- 'measurements.waist_cm': 77\n"
                        "- 'measurements.chest_cm': 97\n"
                        "- 'current_program_week': 2\n"
                        "- 'coaching_notes': ['append', 'Elbows flare on bench at heavy weight']\n"
                        "- 'patterns': ['append', 'Trains best in the evening']\n"
                        "- 'milestones': ['append', 'First 3x10 pull-ups on 2026-04-06']\n"
                        "- 'injuries_flags': ['append', 'Left shoulder discomfort on dips 2026-04-06']\n"
                        "- 'sleep_notes': 'Moved bedtime to 11:30pm consistently'"
                    ),
                    "additionalProperties": True,
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're updating this memory (for logging).",
                },
            },
            "required": ["updates"],
        },
    },
    {
        "name": "read_notion",
        "description": (
            "Read data from Notion. Use this to look up past workouts, today's meals, "
            "recent measurements, or sleep logs before giving advice. "
            "Always call this when Toan asks about his history or progress, "
            "and before prescribing next session weights (to see what he did last time)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "enum": [
                        "last_session",
                        "recent_workouts",
                        "today_meals",
                        "recent_measurements",
                        "recent_sleep",
                        "all_context",
                    ],
                    "description": (
                        "What to read:\n"
                        "- last_session: most recent workout (any type)\n"
                        "- recent_workouts: last 7 days of workouts\n"
                        "- today_meals: all meals logged today with calorie/protein totals\n"
                        "- recent_measurements: last 4 measurement entries\n"
                        "- recent_sleep: last 7 days of sleep logs\n"
                        "- all_context: everything above in one call"
                    ),
                },
                "session_type": {
                    "type": "string",
                    "description": "Filter recent_workouts by session type, e.g. 'Push A'. Optional.",
                },
            },
            "required": ["query"],
        },
    },
]


# ── Conversation Persistence ──────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                return [m for m in data if isinstance(m.get("content"), str)][-MAX_BUFFER:]
        except Exception:
            return []
    return []


def save_history(buffer):
    try:
        saveable = [m for m in buffer[-MAX_BUFFER:] if isinstance(m.get("content"), str)]
        with open(HISTORY_FILE, "w") as f:
            json.dump(saveable, f)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


conversation_buffer = load_history()


# ── Tool Execution ────────────────────────────────────────────────────

def execute_tool(tool_name, tool_input):
    today = datetime.date.today().isoformat()
    try:
        if tool_name == "log_workout":
            # If active page exists, append a summary block instead of creating a new page
            existing_page_id = active_session.get("notion_page_id")
            if existing_page_id:
                exercises = tool_input.get("exercises", [])
                for ex in exercises:
                    entry = f"{ex['name']}: {ex.get('sets','')}x @ {ex.get('weight','BW')} — {ex.get('reps','')}"
                    if ex.get("notes"):
                        entry += f" ({ex['notes']})"
                    append_actual_entry(existing_page_id, entry)
                notes = tool_input.get("notes", "")
                if notes:
                    append_actual_entry(existing_page_id, f"📝 {notes}")
                logger.info(f"Appended {len(exercises)} exercises to existing page")
                return f"Appended {len(exercises)} exercises to active workout page"
            else:
                page_id = log_workout(
                    date=today,
                    session_type=tool_input["session_type"],
                    exercises=tool_input.get("exercises", []),
                    notes=tool_input.get("notes", ""),
                )
                logger.info(f"Logged workout: {tool_input['session_type']}")
                return f"Workout logged to Notion (ID: {page_id})"

        elif tool_name == "log_meal":
            page_id = log_meal(
                date=today,
                description=tool_input["description"],
                calories=tool_input.get("calories", 0),
                protein=tool_input.get("protein", 0),
                meal_type=tool_input.get("meal_type", "Meal"),
            )
            logger.info(f"Logged meal: {tool_input['description'][:40]}")
            return f"Meal logged to Notion (ID: {page_id})"

        elif tool_name == "log_measurement":
            page_id = log_measurement(
                date=today,
                weight=tool_input.get("weight", 0),
                waist=tool_input.get("waist", 0),
                chest=tool_input.get("chest", 0),
                shoulders=tool_input.get("shoulders", 0),
                arms=tool_input.get("arms", 0),
                notes=tool_input.get("notes", ""),
            )
            logger.info(f"Logged measurements")
            return f"Measurements logged to Notion (ID: {page_id})"

        elif tool_name == "log_sleep":
            page_id = log_sleep(
                date=today,
                bedtime=tool_input.get("bedtime", ""),
                wake_time=tool_input.get("wake_time", ""),
                hours=tool_input.get("hours", 0),
                quality=tool_input.get("quality", ""),
                notes=tool_input.get("notes", ""),
            )
            logger.info(f"Logged sleep")
            return f"Sleep logged to Notion (ID: {page_id})"

        elif tool_name == "set_active_session":
            session_type = tool_input["session_type"]
            if session_type == "none":
                # End session — finalize the Notion page
                page_id = active_session.get("notion_page_id")
                if page_id:
                    done_count = len(active_session["exercises_done"])
                    finish_workout_page(page_id, notes=f"Complete — {done_count} exercise entries logged")
                active_session["type"] = None
                active_session["exercises_done"] = []
                active_session["started_at"] = None
                active_session["notion_page_id"] = None
                return "Session ended and Notion page finalized."
            else:
                # Start session — create Notion page with the plan immediately
                active_session["type"] = session_type
                active_session["exercises_done"] = []
                active_session["started_at"] = datetime.datetime.now().isoformat()
                active_session["notion_page_id"] = None

                planned = SESSION_PLANS.get(session_type, [])
                opening_note = tool_input.get("session_notes", "")
                try:
                    page_id = create_workout_page(
                        date=today,
                        session_type=session_type,
                        planned=planned,
                    )
                    active_session["notion_page_id"] = page_id
                    # Add opening note if provided
                    if opening_note:
                        append_actual_entry(page_id, f"📝 Note: {opening_note}")
                    logger.info(f"Created workout page for {session_type}: {page_id}")
                    return f"Session started: {session_type}. Notion page created with {len(planned)} planned exercises."
                except Exception as e:
                    logger.error(f"Failed to create workout page: {e}")
                    return f"Session started: {session_type} (Notion page creation failed: {e})"

        elif tool_name == "log_set":
            exercise = tool_input["exercise"]
            reps = tool_input["reps"]
            weight = tool_input["weight"]
            set_num = tool_input.get("set_number", "")
            notes = tool_input.get("notes", "")

            # Build the entry text
            set_label = f"Set {set_num}" if set_num else "Set"
            entry = f"{exercise} — {set_label}: {weight} × {reps} reps"
            if notes:
                entry += f"  ({notes})"

            # Track in active session
            active_session["exercises_done"].append(exercise)

            # Append to Notion page in real-time
            page_id = active_session.get("notion_page_id")
            if page_id:
                try:
                    append_actual_entry(page_id, entry)
                    logger.info(f"Logged set: {entry}")
                    return f"Logged: {entry}"
                except Exception as e:
                    logger.error(f"Failed to append set: {e}")
                    return f"Set tracked (Notion append failed: {e})"
            else:
                return f"Set tracked in memory (no active Notion page — call set_active_session first)"

        elif tool_name == "update_memory":
            updates = tool_input.get("updates", {})
            reason = tool_input.get("reason", "")
            update_memory(updates)
            logger.info(f"Memory updated: {list(updates.keys())} — {reason}")
            return f"Memory updated: {list(updates.keys())}"

        elif tool_name == "read_notion":
            query = tool_input["query"]
            session_type = tool_input.get("session_type")
            result = read_notion_query(query, session_type=session_type)
            logger.info(f"Notion read: {query} (session_type={session_type})")
            return result

        return f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return f"Error: {str(e)}"


# ── Main Chat ─────────────────────────────────────────────────────────

def chat(user_message, user_context="", recent_history="",
         image_data=None, image_media_type="image/jpeg"):
    global conversation_buffer

    # Build content
    if image_data:
        import base64
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type,
                    "data": base64.b64encode(image_data).decode("utf-8"),
                },
            },
            {"type": "text", "text": user_message or "Analyze this image."},
        ]
        log_conversation_turn("user", f"[image] {user_message or ''}")
    else:
        content = user_message
        log_conversation_turn("user", user_message)

    conversation_buffer.append({"role": "user", "content": content})

    if len(conversation_buffer) > MAX_BUFFER:
        conversation_buffer = conversation_buffer[-MAX_BUFFER:]

    # Build context: Notion structured data + long-term memory
    memory_context = get_memory_as_context()
    full_context = f"{memory_context}\n\n{user_context}".strip()

    # Add active session to context
    if active_session["type"]:
        full_context += (
            f"\n\n**ACTIVE SESSION:** {active_session['type']} — started {active_session['started_at']}\n"
            f"Exercises done: {', '.join(active_session['exercises_done']) or 'none yet'}\n"
            f"STAY ON THIS SESSION. Do not switch workouts."
        )

    system_prompt = get_system_prompt(full_context, recent_history)

    # Call Claude with tools
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=conversation_buffer,
        tools=TOOLS,
    )

    final_text = ""

    while response.stop_reason == "tool_use":
        assistant_content = response.content
        tool_results = []

        for block in assistant_content:
            if block.type == "text":
                final_text += block.text
            elif block.type == "tool_use":
                result = execute_tool(block.name, block.input)

                if block.name == "log_workout":
                    for ex in block.input.get("exercises", []):
                        active_session["exercises_done"].append(ex.get("name", ""))

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        conversation_buffer.append({"role": "assistant", "content": [
            {"type": "text", "text": b.text} if b.type == "text"
            else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            for b in assistant_content
        ]})
        conversation_buffer.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=conversation_buffer,
            tools=TOOLS,
        )

    for block in response.content:
        if block.type == "text":
            final_text += block.text

    conversation_buffer.append({"role": "assistant", "content": final_text})
    save_history(conversation_buffer)
    log_conversation_turn("assistant", final_text)

    return final_text


def reset_conversation():
    global conversation_buffer, active_session
    conversation_buffer = []
    active_session = {"type": None, "exercises_done": [], "started_at": None, "notion_page_id": None}
    save_history([])
