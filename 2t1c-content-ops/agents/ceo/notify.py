"""
CEO Bot — Proactive Notification Module

Any script can import this to push insights to Toản's Telegram.
Messages land in the CEO bot chat, so he can reply and have a conversation.

Usage:
    from agents.ceo.notify import send_insight, send_weekly_report_summary

    # Simple message
    send_insight("Pipeline is running low — only 3 ideas in Ready status.")

    # Weekly report summary (pass the report dict from weekly_report.py)
    send_weekly_report_summary(report)
"""

from __future__ import annotations

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

BOT_TOKEN = os.getenv("TELEGRAM_CEO_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CEO_CHAT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to the CEO chat. Returns True on success."""
    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
        },
        timeout=10,
    )
    return resp.status_code == 200


def send_insight(text: str) -> bool:
    """Send a plain insight/alert to Telegram."""
    return send_message(text, parse_mode="HTML")


def send_weekly_report_summary(report: dict) -> bool:
    """Format and send a weekly report summary to Telegram.

    Args:
        report: The report dict from weekly_report.py's create_weekly_report()
    """
    posts = report.get("Posts Published", 0)
    impressions = report.get("Total Impressions", 0)
    avg_imp = report.get("Avg Impressions/Post", 0)
    eng_rate = report.get("Engagement Rate %", 0)
    saves = report.get("Saves", 0)
    clicks = report.get("Profile Clicks", 0)
    status = report.get("Status", "Unknown")
    ideas = report.get("Ideas in Pipeline", 0)
    ready = report.get("Ideas Ready to Post", 0)
    top_preview = report.get("Top Post Preview", "")[:120]
    week = report.get("Week", "This week")
    notes = report.get("Notes", "")

    # Status emoji
    status_emoji = {"Ahead": "🟢", "On Track": "🟡", "Behind": "🔴"}.get(status, "⚪")

    # Format large numbers
    def fmt(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    msg = (
        f"<b>📊 Weekly Report — {week}</b>\n"
        f"{status_emoji} Status: <b>{status}</b>\n"
        f"\n"
        f"<b>Output</b>\n"
        f"  Posts: {posts}\n"
        f"  Impressions: {fmt(impressions)} ({fmt(avg_imp)} avg)\n"
        f"  Engagement: {eng_rate}%\n"
        f"  Saves: {fmt(saves)} · Clicks: {fmt(clicks)}\n"
        f"\n"
        f"<b>Pipeline</b>\n"
        f"  Ideas: {ideas} total · {ready} ready\n"
        f"\n"
        f"<b>Top post</b>\n"
        f"  {top_preview}...\n"
    )

    if notes:
        msg += f"\n<b>Notes</b>\n  {notes}\n"

    msg += "\n💬 Reply to discuss or adjust strategy."

    return send_message(msg)


def send_pipeline_pulse() -> bool:
    """Send a quick pipeline health pulse. Call this from a daily script."""
    from agents.ceo.agent import _pipeline_summary
    import json

    data = json.loads(_pipeline_summary())
    total = data.get("total_ideas", 0)
    by_status = data.get("by_status", {})
    videos = data.get("videos_in_backlog", 0)

    new = by_status.get("New", 0)
    drafting = by_status.get("Drafting", 0)
    review = by_status.get("Ready for Review", 0)
    approved = by_status.get("Approved", 0)

    # Only send if something needs attention
    alerts = []
    if approved < 5:
        alerts.append(f"⚠️ Only {approved} approved ideas — queue is thin")
    if review > 0:
        alerts.append(f"👀 {review} ideas waiting for your review")
    if new > 50:
        alerts.append(f"📥 {new} untriggered ideas piling up")

    if not alerts:
        return True  # Nothing to report

    msg = (
        f"<b>🔔 Pipeline Pulse</b>\n"
        f"\n"
        f"  New: {new} · Drafting: {drafting}\n"
        f"  Review: {review} · Approved: {approved}\n"
        f"  Videos: {videos}\n"
        f"\n"
        + "\n".join(alerts)
        + "\n\n💬 Reply to take action."
    )

    return send_message(msg)
