"""
Weekly Performance Report Generator — GeniusGTX Business Scorecard

Pulls analytics from Typefully + pipeline health from Notion,
then creates a new entry in the Weekly Performance Reports database.

Usage:
    python -m pipeline.weekly_report                 # report for last 7 days
    python -m pipeline.weekly_report --dry-run       # preview without writing to Notion
    python -m pipeline.weekly_report --start 2026-03-24 --end 2026-03-30  # custom range

Designed to be run every Monday by a scheduled agent or cron job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from notion_client import Client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

# ── Config ──────────────────────────────────────────────────────────────────

TYPEFULLY_API_KEY = os.getenv("TYPEFULLY_API_KEY")
TYPEFULLY_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
notion = Client(auth=NOTION_API_KEY)

# Database IDs
# Data source (collection) IDs — used with notion.data_sources.query() in v3
WEEKLY_REPORTS_DB_ID = os.getenv(
    "NOTION_WEEKLY_REPORTS_DB_ID",
    "116a60e2-736e-4062-8054-a59c994857c7",
)
WEEKLY_REPORTS_DS_ID = os.getenv(
    "NOTION_WEEKLY_REPORTS_DS_ID",
    "a4cfa4c8-dead-44ab-a236-42ae91a864a8",
)
IDEA_PIPELINE_DS_ID = os.getenv(
    "NOTION_IDEA_PIPELINE_DB_ID",
    "330aef7b-3feb-401e-abba-28452441a64d",
)
VIDEO_BACKLOG_DS_ID = os.getenv(
    "NOTION_VIDEO_BACKLOG_DB_ID",
    "316f17ad-ba4f-4719-b239-67a38141b0c9",
)

# Q2 2026 targets
TARGETS = {
    "avg_impressions_post": 100_000,       # target: 100K per post
    "avg_impressions_post_min": 50_000,    # minimum acceptable: 50K per post
    "engagement_rate": 1.75,
    "posts_per_week": 25,
    "saves_per_post": 150,
    "profile_clicks_per_post": 50,
    "link_clicks_per_post": 20,
}


# ── Typefully Analytics ─────────────────────────────────────────────────────

def fetch_typefully_analytics(start_date: str, end_date: str) -> list[dict]:
    """Fetch post analytics from Typefully for a date range."""
    url = (
        f"https://api.typefully.com/v2/social-sets/{TYPEFULLY_SOCIAL_SET_ID}"
        f"/analytics/x/posts"
    )
    headers = {
        "Authorization": f"Bearer {TYPEFULLY_API_KEY}",
        "Content-Type": "application/json",
    }
    all_results = []
    offset = 0
    limit = 100

    while True:
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset,
            "include_replies": "false",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        all_results.extend(results)

        if data.get("next") and len(results) == limit:
            offset += limit
        else:
            break

    return all_results


def compute_metrics(posts: list[dict]) -> dict:
    """Compute aggregate metrics from Typefully post data."""
    if not posts:
        return {
            "posts_published": 0,
            "total_impressions": 0,
            "avg_impressions_post": 0,
            "total_engagement": 0,
            "engagement_rate": 0.0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "quotes": 0,
            "saves": 0,
            "profile_clicks": 0,
            "link_clicks": 0,
            "top_post_impressions": 0,
            "top_post_preview": "No posts this week",
        }

    total_impressions = sum(p["metrics"]["impressions"] for p in posts)
    total_engagement = sum(p["metrics"]["engagement"]["total"] for p in posts)
    likes = sum(p["metrics"]["engagement"]["likes"] for p in posts)
    comments = sum(p["metrics"]["engagement"]["comments"] for p in posts)
    shares = sum(p["metrics"]["engagement"]["shares"] for p in posts)
    quotes = sum(p["metrics"]["engagement"]["quotes"] for p in posts)
    saves = sum(p["metrics"]["engagement"]["saves"] for p in posts)
    profile_clicks = sum(p["metrics"]["engagement"]["profile_clicks"] for p in posts)
    # Link clicks: may not be present in all Typefully API responses — gracefully default to 0
    link_clicks = sum(p["metrics"]["engagement"].get("link_clicks", 0) or p["metrics"]["engagement"].get("url_clicks", 0) for p in posts)

    top_post = max(posts, key=lambda p: p["metrics"]["impressions"])

    return {
        "posts_published": len(posts),
        "total_impressions": total_impressions,
        "avg_impressions_post": round(total_impressions / len(posts)),
        "total_engagement": total_engagement,
        "engagement_rate": round(total_engagement / total_impressions * 100, 2) if total_impressions else 0.0,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "quotes": quotes,
        "saves": saves,
        "profile_clicks": profile_clicks,
        "link_clicks": link_clicks,
        "top_post_impressions": top_post["metrics"]["impressions"],
        "top_post_preview": top_post["preview_text"][:200],
    }


# ── Notion Pipeline Health ──────────────────────────────────────────────────

def _query_data_source(ds_id: str, body: dict | None = None) -> list[dict]:
    """Query a Notion data source (collection), returning results or empty list on error."""
    try:
        response = notion.data_sources.query(data_source_id=ds_id, **(body or {}))
        return response.get("results", [])
    except Exception as e:
        print(f"    Warning: Notion query failed for {ds_id}: {e}")
        return []


def count_ideas_by_status(status: str | None = None) -> int:
    """Count ideas in the Idea Pipeline, optionally filtered by status."""
    body = {}
    if status:
        body = {"filter": {"property": "Status", "select": {"equals": status}}}
    return len(_query_data_source(IDEA_PIPELINE_DS_ID, body))


def count_videos_in_backlog() -> int:
    """Count videos in Video Backlog with status 'New' or 'Ready'."""
    body = {
        "filter": {
            "or": [
                {"property": "Status", "select": {"equals": "New"}},
                {"property": "Status", "select": {"equals": "Ready"}},
            ]
        }
    }
    return len(_query_data_source(VIDEO_BACKLOG_DS_ID, body))


# ── Status Assessment ───────────────────────────────────────────────────────

def assess_status(metrics: dict) -> str:
    """Compare metrics against targets to determine status."""
    score = 0
    checks = 0

    if metrics["posts_published"] >= TARGETS["posts_per_week"]:
        score += 1
    checks += 1

    if metrics["avg_impressions_post"] >= TARGETS["avg_impressions_post"]:
        score += 1
    checks += 1

    if metrics["engagement_rate"] >= TARGETS["engagement_rate"]:
        score += 1
    checks += 1

    # Link clicks — the conversion metric for product launch
    if metrics["posts_published"] > 0:
        lc_per_post = metrics.get("link_clicks", 0) / metrics["posts_published"]
        if lc_per_post >= TARGETS["link_clicks_per_post"]:
            score += 1
        checks += 1

    ratio = score / checks if checks else 0
    if ratio >= 0.8:
        return "Ahead"
    elif ratio >= 0.5:
        return "On Track"
    else:
        return "Behind"


# ── Report Writer ───────────────────────────────────────────────────────────

def create_weekly_report(
    start_date: str,
    end_date: str,
    dry_run: bool = False,
) -> dict:
    """Generate and write a weekly report to Notion."""
    print(f"Generating report for {start_date} to {end_date}...")

    # 1. Pull Typefully analytics
    print("  Fetching Typefully analytics...")
    posts = fetch_typefully_analytics(start_date, end_date)
    metrics = compute_metrics(posts)
    print(f"  Found {metrics['posts_published']} posts, {metrics['total_impressions']:,} impressions")

    # 2. Pull pipeline health from Notion
    print("  Checking pipeline health...")
    ideas_total = count_ideas_by_status()
    ideas_ready = count_ideas_by_status("Approved")
    videos_backlog = count_videos_in_backlog()
    print(f"  Pipeline: {ideas_total} ideas total, {ideas_ready} ready, {videos_backlog} videos in backlog")

    # 3. Assess status
    status = assess_status(metrics)
    print(f"  Status: {status}")

    # 4. Build week label
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    week_label = f"Week of {start_dt.strftime('%b %d')} - {end_dt.strftime('%b %d, %Y')}"

    # 5. Build notes summary
    notes_parts = []
    if metrics["posts_published"] == 0:
        notes_parts.append("No posts published this week (analytics may be delayed).")
    else:
        saves_per_post = round(metrics["saves"] / metrics["posts_published"], 1)
        clicks_per_post = round(metrics["profile_clicks"] / metrics["posts_published"], 1)
        notes_parts.append(f"Saves/post: {saves_per_post} (target: {TARGETS['saves_per_post']})")
        notes_parts.append(f"Profile clicks/post: {clicks_per_post} (target: {TARGETS['profile_clicks_per_post']})")

        link_clicks_per_post = round(metrics["link_clicks"] / metrics["posts_published"], 1)
        notes_parts.append(f"Link clicks/post: {link_clicks_per_post} (target: {TARGETS['link_clicks_per_post']})")

        avg = metrics["avg_impressions_post"]
        if avg >= TARGETS["avg_impressions_post"]:
            notes_parts.append(f"Impressions {avg:,}/post — above 100K target.")
        elif avg >= TARGETS["avg_impressions_post_min"]:
            notes_parts.append(f"Impressions {avg:,}/post — above 50K minimum, below 100K target.")
        else:
            notes_parts.append(f"Impressions {avg:,}/post — below 50K minimum.")

    notes = " | ".join(notes_parts)

    # 6. Build the report payload
    report = {
        "Week": week_label,
        "date:Week Start:start": start_date,
        "date:Week End:start": end_date,
        "Posts Published": metrics["posts_published"],
        "Total Impressions": metrics["total_impressions"],
        "Avg Impressions/Post": metrics["avg_impressions_post"],
        "Total Engagement": metrics["total_engagement"],
        "Engagement Rate %": metrics["engagement_rate"],
        "Likes": metrics["likes"],
        "Comments": metrics["comments"],
        "Shares": metrics["shares"],
        "Quotes": metrics["quotes"],
        "Saves": metrics["saves"],
        "Profile Clicks": metrics["profile_clicks"],
        "Link Clicks": metrics["link_clicks"],
        "Top Post Impressions": metrics["top_post_impressions"],
        "Top Post Preview": metrics["top_post_preview"],
        "Ideas in Pipeline": ideas_total,
        "Ideas Ready to Post": ideas_ready,
        "Videos in Backlog": videos_backlog,
        "Status": status,
        "Notes": notes,
    }

    if dry_run:
        print("\n  DRY RUN — would create report:")
        print(json.dumps(report, indent=2))
        return report

    # 7. Write to Notion
    print("  Writing to Notion...")
    page = notion.pages.create(
        parent={"database_id": WEEKLY_REPORTS_DB_ID},
        properties=_build_notion_properties(report),
    )
    report["notion_page_id"] = page["id"]
    report["notion_url"] = page["url"]
    print(f"  Report created: {page['url']}")

    # 8. Push summary to Telegram CEO bot
    try:
        from agents.ceo.notify import send_weekly_report_summary
        print("  Sending Telegram notification...")
        sent = send_weekly_report_summary(report)
        print(f"  Telegram: {'sent' if sent else 'failed'}")
    except Exception as e:
        print(f"  Telegram notification skipped: {e}")

    return report


def _build_notion_properties(report: dict) -> dict:
    """Convert flat report dict to Notion page properties format."""
    return {
        "Week": {"title": [{"text": {"content": report["Week"]}}]},
        "Week Start": {"date": {"start": report["date:Week Start:start"]}},
        "Week End": {"date": {"start": report["date:Week End:start"]}},
        "Posts Published": {"number": report["Posts Published"]},
        "Total Impressions": {"number": report["Total Impressions"]},
        "Avg Impressions/Post": {"number": report["Avg Impressions/Post"]},
        "Total Engagement": {"number": report["Total Engagement"]},
        "Engagement Rate %": {"number": report["Engagement Rate %"]},
        "Likes": {"number": report["Likes"]},
        "Comments": {"number": report["Comments"]},
        "Shares": {"number": report["Shares"]},
        "Quotes": {"number": report["Quotes"]},
        "Saves": {"number": report["Saves"]},
        "Profile Clicks": {"number": report["Profile Clicks"]},
        "Link Clicks": {"number": report["Link Clicks"]},
        "Top Post Impressions": {"number": report["Top Post Impressions"]},
        "Top Post Preview": {"rich_text": [{"text": {"content": report["Top Post Preview"]}}]},
        "Format Mix": {"rich_text": [{"text": {"content": report.get("Format Mix", "")}}]},
        "Ideas in Pipeline": {"number": report["Ideas in Pipeline"]},
        "Ideas Ready to Post": {"number": report["Ideas Ready to Post"]},
        "Videos in Backlog": {"number": report["Videos in Backlog"]},
        "Status": {"select": {"name": report["Status"]}},
        "Notes": {"rich_text": [{"text": {"content": report["Notes"]}}]},
    }


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate weekly performance report")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD). Default: last Monday")
    parser.add_argument("--end", help="End date (YYYY-MM-DD). Default: last Sunday")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion")
    args = parser.parse_args()

    today = datetime.now()
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        # Default: previous Monday to Sunday
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = last_sunday.strftime("%Y-%m-%d")

    report = create_weekly_report(start_date, end_date, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print(f"WEEKLY REPORT: {report['Week']}")
    print("=" * 60)
    print(f"Posts Published:      {report['Posts Published']}")
    print(f"Total Impressions:    {report['Total Impressions']:,}")
    print(f"Avg Impressions/Post: {report['Avg Impressions/Post']:,}")
    print(f"Engagement Rate:      {report['Engagement Rate %']}%")
    print(f"Saves:                {report['Saves']:,}")
    print(f"Profile Clicks:       {report['Profile Clicks']:,}")
    print(f"Link Clicks:          {report['Link Clicks']:,}")
    print(f"Pipeline Ideas:       {report['Ideas in Pipeline']}")
    print(f"Ready to Post:        {report['Ideas Ready to Post']}")
    print(f"Video Backlog:        {report['Videos in Backlog']}")
    print(f"Status:               {report['Status']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
