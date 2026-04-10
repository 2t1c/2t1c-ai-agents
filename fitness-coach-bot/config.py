"""
Configuration — loads from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))

# Claude API
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Notion
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_WORKOUTS_DB = os.getenv("NOTION_WORKOUTS_DB", "")
NOTION_MEALS_DB = os.getenv("NOTION_MEALS_DB", "")
NOTION_MEASUREMENTS_DB = os.getenv("NOTION_MEASUREMENTS_DB", "")
NOTION_SLEEP_DB = os.getenv("NOTION_SLEEP_DB", "")

# Timezone
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

# Scheduler
MORNING_BRIEFING_HOUR = int(os.getenv("MORNING_BRIEFING_HOUR", "7"))
EVENING_CHECKIN_HOUR = int(os.getenv("EVENING_CHECKIN_HOUR", "22"))
EVENING_CHECKIN_MINUTE = int(os.getenv("EVENING_CHECKIN_MINUTE", "30"))
