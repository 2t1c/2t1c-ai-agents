"""
Creates the 4 Notion databases needed for the fitness coach bot.
Run once: python setup_notion.py

Requires NOTION_API_KEY in .env and a parent page ID.
"""

import os
import sys
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
# Put databases under AI & Agents page
PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE", "32e04fca-1794-8117-93e7-e8f3d8d66f53")

if not NOTION_API_KEY:
    print("Set NOTION_API_KEY in .env first")
    sys.exit(1)

notion = Client(auth=NOTION_API_KEY)


def create_workouts_db():
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        title=[{"type": "text", "text": {"content": "Fitness — Workouts"}}],
        icon={"type": "emoji", "emoji": "🏋️"},
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Session Type": {
                "select": {
                    "options": [
                        {"name": "Push A", "color": "red"},
                        {"name": "Push B", "color": "orange"},
                        {"name": "Pull A", "color": "blue"},
                        {"name": "Pull B", "color": "purple"},
                        {"name": "Swimming", "color": "green"},
                        {"name": "Football", "color": "yellow"},
                        {"name": "Active Recovery", "color": "gray"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
        },
    )
    print(f"Workouts DB: {db['id']}")
    return db["id"]


def create_meals_db():
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        title=[{"type": "text", "text": {"content": "Fitness — Meals"}}],
        icon={"type": "emoji", "emoji": "🍽️"},
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "Breakfast", "color": "yellow"},
                        {"name": "Lunch", "color": "orange"},
                        {"name": "Dinner", "color": "red"},
                        {"name": "Snack", "color": "green"},
                        {"name": "Pre-workout", "color": "blue"},
                        {"name": "Post-workout", "color": "purple"},
                    ]
                }
            },
            "Calories": {"number": {"format": "number"}},
            "Protein (g)": {"number": {"format": "number"}},
            "Description": {"rich_text": {}},
        },
    )
    print(f"Meals DB: {db['id']}")
    return db["id"]


def create_measurements_db():
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        title=[{"type": "text", "text": {"content": "Fitness — Measurements"}}],
        icon={"type": "emoji", "emoji": "📏"},
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Weight (kg)": {"number": {"format": "number"}},
            "Waist (cm)": {"number": {"format": "number"}},
            "Chest (cm)": {"number": {"format": "number"}},
            "Shoulders (cm)": {"number": {"format": "number"}},
            "Arms (cm)": {"number": {"format": "number"}},
            "Notes": {"rich_text": {}},
        },
    )
    print(f"Measurements DB: {db['id']}")
    return db["id"]


def create_sleep_db():
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        title=[{"type": "text", "text": {"content": "Fitness — Sleep"}}],
        icon={"type": "emoji", "emoji": "😴"},
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Bedtime": {"rich_text": {}},
            "Wake Time": {"rich_text": {}},
            "Hours": {"number": {"format": "number"}},
            "Quality": {
                "select": {
                    "options": [
                        {"name": "Great", "color": "green"},
                        {"name": "Good", "color": "blue"},
                        {"name": "OK", "color": "yellow"},
                        {"name": "Poor", "color": "orange"},
                        {"name": "Terrible", "color": "red"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
        },
    )
    print(f"Sleep DB: {db['id']}")
    return db["id"]


if __name__ == "__main__":
    print("Creating Notion databases for Fitness Coach Bot...\n")

    workouts_id = create_workouts_db()
    meals_id = create_meals_db()
    measurements_id = create_measurements_db()
    sleep_id = create_sleep_db()

    print(f"\nDone! Add these to your .env file:\n")
    print(f"NOTION_WORKOUTS_DB={workouts_id}")
    print(f"NOTION_MEALS_DB={meals_id}")
    print(f"NOTION_MEASUREMENTS_DB={measurements_id}")
    print(f"NOTION_SLEEP_DB={sleep_id}")
