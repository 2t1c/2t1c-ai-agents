"""
Telegram Review Bot — Push-notification review flow for GeniusGTX content.

Polls Notion for "Ready for Review" drafts, sends them to Telegram with
Approve/Reject inline buttons. On reject, collects feedback, triggers
a rewrite via Maya, creates a new Typefully draft, and re-sends for review.

Setup:
    1. Create a bot via @BotFather on Telegram → copy the token
    2. Message your bot once so it can find your chat ID
    3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
    4. Run: python -m tools.telegram_review_bot

Usage:
    python -m tools.telegram_review_bot               # start the bot
    python -m tools.telegram_review_bot --poll-only    # just poll + send, no button handler
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tools.notion_client import (
    get_ready_for_review_ideas,
    get_ready_for_review_library,
    update_idea_status,
    update_longform_post,
    save_review_feedback,
    save_typefully_draft_id,
)
from tools.typefully_client import (
    get_draft,
    create_draft,
    edit_draft_text,
    add_tag_to_draft,
    enable_sharing,
)
from agents.maya.agent import revise_post

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("review-bot")

# ── Config ──────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
POLL_INTERVAL = 300  # 5 minutes
MAX_BATCH_SIZE = 5  # Max reviews to send per poll cycle (avoid overwhelming)

# Track which Notion page IDs we've already sent to avoid duplicate messages
# Persisted to disk so restarts don't re-send old drafts
_SENT_IDS_PATH = PROJECT_ROOT / ".sent_review_ids.json"


def _load_sent_ids() -> set[str]:
    """Load sent IDs from disk."""
    if _SENT_IDS_PATH.exists():
        try:
            import json as _json
            return set(_json.loads(_SENT_IDS_PATH.read_text()))
        except Exception:
            return set()
    return set()


def _save_sent_ids():
    """Persist sent IDs to disk."""
    try:
        import json as _json
        _SENT_IDS_PATH.write_text(_json.dumps(list(_sent_ids)))
    except Exception as e:
        logger.warning(f"Could not save sent IDs: {e}")


_sent_ids: set[str] = _load_sent_ids()

# Store pending reject states: chat_id -> {notion_id, source, draft_id, timestamp, ...}
# Entries expire after FEEDBACK_TIMEOUT_SECONDS
_pending_feedback: dict[int, dict] = {}
FEEDBACK_TIMEOUT_SECONDS = 600  # 10 minutes


# ── Helpers ─────────────────────────────────────────────────────────────────

TYPEFULLY_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))


def _get_share_link(draft_id: str) -> str:
    """Enable sharing on a draft and return the public share URL."""
    if not draft_id:
        return "(no draft)"
    try:
        share_url = enable_sharing(draft_id)
        if share_url:
            return share_url
    except Exception as e:
        logger.warning(f"Could not enable sharing for draft {draft_id}: {e}")
    # Fallback to private URL if sharing fails
    return f"https://typefully.com/?d={draft_id}&a={TYPEFULLY_SOCIAL_SET_ID}"


def _extract_text_from_draft(draft: dict) -> str:
    """Extract the full post text from a Typefully draft dict."""
    platforms = draft.get("platforms", {})
    x_data = platforms.get("x", {})
    posts = x_data.get("posts", [])
    if posts:
        return "\n\n---\n\n".join(p.get("text", "") for p in posts)
    return draft.get("preview", draft.get("content", ""))


def _get_draft_preview(draft_id: str) -> str:
    """Fetch the first 280 chars of a Typefully draft for the review message."""
    if not draft_id:
        return ""
    try:
        draft = get_draft(draft_id)
        return _extract_text_from_draft(draft)[:280]
    except Exception as e:
        logger.warning(f"Could not fetch draft preview {draft_id}: {e}")
        return ""


def _get_draft_text(draft_id: str) -> str:
    """Fetch the full post text from a Typefully draft. Used for rewrite context."""
    if not draft_id:
        return ""
    try:
        draft = get_draft(draft_id)
        return _extract_text_from_draft(draft)
    except Exception as e:
        logger.warning(f"Could not fetch draft text {draft_id}: {e}")
        return ""


def _format_review_message(item: dict, preview: str = "") -> str:
    """Format a review item as a concise Telegram message with preview + Typefully link."""
    title = item.get("idea", item.get("title", "Untitled"))
    fmt = ", ".join(item.get("assigned_formats", [])) or item.get("format", "—")
    urgency = item.get("urgency", "")
    urgency_tag = " [URGENT]" if urgency and urgency.lower() in ("urgent", "high", "breaking") else ""
    draft_id = item.get("typefully_draft_id", "")
    link = _get_share_link(draft_id)

    # Show actual source URL (tweet, YouTube, article) — not the internal pipeline name
    source_url = item.get("source_url", "")
    if source_url:
        source_display = f"[{source_url[:60]}]({source_url})"
    else:
        source_display = "—"

    msg = (
        f"📝 *New Draft for Review*{urgency_tag}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Title:* {title}\n"
        f"*Format:* {fmt}\n"
        f"*Source:* {source_display}\n"
        f"━━━━━━━━━━━━━━━━━\n"
    )
    if preview:
        msg += f"\n{preview}\n\n"
    msg += f"👉 [Open in Typefully]({link})"
    return msg


# ── Notion Polling ─────────────────────────────────────────────────────────

def gather_review_items() -> list[dict]:
    """Pull all 'Ready for Review' items from both Notion sources."""
    ideas = get_ready_for_review_ideas()
    library = get_ready_for_review_library()
    # Normalize library items
    for item in library:
        item["idea"] = item.get("title", "Untitled")
    return ideas + library


async def poll_and_send(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback: poll Notion for new review items and send to Telegram."""
    chat_id = int(TELEGRAM_CHAT_ID)

    try:
        items = gather_review_items()
    except Exception as e:
        logger.error(f"Notion poll failed: {e}")
        return

    new_items = [item for item in items if item["id"] not in _sent_ids]
    if not new_items:
        return

    # Prioritize by urgency: Breaking > Trending > everything else
    urgency_order = {"🔴 Breaking": 0, "🟡 Trending": 1, "🟢 Evergreen": 3, "⚪ Backlog": 4}
    new_items.sort(key=lambda x: urgency_order.get(x.get("urgency", ""), 2))

    # Cap per cycle to avoid overwhelming Telegram
    batch = new_items[:MAX_BATCH_SIZE]
    remaining = len(new_items) - len(batch)

    logger.info(f"Found {len(new_items)} new items for review, sending {len(batch)}" +
                (f" ({remaining} more next cycle)" if remaining else ""))

    if remaining:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📋 *{len(new_items)} drafts waiting for review* — showing top {len(batch)} by urgency. {remaining} more will come in the next cycle.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    for item in batch:
        notion_id = item["id"]
        draft_id = item.get("typefully_draft_id", "")
        source = item.get("source", "idea_pipeline")

        # Fetch preview text and build message
        preview = _get_draft_preview(draft_id)
        message = _format_review_message(item, preview)

        # Inline keyboard: Approve / Reject
        # Use short prefixes + no-dash UUIDs to stay under Telegram's 64-byte callback limit
        nid = notion_id.replace("-", "")
        src = "ip" if source == "idea_pipeline" else "lb"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"a:{nid}:{src}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"r:{nid}:{src}:{draft_id}"),
            ]
        ])

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            _sent_ids.add(notion_id)
            _save_sent_ids()
            logger.info(f"Sent review for: {item.get('idea', item.get('title', ''))[:50]}")
        except Exception as e:
            logger.error(f"Failed to send message for {notion_id}: {e}")


# ── Button Handlers ────────────────────────────────────────────────────────

async def handle_approve(update: Update, notion_id: str, source: str) -> None:
    """Handle the Approve button press."""
    query = update.callback_query
    await query.answer("Approving...")

    try:
        if source == "idea_pipeline":
            update_idea_status(notion_id, "Approved")
        else:
            update_longform_post(notion_id, status="Approved")

        await query.edit_message_text(
            text=query.message.text + "\n\n✅ *APPROVED* — moved to scheduling queue.",
            parse_mode="Markdown",
        )
        logger.info(f"Approved: {notion_id}")
    except Exception as e:
        await query.edit_message_text(
            text=query.message.text + f"\n\n⚠️ Error approving: {e}",
        )
        logger.error(f"Approve failed for {notion_id}: {e}")


async def handle_reject(
    update: Update,
    notion_id: str,
    source: str,
    draft_id: str,
) -> None:
    """Handle the Reject button press — ask for feedback."""
    query = update.callback_query
    await query.answer("Send me your feedback...")

    chat_id = query.message.chat_id

    # Store the reject state so we know the next text message is feedback
    _pending_feedback[chat_id] = {
        "notion_id": notion_id,
        "source": source,
        "draft_id": draft_id,
        "timestamp": time.time(),
    }

    nid = notion_id.replace("-", "")
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Cancel", callback_data=f"cr:{nid}")]
    ])

    await query.edit_message_text(
        text=query.message.text + "\n\n❌ *REJECTED* — type your feedback below. What should change?\n_Send /cancel to skip._",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard,
    )


def _expand_uuid(compact: str) -> str:
    """Convert a 32-char compact UUID back to standard format with dashes."""
    c = compact.replace("-", "")
    if len(c) == 32:
        return f"{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}"
    return compact  # already has dashes or not a UUID


def _expand_source(short: str) -> str:
    """Expand short source code back to full name."""
    return "idea_pipeline" if short == "ip" else "library"


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Router for all inline button callbacks."""
    query = update.callback_query
    data = query.data

    if data.startswith("a:"):
        # a:NOTION_ID:SOURCE
        parts = data.split(":", 2)
        notion_id = _expand_uuid(parts[1])
        source = _expand_source(parts[2])
        await handle_approve(update, notion_id, source)

    elif data.startswith("r:"):
        # r:NOTION_ID:SOURCE:DRAFT_ID
        parts = data.split(":", 3)
        notion_id = _expand_uuid(parts[1])
        source = _expand_source(parts[2])
        draft_id = parts[3]
        await handle_reject(update, notion_id, source, draft_id)

    elif data.startswith("cr:"):
        # cr:NOTION_ID — cancel reject
        chat_id = query.message.chat_id
        _pending_feedback.pop(chat_id, None)
        await query.answer("Cancelled.")
        await query.edit_message_text(
            text=query.message.text.split("\n\n❌")[0] + "\n\n🚫 *Rejection cancelled.* Draft unchanged.",
            parse_mode="Markdown",
        )


# ── Feedback → Rewrite Flow ───────────────────────────────────────────────

async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    When the user sends a text message after hitting Reject, treat it as
    revision feedback. Edits the EXISTING draft in place:
    1. Fetch the current draft from Typefully (text + media + QRT)
    2. Call Maya to apply targeted edits (only changes what feedback asks for)
    3. Update the SAME draft via Typefully edit API (preserves media, QRT, tags)
    4. Re-send for review with same Approve/Reject buttons
    """
    chat_id = update.message.chat_id

    if chat_id not in _pending_feedback:
        return  # No pending reject — ignore

    pending = _pending_feedback[chat_id]

    # Check timeout — expire after 10 minutes
    elapsed = time.time() - pending.get("timestamp", 0)
    if elapsed > FEEDBACK_TIMEOUT_SECONDS:
        _pending_feedback.pop(chat_id, None)
        await update.message.reply_text("⏰ Rejection timed out (10 min). The draft is unchanged. Use /refresh to get it again.")
        return

    feedback = update.message.text
    _pending_feedback.pop(chat_id)
    notion_id = pending["notion_id"]
    source = pending["source"]
    draft_id = pending["draft_id"]

    await update.message.reply_text("📝 Got your feedback. Revising the draft...")

    # 1. Fetch the FULL current draft from Typefully (preserves media, QRT, etc.)
    try:
        draft = get_draft(draft_id)
        platforms = draft.get("platforms", {})
        x_data = platforms.get("x", {})
        original_posts = x_data.get("posts", [])
        original_text = "\n\n---\n\n".join(p.get("text", "") for p in original_posts)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Couldn't fetch draft from Typefully: {e}\nPlease revise manually.")
        return

    if not original_text:
        await update.message.reply_text("⚠️ Draft has no text. Please revise manually in Typefully.")
        return

    # 2. Call Maya to apply TARGETED edits (only changes what feedback asks for)
    await update.message.reply_text("🔄 Maya is revising... (this takes ~30 seconds)")

    try:
        revised_text = revise_post(original_text, feedback)

        if not revised_text or len(revised_text.strip()) < 50:
            await update.message.reply_text("⚠️ Revision was too short. Try again with more specific feedback.")
            return

        logger.info(f"Maya revision: {len(original_text)} → {len(revised_text)} chars")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Maya revision failed: {e}\nThe draft is unchanged — you can edit it manually in Typefully.")
        logger.error(f"Revision failed: {e}")
        return

    # 3. Update the EXISTING draft in Typefully (preserves media, QRT, tags)
    #    Rebuild the posts array: keep media_ids and quote_post_url, update text only
    try:
        if len(original_posts) == 1:
            # Single post — replace the text, keep media + QRT
            updated_posts = [dict(original_posts[0])]
            updated_posts[0]["text"] = revised_text
        else:
            # Thread (multiple posts) — split revised text by --- separator
            revised_parts = [p.strip() for p in revised_text.split("---") if p.strip()]
            updated_posts = []
            for i, part in enumerate(revised_parts):
                if i < len(original_posts):
                    # Preserve media_ids and quote_post_url from original
                    post = dict(original_posts[i])
                    post["text"] = part
                else:
                    post = {"text": part}
                updated_posts.append(post)

        edit_draft_text(draft_id, updated_posts)
        logger.info(f"Draft {draft_id} updated in place")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Couldn't update draft in Typefully: {e}\n\n"
            f"Here's the revised text — paste it manually:\n\n{revised_text[:3000]}"
        )
        logger.error(f"Draft edit failed: {e}")
        return

    # 4. Save feedback to Notion (non-fatal)
    try:
        save_review_feedback(notion_id, feedback, source)
    except Exception as e:
        logger.warning(f"Notion feedback save failed (non-fatal): {e}")

    # 5. Re-send for review with same draft link + buttons
    _sent_ids.discard(notion_id)

    share_url = draft.get("share_url") or _get_share_link(draft_id)
    revision_preview = revised_text[:280]
    message = (
        f"🔄 *Revised Draft* (edited in place)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Feedback applied:* {feedback[:200]}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{revision_preview}\n\n"
        f"👉 [Open in Typefully]({share_url})"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"a:{notion_id.replace('-', '')}:{'ip' if source == 'idea_pipeline' else 'lb'}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"r:{notion_id.replace('-', '')}:{'ip' if source == 'idea_pipeline' else 'lb'}:{draft_id}"),
        ]
    ])

    await update.message.reply_text(
        text=message,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    _sent_ids.add(notion_id)
    _save_sent_ids()


# ── Commands ───────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — show welcome + chat ID."""
    chat_id = update.message.chat_id
    await update.message.reply_text(
        f"👋 GeniusGTX Review Bot active.\n\n"
        f"Your chat ID: `{chat_id}`\n"
        f"Add this as TELEGRAM_CHAT_ID in your .env file.\n\n"
        f"I'll send you drafts for review with Approve/Reject buttons.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command — show pending review items."""
    try:
        items = gather_review_items()
        if not items:
            await update.message.reply_text("✅ No drafts waiting for review.")
            return

        lines = [f"📋 *{len(items)} drafts waiting for review:*\n"]
        for item in items[:10]:
            title = item.get("idea", item.get("title", "Untitled"))
            fmt = ", ".join(item.get("assigned_formats", [])) or item.get("format", "—")
            sent = "📨" if item["id"] in _sent_ids else "🆕"
            lines.append(f"{sent} [{fmt}] {title[:50]}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error checking status: {e}")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command — cancel pending rejection feedback."""
    chat_id = update.message.chat_id
    if chat_id in _pending_feedback:
        _pending_feedback.pop(chat_id)
        await update.message.reply_text("🚫 Rejection cancelled. Draft unchanged.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /refresh command — force a poll cycle now."""
    await update.message.reply_text("🔄 Checking for new drafts...")
    await poll_and_send(context)
    await update.message.reply_text("✅ Done.")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        print("  1. Message @BotFather on Telegram to create a bot")
        print("  2. Copy the token and add to .env: TELEGRAM_BOT_TOKEN=<token>")
        sys.exit(1)

    if not TELEGRAM_CHAT_ID:
        print("WARNING: TELEGRAM_CHAT_ID not set in .env")
        print("  1. Start the bot and send /start")
        print("  2. Copy the chat ID from the response")
        print("  3. Add to .env: TELEGRAM_CHAT_ID=<id>")
        print("  Bot will start but won't send proactive review notifications.\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback))

    # Text messages (for feedback after reject)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message))

    # Scheduled polling job
    if TELEGRAM_CHAT_ID:
        app.job_queue.run_repeating(
            poll_and_send,
            interval=POLL_INTERVAL,
            first=10,  # first poll 10s after start
            name="notion_poll",
        )
        logger.info(f"Polling Notion every {POLL_INTERVAL}s, sending to chat {TELEGRAM_CHAT_ID}")

    logger.info("Review bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
