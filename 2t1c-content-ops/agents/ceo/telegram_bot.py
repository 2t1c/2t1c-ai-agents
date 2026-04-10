"""
CEO Telegram Bot — Toản's strategic co-pilot for GeniusGTX.

Talk to this bot on Telegram to steer the content machine.
It connects to Claude with tool use for reading/writing Notion.
Supports text, voice messages, and proactive daily briefings.

Usage:
    python -m agents.ceo.telegram_bot
"""

from __future__ import annotations

import logging
import os
import random
import re
import sys
import tempfile
from datetime import time
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from agents.ceo.agent import chat

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ceo-bot")

BOT_TOKEN = os.getenv("TELEGRAM_CEO_BOT_TOKEN")
AUTHORIZED_CHAT_ID = os.getenv("TELEGRAM_CEO_CHAT_ID")

# Conversation history per chat — persists for the session
conversation_history: dict[int, list] = {}

# Cap history to avoid token bloat
MAX_HISTORY_TURNS = 30

# Thinking messages — rotated randomly
THINKING_MESSAGES = [
    "On it...",
    "Pulling the data...",
    "Checking Notion...",
    "Let me look into that...",
    "Working on it...",
    "One sec...",
]

VOICE_THINKING_MESSAGES = [
    "Got your voice note, processing...",
    "Heard you, thinking...",
    "Transcribing and processing...",
]


# ── Voice Transcription ────────────────────────────────────────────────────

def transcribe_voice(file_path: str) -> str:
    """Transcribe a voice message using OpenAI Whisper API."""
    from openai import OpenAI

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    # If no OpenAI key, fall back to Anthropic-compatible transcription
    if not os.getenv("OPENAI_API_KEY"):
        # Use Telegram's built-in voice duration as fallback indicator
        return None

    with open(file_path, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )
    return transcript.text


# ── Markdown → Telegram HTML ───────────────────────────────────────────────

def md_to_html(text: str) -> str:
    """Convert Claude's markdown output to Telegram-compatible HTML."""
    lines = text.split("\n")
    result = []
    table_buffer = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            if not in_table:
                in_table = True
                table_buffer = []
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            table_buffer.append(stripped)
        else:
            if in_table:
                result.append(_format_table(table_buffer))
                table_buffer = []
                in_table = False
            result.append(line)

    if in_table:
        result.append(_format_table(table_buffer))

    text = "\n".join(result)

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!</b>)\*(.+?)\*(?!<)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"^#{1,3}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", "━━━━━━━━━━━━━━━", text, flags=re.MULTILINE)

    return text


def _format_table(rows: list[str]) -> str:
    if not rows:
        return ""
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        parsed.append(cells)
    if not parsed:
        return ""
    num_cols = max(len(row) for row in parsed)
    col_widths = [0] * num_cols
    for row in parsed:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))
    formatted = []
    for idx, row in enumerate(parsed):
        parts = []
        for i in range(num_cols):
            cell = row[i] if i < len(row) else ""
            parts.append(cell.ljust(col_widths[i]))
        formatted.append("  ".join(parts))
        if idx == 0:
            formatted.append("  ".join("─" * w for w in col_widths))
    return "<pre>" + "\n".join(formatted) + "</pre>"


# ── Message Sending Helper ─────────────────────────────────────────────────

async def send_response(update: Update, response_text: str):
    """Send a response with HTML formatting, splitting if needed."""
    html_text = md_to_html(response_text)

    if len(html_text) <= 4096:
        try:
            await update.message.reply_text(html_text, parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text(response_text)
    else:
        chunks = _split_message(html_text, 4096)
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(chunk)


async def process_and_respond(update: Update, user_message: str):
    """Core processing: send thinking msg, call Claude, respond."""
    chat_id = update.effective_chat.id
    history = conversation_history.get(chat_id, [])

    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-(MAX_HISTORY_TURNS * 2):]

    thinking_msg = await update.message.reply_text(
        random.choice(THINKING_MESSAGES)
    )

    try:
        response_text, updated_history = chat(user_message, history)
        conversation_history[chat_id] = updated_history
        await thinking_msg.delete()
        await send_response(update, response_text)
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"Something went wrong: {str(e)[:200]}")


# ── Handlers ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "CEO bot online. Full access to Notion, Typefully analytics, and pipeline commands.\n\n"
        "Text or voice message me anything — strategy, ideas, pipeline checks, guideline updates.\n\n"
        "/reset — clear conversation\n"
        "/briefing — get today's briefing now"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    await update.message.reply_text("History cleared. Fresh start.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    chat_id = update.effective_chat.id

    if AUTHORIZED_CHAT_ID and str(chat_id) != str(AUTHORIZED_CHAT_ID):
        await update.message.reply_text("Unauthorized.")
        return

    await process_and_respond(update, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages — transcribe then process."""
    chat_id = update.effective_chat.id

    if AUTHORIZED_CHAT_ID and str(chat_id) != str(AUTHORIZED_CHAT_ID):
        await update.message.reply_text("Unauthorized.")
        return

    # Acknowledge receipt immediately
    thinking_msg = await update.message.reply_text(
        random.choice(VOICE_THINKING_MESSAGES)
    )

    try:
        # Download voice file
        voice = update.message.voice or update.message.audio
        if not voice:
            await thinking_msg.edit_text("Couldn't process that audio.")
            return

        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Transcribe
        transcript = transcribe_voice(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        if not transcript:
            await thinking_msg.edit_text(
                "Voice transcription requires an OpenAI API key. "
                "Add OPENAI_API_KEY to your .env file."
            )
            return

        # Show what was transcribed
        await thinking_msg.edit_text(f"🎤 \"{transcript}\"\n\nProcessing...")

        # Get conversation history
        history = conversation_history.get(chat_id, [])
        if len(history) > MAX_HISTORY_TURNS * 2:
            history = history[-(MAX_HISTORY_TURNS * 2):]

        # Process through Claude
        response_text, updated_history = chat(transcript, history)
        conversation_history[chat_id] = updated_history

        await thinking_msg.delete()
        await send_response(update, response_text)

    except Exception as e:
        logger.error(f"Voice processing error: {e}", exc_info=True)
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"Voice processing failed: {str(e)[:200]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos — analyze screenshots of tweets/posts."""
    chat_id = update.effective_chat.id

    if AUTHORIZED_CHAT_ID and str(chat_id) != str(AUTHORIZED_CHAT_ID):
        await update.message.reply_text("Unauthorized.")
        return

    thinking_msg = await update.message.reply_text("Analyzing the image...")

    try:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Get caption as instruction if provided
        caption = update.message.caption or "Analyze this content. What makes it work? Propose a GeniusGTX angle."

        # Get conversation history
        history = conversation_history.get(chat_id, [])
        if len(history) > MAX_HISTORY_TURNS * 2:
            history = history[-(MAX_HISTORY_TURNS * 2):]

        # Process through Claude — tell it to use the analyze_image tool
        message = f"I'm sending you a screenshot. The image is saved at {tmp_path}. Use the analyze_image tool with that path. Instruction: {caption}"
        response_text, updated_history = chat(message, history)
        conversation_history[chat_id] = updated_history

        # Clean up
        os.unlink(tmp_path)

        await thinking_msg.delete()
        await send_response(update, response_text)

    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"Image analysis failed: {str(e)[:200]}")


# ── Daily Briefing ─────────────────────────────────────────────────────────

async def send_daily_briefing(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Proactive daily briefing — sent every morning."""
    if not AUTHORIZED_CHAT_ID:
        return

    logger.info("Generating daily briefing...")

    try:
        briefing_prompt = (
            "Generate my morning briefing. Use tools to get real data:\n"
            "1. Check pipeline health (pipeline_summary)\n"
            "2. Pull last 7 days of analytics (get_analytics)\n"
            "3. Check any saved memories for context (recall_memories)\n"
            "4. Check experiments awaiting review (get_experiments with status 'Awaiting Review')\n"
            "5. Run analyze_performance for pattern insights\n\n"
            "Format as a concise morning brief:\n"
            "- Top performing post from last 7 days\n"
            "- Key numbers (impressions trend, engagement)\n"
            "- Pipeline status (anything stuck or needing attention?)\n"
            "- Experiment updates (any A/B tests waiting for my review?)\n"
            "- One insight or suggestion (e.g. 'Your number hooks outperform questions 3:1 — want to test more?')\n\n"
            "End with a suggested A/B test based on the data. Keep it short — I'm reading this on my phone over coffee."
        )

        response_text, _ = chat(briefing_prompt)
        html_text = md_to_html(response_text)

        if len(html_text) <= 4096:
            try:
                await context.bot.send_message(
                    chat_id=AUTHORIZED_CHAT_ID,
                    text=f"☀️ <b>Morning Briefing</b>\n\n{html_text}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=AUTHORIZED_CHAT_ID,
                    text=f"Morning Briefing\n\n{response_text}",
                )
        else:
            chunks = _split_message(html_text, 4000)
            for i, chunk in enumerate(chunks):
                prefix = "☀️ <b>Morning Briefing</b>\n\n" if i == 0 else ""
                try:
                    await context.bot.send_message(
                        chat_id=AUTHORIZED_CHAT_ID,
                        text=f"{prefix}{chunk}",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id=AUTHORIZED_CHAT_ID, text=chunk,
                    )

        logger.info("Daily briefing sent.")

    except Exception as e:
        logger.error(f"Daily briefing failed: {e}", exc_info=True)


async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /briefing command — send briefing on demand."""
    await send_daily_briefing(context)


# ── Habits Reminders ───────────────────────────────────────────────────────

async def send_morning_habits(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Morning non-negotiables reminder."""
    if not AUTHORIZED_CHAT_ID:
        return
    try:
        from agents.ceo.habits import format_morning_reminder
        text = format_morning_reminder()
        await context.bot.send_message(
            chat_id=AUTHORIZED_CHAT_ID,
            text=f"<b>Daily Non-Negotiables</b>\n\n<pre>{text}</pre>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Morning habits reminder sent.")
    except Exception as e:
        logger.error(f"Morning habits failed: {e}", exc_info=True)


async def send_midday_checkin(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mid-day habits check-in."""
    if not AUTHORIZED_CHAT_ID:
        return
    try:
        from agents.ceo.habits import format_midday_checkin
        text = format_midday_checkin()
        await context.bot.send_message(
            chat_id=AUTHORIZED_CHAT_ID,
            text=f"<b>Mid-Day Check</b>\n\n<pre>{text}</pre>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Midday check-in sent.")
    except Exception as e:
        logger.error(f"Midday check-in failed: {e}", exc_info=True)


async def send_evening_scorecard(context: ContextTypes.DEFAULT_TYPE) -> None:
    """End-of-day scorecard."""
    if not AUTHORIZED_CHAT_ID:
        return
    try:
        from agents.ceo.habits import format_evening_scorecard
        text = format_evening_scorecard()
        await context.bot.send_message(
            chat_id=AUTHORIZED_CHAT_ID,
            text=f"<b>End of Day</b>\n\n<pre>{text}</pre>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Evening scorecard sent.")
    except Exception as e:
        logger.error(f"Evening scorecard failed: {e}", exc_info=True)


async def send_weekly_habits(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sunday weekly habits summary."""
    if not AUTHORIZED_CHAT_ID:
        return
    try:
        from agents.ceo.habits import format_weekly_summary
        text = format_weekly_summary()
        await context.bot.send_message(
            chat_id=AUTHORIZED_CHAT_ID,
            text=f"<b>Weekly Habits Review</b>\n\n<pre>{text}</pre>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Weekly habits summary sent.")
    except Exception as e:
        logger.error(f"Weekly habits failed: {e}", exc_info=True)


async def habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /habits command — show today's status."""
    try:
        from agents.ceo.habits import format_midday_checkin
        text = format_midday_checkin()
        await update.message.reply_text(
            f"<pre>{text}</pre>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


# ── Utilities ──────────────────────────────────────────────────────────────

def _split_message(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current += ("\n\n" if current else "") + paragraph
    if current.strip():
        chunks.append(current.strip())
    return chunks


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_CEO_BOT_TOKEN not set in .env")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("habits", habits_command))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Schedule daily briefing at 8am local (Asia/Saigon = UTC+7, so 1am UTC)
    job_queue = app.job_queue
    if job_queue:
        # Daily briefing: 8:03am Asia/Saigon (01:03 UTC)
        job_queue.run_daily(
            send_daily_briefing,
            time=time(hour=1, minute=3),
            name="daily_briefing",
        )

        # Morning habits: 7:30am Asia/Saigon (00:30 UTC)
        job_queue.run_daily(
            send_morning_habits,
            time=time(hour=0, minute=30),
            name="morning_habits",
        )

        # Mid-day check-in: 2pm Asia/Saigon (07:00 UTC)
        job_queue.run_daily(
            send_midday_checkin,
            time=time(hour=7, minute=0),
            name="midday_checkin",
        )

        # Evening scorecard: 9:30pm Asia/Saigon (14:30 UTC)
        job_queue.run_daily(
            send_evening_scorecard,
            time=time(hour=14, minute=30),
            name="evening_scorecard",
        )

        # Weekly summary: Sunday 8pm Asia/Saigon (13:00 UTC)
        job_queue.run_daily(
            send_weekly_habits,
            time=time(hour=13, minute=0),
            days=(6,),  # Sunday
            name="weekly_habits",
        )

        logger.info("Scheduled: briefing 8:03am, habits 7:30am, check-in 2pm, scorecard 9:30pm, weekly Sun 8pm")

    logger.info("CEO bot starting — text, voice, habits, and daily briefing enabled")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
