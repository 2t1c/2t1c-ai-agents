"""
Fitness Coach Telegram Bot — Main entry point.
Handles all Telegram interactions and routes to Claude for coaching.
"""

import logging
import datetime
import pytz
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID, TIMEZONE, \
    MORNING_BRIEFING_HOUR, EVENING_CHECKIN_HOUR, EVENING_CHECKIN_MINUTE
from coach.claude_client import chat, reset_conversation
from storage.notion_client import (
    build_user_context, log_workout, log_meal, log_measurement, log_sleep,
    get_today_nutrition_summary, get_recent_measurements, get_recent_workouts,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)


# ── Auth ──────────────────────────────────────────────────────────────

def authorized(func):
    """Only respond to the configured user."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if TELEGRAM_USER_ID and update.effective_user.id != TELEGRAM_USER_ID:
            await update.message.reply_text("This bot is private.")
            return
        return await func(update, context)
    return wrapper


# ── Command Handlers ──────────────────────────────────────────────────

@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    await update.message.reply_text(
        "Hey Toan! I'm your fitness coach.\n\n"
        "Just talk to me naturally — log workouts, share meals, ask about form, "
        "or check your progress.\n\n"
        "Commands:\n"
        "/today — Today's workout plan\n"
        "/meals — Today's nutrition summary\n"
        "/progress — Recent measurements & trends\n"
        "/form <exercise> — Form cues for an exercise\n"
        "/log — Quick log (workout/meal/sleep)\n"
        "/week — Weekly review\n"
        "/reset — Clear conversation context\n\n"
        "Or just send me a message, photo, or voice note."
    )


@authorized
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get today's workout plan."""
    user_context = build_user_context()
    day_name = datetime.datetime.now(tz).strftime("%A")
    response = chat(
        f"What's my workout for today ({day_name})? Give me the full session plan with "
        f"target weights and reps based on my recent performance.",
        user_context=user_context,
    )
    await update.message.reply_text(response, parse_mode="Markdown")


@authorized
async def cmd_meals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Today's nutrition summary."""
    try:
        summary = get_today_nutrition_summary()
        if summary["meal_count"] == 0:
            await update.message.reply_text(
                "No meals logged today yet. Share what you've eaten!"
            )
            return

        text = (
            f"*Today's Nutrition*\n\n"
            f"Meals: {summary['meal_count']}\n"
            f"Calories: {summary['total_calories']} / ~1800 target\n"
            f"Protein: {summary['total_protein']}g / 135g target\n\n"
        )
        remaining_cal = 1800 - summary["total_calories"]
        remaining_pro = 135 - summary["total_protein"]
        if remaining_cal > 0:
            text += f"Remaining: ~{remaining_cal} cal, ~{remaining_pro}g protein"
        else:
            text += "You've hit your calorie target for today."

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching meals: {e}")
        await update.message.reply_text("Couldn't fetch meals — check Notion DB config.")


@authorized
async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent measurements and progress."""
    user_context = build_user_context()
    response = chat(
        "Show me my progress summary — recent measurements, lift progression, and any trends you see.",
        user_context=user_context,
    )
    await update.message.reply_text(response, parse_mode="Markdown")


@authorized
async def cmd_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Form cues for a specific exercise."""
    exercise = " ".join(context.args) if context.args else ""
    if not exercise:
        await update.message.reply_text("Which exercise? e.g. /form bench press")
        return

    response = chat(
        f"Give me form cues for {exercise}. Key cues only, then common mistakes at my level.",
    )
    await update.message.reply_text(response, parse_mode="Markdown")


@authorized
async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Weekly review."""
    user_context = build_user_context()
    response = chat(
        "Give me my weekly review — summarize this week's training, nutrition, sleep, "
        "measurements, what went well, what to improve, and adjustments for next week.",
        user_context=user_context,
    )
    await update.message.reply_text(response, parse_mode="Markdown")


@authorized
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation buffer."""
    reset_conversation()
    await update.message.reply_text("Conversation context cleared. Fresh start!")


# ── Message Handlers ──────────────────────────────────────────────────

@authorized
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message — route to Claude for natural conversation."""
    user_message = update.message.text
    user_context = build_user_context()

    response = chat(user_message, user_context=user_context)

    # Try Markdown first, fall back to plain text if parsing fails
    try:
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(response)


@authorized
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — meal photos or form check images."""
    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    caption = update.message.caption or "Analyze this image. Is it a meal? Estimate calories and protein. Is it a form check? Give feedback."
    user_context = build_user_context()

    response = chat(
        caption,
        user_context=user_context,
        image_data=bytes(photo_bytes),
        image_media_type="image/jpeg",
    )

    try:
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(response)


@authorized
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video messages — form checks."""
    await update.message.reply_text(
        "Got your video! For now, send me a screenshot of the key position "
        "(bottom of bench, top of pull-up, etc.) and I'll analyze your form.\n\n"
        "Video analysis coming soon."
    )


# ── Scheduled Messages ────────────────────────────────────────────────

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Proactive morning message with today's plan."""
    user_context = build_user_context()
    day_name = datetime.datetime.now(tz).strftime("%A")

    response = chat(
        f"Good morning! Today is {day_name}. Give me my morning briefing: "
        f"what's the plan today, any focus points from recent sessions, "
        f"and a quick motivation note. Keep it short.",
        user_context=user_context,
    )

    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=response,
        parse_mode="Markdown",
    )


async def evening_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Evening wind-down reminder."""
    user_context = build_user_context()

    response = chat(
        "Evening check-in time. Ask me how my day went, remind me about sleep, "
        "and ask if I've logged everything. Be brief — it's wind-down time.",
        user_context=user_context,
    )

    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=response,
        parse_mode="Markdown",
    )


async def weekly_measurement_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Sunday evening measurement reminder."""
    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=(
            "Hey! Weekly check-in time.\n\n"
            "Send me your measurements when you get a chance:\n"
            "- Weight (kg)\n"
            "- Waist (cm)\n"
            "- Chest (cm)\n\n"
            "Same conditions as last time — morning, before eating."
        ),
    )


# ── Main ──────────────────────────────────────────────────────────────

def main():
    """Start the bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("meals", cmd_meals))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("form", cmd_form))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("reset", cmd_reset))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))

    # Scheduled jobs
    job_queue = app.job_queue

    # Morning briefing — daily at configured hour
    job_queue.run_daily(
        morning_briefing,
        time=datetime.time(hour=MORNING_BRIEFING_HOUR, minute=0, tzinfo=tz),
        name="morning_briefing",
    )

    # Evening check-in — daily at 10:30pm
    job_queue.run_daily(
        evening_checkin,
        time=datetime.time(hour=EVENING_CHECKIN_HOUR, minute=EVENING_CHECKIN_MINUTE, tzinfo=tz),
        name="evening_checkin",
    )

    # Weekly measurement reminder — Sunday at 6pm
    job_queue.run_daily(
        weekly_measurement_reminder,
        time=datetime.time(hour=18, minute=0, tzinfo=tz),
        days=(6,),  # Sunday
        name="weekly_measurements",
    )

    # Set bot commands
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("today", "Today's workout plan"),
            BotCommand("meals", "Nutrition summary"),
            BotCommand("progress", "Measurements & trends"),
            BotCommand("form", "Form cues for an exercise"),
            BotCommand("week", "Weekly review"),
            BotCommand("reset", "Clear conversation"),
        ])

    app.post_init = post_init

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
