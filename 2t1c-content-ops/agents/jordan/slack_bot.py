"""
Jordan's Slack Bot — connects Jordan to a Slack workspace via Socket Mode.

Jordan is a normal teammate who chats naturally.
He only writes hooks when explicitly asked.
"""

from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import generate_hooks, process_feedback, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jordan-slack")

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
slack_client = app.client

# Conversation history per channel (for chat) and per thread (for hooks)
BOT_USER_ID = ""  # Set at startup
chat_history: dict[str, list] = {}
hook_history: dict[str, list] = {}

# Cap chat history to avoid token bloat
MAX_CHAT_HISTORY = 20


def react(channel: str, timestamp: str, emoji: str = "eyes"):
    """Add an emoji reaction as instant acknowledgment."""
    try:
        slack_client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
    except Exception:
        pass


def get_chat_key(channel: str) -> str:
    return channel


def get_hook_thread_key(channel: str, thread_ts: str) -> str:
    return f"{channel}:{thread_ts}"


def classify_message(text: str) -> tuple[str, str]:
    """
    Classify a message as 'hook', 'feedback', or 'chat'.

    Only returns 'hook' if the user explicitly asks for hooks.
    Everything else is normal chat.
    """
    # Remove bot mention
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not text:
        return "chat", ""

    # Explicit hook request patterns
    hook_patterns = [
        r"^hook (?:me|this|about)",
        r"^write (?:a |me |)(?:hook|hooks)",
        r"^give me (?:a |some |)hooks?",
        r"^I need (?:a |some |)hooks?",
        r"^hooks? (?:for|about|on)[:\s]",
    ]
    for pattern in hook_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            topic = re.sub(
                r"^(?:hook me[:\s]*|write (?:a |me |)hooks?[:\s]*(?:about |for |on )?|give me (?:a |some |)hooks?[:\s]*(?:about |for |on )?|I need (?:a |some |)hooks?[:\s]*(?:about |for |on )?|hooks? (?:for|about|on)[:\s]*)",
                "", text, flags=re.IGNORECASE
            ).strip()
            return "hook", topic if topic else text

    # Feedback only makes sense in a hook thread
    # (handled contextually in the handler, not here)

    # Everything else is chat
    return "chat", text


def is_hook_feedback(text: str, channel: str, thread_ts: str | None) -> bool:
    """Check if this message is feedback on hooks in an active hook thread."""
    if not thread_ts:
        return False
    key = get_hook_thread_key(channel, thread_ts)
    if key not in hook_history:
        return False
    # If we're in a hook thread, treat the reply as feedback
    return True


def handle_message(event, say):
    """Core message handler for both DMs and mentions."""
    text = event.get("text", "")
    channel = event.get("channel")
    msg_ts = event.get("ts")
    thread_ts = event.get("thread_ts")

    # Clean text (remove bot mention)
    clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not clean_text:
        return

    # Instant acknowledgment
    react(channel, msg_ts)

    # Check if this is a reply inside a hook thread (= feedback)
    if is_hook_feedback(clean_text, channel, thread_ts):
        react(channel, msg_ts, "pencil2")
        key = get_hook_thread_key(channel, thread_ts)
        history = hook_history[key]

        try:
            response = process_feedback(clean_text, history)
            history.append({"role": "user", "content": f"FEEDBACK: {clean_text}"})
            history.append({"role": "assistant", "content": response})
            hook_history[key] = history
            say(text=response, thread_ts=thread_ts)
        except Exception as e:
            logger.error(f"Feedback error: {e}")
            say(text=f"Hit an error processing that feedback: {str(e)[:200]}", thread_ts=thread_ts)
        return

    # Classify the message
    intent, content = classify_message(text)

    if intent == "hook":
        # Hook requests get their own thread (big output)
        say(text="Finding the angle. Writing 3 hooks...", thread_ts=msg_ts)

        try:
            response = generate_hooks(content)
            # Store in hook history keyed by the thread
            key = get_hook_thread_key(channel, msg_ts)
            hook_history[key] = [
                {"role": "user", "content": f"Topic: {content}"},
                {"role": "assistant", "content": response},
            ]
            say(text=response, thread_ts=msg_ts)
        except Exception as e:
            logger.error(f"Hook error: {e}")
            say(text=f"Something went wrong writing those hooks: {str(e)[:200]}", thread_ts=msg_ts)

    else:
        # Normal chat — reply directly, no thread
        chat_key = get_chat_key(channel)
        history = chat_history.get(chat_key, [])

        try:
            response = chat(clean_text, conversation_history=history if history else None)

            # Update chat history
            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": response})
            # Trim to keep it manageable
            if len(history) > MAX_CHAT_HISTORY:
                history = history[-MAX_CHAT_HISTORY:]
            chat_history[chat_key] = history

            say(text=response)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            say(text=f"My bad, something broke: {str(e)[:200]}")


def should_respond(text: str, channel: str, bot_user_id: str) -> bool:
    """Decide if Jordan should respond to a channel message."""
    text_lower = text.lower()
    # Always respond if @mentioned
    if bot_user_id and f"<@{bot_user_id}>" in text:
        return True
    # Respond if name is mentioned
    if "jordan" in text_lower:
        return True
    # Respond in DMs always
    return False


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @Jordan mentions in channels."""
    handle_message(event, say)


@app.event("message")
def handle_dm(event, say):
    """Handle DMs and channel messages."""
    if event.get("bot_id") or event.get("subtype"):
        return

    channel_type = event.get("channel_type", "")
    text = event.get("text", "")
    channel = event.get("channel", "")

    # Always respond in DMs
    if channel_type == "im":
        handle_message(event, say)
        return

    # In channels: respond if Jordan is addressed by name or @mention
    if should_respond(text, channel, BOT_USER_ID):
        handle_message(event, say)


def main():
    global BOT_USER_ID
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")

    if not bot_token or not app_token:
        print("ERROR: Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN in .env")
        return

    # Get bot's own user ID for mention detection
    try:
        auth = slack_client.auth_test()
        BOT_USER_ID = auth["user_id"]
    except Exception:
        BOT_USER_ID = ""

    print("=" * 60)
    print(f"JORDAN — Online (bot ID: {BOT_USER_ID})")
    print("=" * 60)

    handler = SocketModeHandler(app, app_token)
    handler.start()


if __name__ == "__main__":
    main()
