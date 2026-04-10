"""
Notion storage layer — logs workouts, meals, measurements, and sleep.
Retrieves recent history for Claude context.
"""

import datetime
from notion_client import Client
from config import (
    NOTION_API_KEY, NOTION_WORKOUTS_DB, NOTION_MEALS_DB,
    NOTION_MEASUREMENTS_DB, NOTION_SLEEP_DB,
)

notion = Client(auth=NOTION_API_KEY)


# ── Workouts ──────────────────────────────────────────────────────────

def create_workout_page(date: str, session_type: str, planned: list[dict]) -> str:
    """
    Create a workout page at session START with the full planned exercises.
    Returns the page_id to be used for real-time actual logging.

    planned: [{"name": "Bench Press", "sets": "3 (RPT)", "target": "40kg x5 / 36kg x6-8 / 32kg x8-10"}]
    """
    # Build planned section blocks
    planned_lines = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📋 Planned"}}]},
        }
    ]
    for ex in planned:
        line = f"{ex['name']}"
        if ex.get("sets"):
            line += f"  —  {ex['sets']}"
        if ex.get("target"):
            line += f"  →  {ex['target']}"
        planned_lines.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": line}}]
            },
        })

    # Actual section header (entries appended below during session)
    actual_header = [
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "✅ Actual"}}]},
        },
    ]

    page = notion.pages.create(
        parent={"database_id": NOTION_WORKOUTS_DB},
        properties={
            "Name": {"title": [{"text": {"content": f"{session_type} — {date}"}}]},
            "Date": {"date": {"start": date}},
            "Session Type": {"select": {"name": session_type}},
            "Notes": {"rich_text": [{"text": {"content": "In progress..."}}]},
        },
        children=planned_lines + actual_header,
    )
    return page["id"]


def append_actual_entry(page_id: str, text: str) -> None:
    """
    Append one actual set/exercise entry to an existing workout page.
    Called in real-time as Toan reports each set during the session.
    """
    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            }
        ],
    )


def finish_workout_page(page_id: str, notes: str = "") -> None:
    """Update the Notes field when the session is complete."""
    notion.pages.update(
        page_id=page_id,
        properties={
            "Notes": {"rich_text": [{"text": {"content": notes or "Complete"}}]},
        },
    )


def log_workout(date: str, session_type: str, exercises: list[dict], notes: str = "") -> str:
    """
    Fallback: log a full workout in one shot (used when no active page exists).
    exercises: [{"name": "Bench Press", "sets": "3", "reps": "5,7,9", "weight": "40kg"}]
    """
    exercise_text = "\n".join(
        f"- {e['name']}: {e.get('sets', '')}x @ {e.get('weight', 'BW')} — reps: {e.get('reps', '')}"
        + (f" ({e['notes']})" if e.get('notes') else "")
        for e in exercises
    )
    page = notion.pages.create(
        parent={"database_id": NOTION_WORKOUTS_DB},
        properties={
            "Name": {"title": [{"text": {"content": f"{session_type} — {date}"}}]},
            "Date": {"date": {"start": date}},
            "Session Type": {"select": {"name": session_type}},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": exercise_text}}]},
            }
        ],
    )
    return page["id"]


def get_recent_workouts(days: int = 7, session_type: str = None) -> list[dict]:
    """Get workouts from the last N days, optionally filtered by session type."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    db_filter = {"property": "Date", "date": {"on_or_after": since}}
    if session_type:
        db_filter = {
            "and": [
                db_filter,
                {"property": "Session Type", "select": {"equals": session_type}},
            ]
        }

    results = notion.databases.query(
        database_id=NOTION_WORKOUTS_DB,
        filter=db_filter,
        sorts=[{"property": "Date", "direction": "descending"}],
    )

    workouts = []
    for page in results.get("results", []):
        props = page["properties"]
        title = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else ""
        date = props["Date"]["date"]["start"] if props["Date"]["date"] else ""
        session_type = props["Session Type"]["select"]["name"] if props["Session Type"].get("select") else ""
        notes = props["Notes"]["rich_text"][0]["text"]["content"] if props["Notes"]["rich_text"] else ""

        # Get exercise details from page content
        blocks = notion.blocks.children.list(block_id=page["id"])
        content = ""
        for block in blocks.get("results", []):
            if block["type"] == "paragraph" and block["paragraph"]["rich_text"]:
                content += block["paragraph"]["rich_text"][0]["text"]["content"]

        workouts.append({
            "date": date,
            "session_type": session_type,
            "title": title,
            "notes": notes,
            "exercises": content,
        })

    return workouts


# ── Meals ─────────────────────────────────────────────────────────────

def log_meal(date: str, description: str, calories: int = 0, protein: int = 0,
             meal_type: str = "Meal") -> str:
    """Log a meal entry."""
    page = notion.pages.create(
        parent={"database_id": NOTION_MEALS_DB},
        properties={
            "Name": {"title": [{"text": {"content": f"{meal_type} — {date}"}}]},
            "Date": {"date": {"start": date}},
            "Type": {"select": {"name": meal_type}},
            "Calories": {"number": calories},
            "Protein (g)": {"number": protein},
            "Description": {"rich_text": [{"text": {"content": description}}]},
        },
    )
    return page["id"]


def get_today_meals() -> list[dict]:
    """Get all meals logged today."""
    today = datetime.date.today().isoformat()

    results = notion.databases.query(
        database_id=NOTION_MEALS_DB,
        filter={
            "property": "Date",
            "date": {"equals": today},
        },
        sorts=[{"property": "Date", "direction": "ascending"}],
    )

    meals = []
    for page in results.get("results", []):
        props = page["properties"]
        meals.append({
            "type": props["Type"]["select"]["name"] if props["Type"].get("select") else "",
            "calories": props["Calories"]["number"] or 0,
            "protein": props["Protein (g)"]["number"] or 0,
            "description": props["Description"]["rich_text"][0]["text"]["content"] if props["Description"]["rich_text"] else "",
        })

    return meals


def get_today_nutrition_summary() -> dict:
    """Get total calories and protein for today."""
    meals = get_today_meals()
    return {
        "total_calories": sum(m["calories"] for m in meals),
        "total_protein": sum(m["protein"] for m in meals),
        "meal_count": len(meals),
        "meals": meals,
    }


# ── Measurements ──────────────────────────────────────────────────────

def log_measurement(date: str, weight: float = 0, waist: float = 0, chest: float = 0,
                    shoulders: float = 0, arms: float = 0, notes: str = "") -> str:
    """Log body measurements."""
    page = notion.pages.create(
        parent={"database_id": NOTION_MEASUREMENTS_DB},
        properties={
            "Name": {"title": [{"text": {"content": f"Measurements — {date}"}}]},
            "Date": {"date": {"start": date}},
            "Weight (kg)": {"number": weight or None},
            "Waist (cm)": {"number": waist or None},
            "Chest (cm)": {"number": chest or None},
            "Shoulders (cm)": {"number": shoulders or None},
            "Arms (cm)": {"number": arms or None},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        },
    )
    return page["id"]


def get_recent_measurements(count: int = 4) -> list[dict]:
    """Get the last N measurement entries."""
    results = notion.databases.query(
        database_id=NOTION_MEASUREMENTS_DB,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=count,
    )

    measurements = []
    for page in results.get("results", []):
        props = page["properties"]
        measurements.append({
            "date": props["Date"]["date"]["start"] if props["Date"]["date"] else "",
            "weight": props["Weight (kg)"]["number"],
            "waist": props["Waist (cm)"]["number"],
            "chest": props["Chest (cm)"]["number"],
            "shoulders": props["Shoulders (cm)"]["number"],
            "arms": props["Arms (cm)"]["number"],
        })

    return measurements


# ── Sleep ─────────────────────────────────────────────────────────────

def log_sleep(date: str, bedtime: str = "", wake_time: str = "", hours: float = 0,
              quality: str = "", notes: str = "") -> str:
    """Log sleep data."""
    page = notion.pages.create(
        parent={"database_id": NOTION_SLEEP_DB},
        properties={
            "Name": {"title": [{"text": {"content": f"Sleep — {date}"}}]},
            "Date": {"date": {"start": date}},
            "Bedtime": {"rich_text": [{"text": {"content": bedtime}}]},
            "Wake Time": {"rich_text": [{"text": {"content": wake_time}}]},
            "Hours": {"number": hours or None},
            "Quality": {"select": {"name": quality}} if quality else {"select": None},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        },
    )
    return page["id"]


def get_recent_sleep(days: int = 7) -> list[dict]:
    """Get sleep data from the last N days."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    results = notion.databases.query(
        database_id=NOTION_SLEEP_DB,
        filter={
            "property": "Date",
            "date": {"on_or_after": since},
        },
        sorts=[{"property": "Date", "direction": "descending"}],
    )

    sleep_data = []
    for page in results.get("results", []):
        props = page["properties"]
        sleep_data.append({
            "date": props["Date"]["date"]["start"] if props["Date"]["date"] else "",
            "hours": props["Hours"]["number"],
            "quality": props["Quality"]["select"]["name"] if props["Quality"].get("select") else "",
            "bedtime": props["Bedtime"]["rich_text"][0]["text"]["content"] if props["Bedtime"]["rich_text"] else "",
        })

    return sleep_data


# ── On-demand Notion Reader ───────────────────────────────────────────

def get_last_session(session_type: str = None) -> dict:
    """Get the single most recent workout, optionally filtered by session type."""
    db_filter = None
    if session_type:
        db_filter = {"property": "Session Type", "select": {"equals": session_type}}

    results = notion.databases.query(
        database_id=NOTION_WORKOUTS_DB,
        filter=db_filter,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=1,
    )
    pages = results.get("results", [])
    if not pages:
        return {}

    page = pages[0]
    props = page["properties"]
    date = props["Date"]["date"]["start"] if props["Date"]["date"] else ""
    stype = props["Session Type"]["select"]["name"] if props["Session Type"].get("select") else ""
    notes = props["Notes"]["rich_text"][0]["text"]["content"] if props["Notes"]["rich_text"] else ""

    blocks = notion.blocks.children.list(block_id=page["id"])
    content_lines = []
    for block in blocks.get("results", []):
        btype = block["type"]
        rich = block.get(btype, {}).get("rich_text", [])
        if rich:
            content_lines.append(rich[0]["text"]["content"])

    return {
        "date": date,
        "session_type": stype,
        "notes": notes,
        "content": "\n".join(content_lines),
    }


def read_notion_query(query: str, session_type: str = None) -> str:
    """Execute a read query and return formatted text for Claude."""
    try:
        if query == "last_session":
            w = get_last_session(session_type)
            if not w:
                return "No workouts found in Notion."
            return (
                f"**Last session** ({w['session_type']} — {w['date']})\n"
                f"{w['content']}\n"
                f"Notes: {w['notes']}"
            )

        elif query == "recent_workouts":
            workouts = get_recent_workouts(14, session_type=session_type)
            if not workouts:
                return "No workouts in the last 14 days."
            lines = [f"**Recent workouts (last 14 days):**"]
            for w in workouts:
                lines.append(f"\n{w['session_type']} — {w['date']}")
                if w["exercises"]:
                    lines.append(w["exercises"])
            return "\n".join(lines)

        elif query == "today_meals":
            s = get_today_nutrition_summary()
            if s["meal_count"] == 0:
                return "No meals logged today yet."
            lines = [f"**Today's nutrition:** {s['meal_count']} meals"]
            lines.append(f"Calories: {s['total_calories']} / 1800 target")
            lines.append(f"Protein: {s['total_protein']}g / 135g target")
            for m in s["meals"]:
                lines.append(f"  • {m['type']}: {m['description']} — {m['calories']} cal, {m['protein']}g protein")
            return "\n".join(lines)

        elif query == "recent_measurements":
            measurements = get_recent_measurements(4)
            if not measurements:
                return "No measurements logged yet."
            lines = ["**Recent measurements:**"]
            for m in measurements:
                parts = [m["date"]]
                if m["weight"]: parts.append(f"Weight {m['weight']}kg")
                if m["waist"]:  parts.append(f"Waist {m['waist']}cm")
                if m["chest"]:  parts.append(f"Chest {m['chest']}cm")
                if m["shoulders"]: parts.append(f"Shoulders {m['shoulders']}cm")
                if m["arms"]:   parts.append(f"Arms {m['arms']}cm")
                lines.append("  • " + " | ".join(parts))
            return "\n".join(lines)

        elif query == "recent_sleep":
            sleep = get_recent_sleep(7)
            if not sleep:
                return "No sleep logs found."
            lines = ["**Recent sleep (last 7 days):**"]
            for s in sleep:
                parts = [s["date"]]
                if s["hours"]:   parts.append(f"{s['hours']}h")
                if s["bedtime"]: parts.append(f"bed {s['bedtime']}")
                if s["quality"]: parts.append(s["quality"])
                lines.append("  • " + " | ".join(parts))
            return "\n".join(lines)

        elif query == "all_context":
            parts = []
            for q in ["recent_workouts", "today_meals", "recent_measurements", "recent_sleep"]:
                result = read_notion_query(q)
                parts.append(result)
            return "\n\n".join(parts)

        return f"Unknown query: {query}"

    except Exception as e:
        return f"Notion read error ({query}): {str(e)}"


# ── Context Builder ───────────────────────────────────────────────────

def build_user_context() -> str:
    """Build a context string from recent Notion data for the system prompt."""
    sections = []

    try:
        workouts = get_recent_workouts(7)
        if workouts:
            lines = ["## Recent Workouts (Last 7 Days)"]
            for w in workouts:
                lines.append(f"**{w['date']} — {w['session_type']}**")
                if w["exercises"]:
                    lines.append(w["exercises"])
                if w["notes"]:
                    lines.append(f"Notes: {w['notes']}")
            sections.append("\n".join(lines))
    except Exception:
        pass

    try:
        nutrition = get_today_nutrition_summary()
        if nutrition["meal_count"] > 0:
            sections.append(
                f"## Today's Nutrition\n"
                f"Meals logged: {nutrition['meal_count']}\n"
                f"Total calories: {nutrition['total_calories']}\n"
                f"Total protein: {nutrition['total_protein']}g"
            )
    except Exception:
        pass

    try:
        measurements = get_recent_measurements(4)
        if measurements:
            lines = ["## Recent Measurements"]
            for m in measurements:
                parts = [f"**{m['date']}**:"]
                if m["weight"]: parts.append(f"Weight {m['weight']}kg")
                if m["waist"]: parts.append(f"Waist {m['waist']}cm")
                if m["chest"]: parts.append(f"Chest {m['chest']}cm")
                lines.append(" | ".join(parts))
            sections.append("\n".join(lines))
    except Exception:
        pass

    try:
        sleep = get_recent_sleep(7)
        if sleep:
            lines = ["## Recent Sleep"]
            for s in sleep:
                parts = [f"**{s['date']}**:"]
                if s["hours"]: parts.append(f"{s['hours']}h")
                if s["bedtime"]: parts.append(f"bed at {s['bedtime']}")
                if s["quality"]: parts.append(f"({s['quality']})")
                lines.append(" ".join(parts))
            sections.append("\n".join(lines))
    except Exception:
        pass

    return "\n\n".join(sections) if sections else ""
