"""
Maya's Slack Bot — connects Maya to a Slack workspace via Socket Mode.

Maya is a normal teammate who chats naturally.
She only writes threads/content when explicitly asked.
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
from agent import write_thread, process_feedback, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("maya-slack")

app = App(token=os.getenv("SLACK_BOT_TOKEN_MAYA"))
slack_client = app.client

BOT_USER_ID = ""  # Set at startup
chat_history: dict[str, list] = {}
thread_history: dict[str, list] = {}

MAX_CHAT_HISTORY = 20


def react(channel: str, timestamp: str, emoji: str = "eyes"):
    try:
        slack_client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
    except Exception:
        pass


def classify_message(text: str) -> tuple[str, str]:
    """Classify as 'write', 'feedback' (contextual), or 'chat'."""
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not text:
        return "chat", ""

    # Explicit write request
    write_patterns = [
        r"^write (?:a |the |me )?(?:thread|body|content|post)",
        r"^thread (?:for|about|on)[:\s]",
        r"^turn this into",
        r"^expand this",
        r"^write about",
    ]
    for pattern in write_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            content = re.sub(
                r"^(?:write (?:a |the |me )?(?:thread|body|content|post)[:\s]*(?:about |for |on )?|thread (?:for|about|on)[:\s]*|turn this into (?:a )?(?:thread|content|post)[:\s]*|expand this[:\s]*(?:into )?(?:a )?(?:thread)?[:\s]*|write about[:\s]*)",
                "", text, flags=re.IGNORECASE
            ).strip()
            return "write", content if content else text

    return "chat", text


def is_thread_feedback(text: str, channel: str, thread_ts: str | None) -> bool:
    if not thread_ts:
        return False
    key = f"{channel}:{thread_ts}"
    return key in thread_history


def handle_message(event, say):
    text = event.get("text", "")
    channel = event.get("channel")
    msg_ts = event.get("ts")
    thread_ts = event.get("thread_ts")

    clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not clean_text:
        return

    react(channel, msg_ts)

    # Feedback in a writing thread
    if is_thread_feedback(clean_text, channel, thread_ts):
        react(channel, msg_ts, "pencil2")
        key = f"{channel}:{thread_ts}"
        history = thread_history[key]

        try:
            response = process_feedback(clean_text, history)
            history.append({"role": "user", "content": f"FEEDBACK: {clean_text}"})
            history.append({"role": "assistant", "content": response})
            thread_history[key] = history
            say(text=response, thread_ts=thread_ts)
        except Exception as e:
            logger.error(f"Feedback error: {e}")
            say(text=f"Hit an error on that revision: {str(e)[:200]}", thread_ts=thread_ts)
        return

    intent, content = classify_message(text)

    if intent == "write":
        say(text="Writing. Give me a minute...", thread_ts=msg_ts)

        try:
            # Check if content looks like a hook (multi-line, has thread structure)
            if "\n" in content or len(content) > 200:
                response = write_thread(hook=content)
            else:
                response = write_thread(topic=content)

            key = f"{channel}:{msg_ts}"
            thread_history[key] = [
                {"role": "user", "content": f"Write thread: {content}"},
                {"role": "assistant", "content": response},
            ]
            say(text=response, thread_ts=msg_ts)
        except Exception as e:
            logger.error(f"Write error: {e}")
            say(text=f"Something went wrong: {str(e)[:200]}", thread_ts=msg_ts)

    else:
        chat_key = channel
        history = chat_history.get(chat_key, [])

        try:
            response = chat(clean_text, conversation_history=history if history else None)

            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": response})
            if len(history) > MAX_CHAT_HISTORY:
                history = history[-MAX_CHAT_HISTORY:]
            chat_history[chat_key] = history

            say(text=response)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            say(text=f"My bad, something broke: {str(e)[:200]}")


def should_respond(text: str, channel: str, bot_user_id: str) -> bool:
    """Decide if Maya should respond to a channel message."""
    text_lower = text.lower()
    if bot_user_id and f"<@{bot_user_id}>" in text:
        return True
    if "maya" in text_lower:
        return True
    return False


@app.event("app_mention")
def handle_mention(event, say):
    handle_message(event, say)


@app.event("message")
def handle_dm(event, say):
    if event.get("bot_id") or event.get("subtype"):
        return

    channel_type = event.get("channel_type", "")
    text = event.get("text", "")
    channel = event.get("channel", "")

    if channel_type == "im":
        handle_message(event, say)
        return

    if should_respond(text, channel, BOT_USER_ID):
        handle_message(event, say)


def main():
    global BOT_USER_ID
    bot_token = os.getenv("SLACK_BOT_TOKEN_MAYA")
    app_token = os.getenv("SLACK_APP_TOKEN_MAYA")

    if not bot_token or not app_token:
        print("ERROR: Missing SLACK_BOT_TOKEN_MAYA or SLACK_APP_TOKEN_MAYA in .env")
        return

    try:
        auth = slack_client.auth_test()
        BOT_USER_ID = auth["user_id"]
    except Exception:
        BOT_USER_ID = ""

    print("=" * 60)
    print(f"MAYA — Online (bot ID: {BOT_USER_ID})")
    print("=" * 60)

    handler = SocketModeHandler(app, app_token)
    handler.start()


if __name__ == "__main__":
    main()
