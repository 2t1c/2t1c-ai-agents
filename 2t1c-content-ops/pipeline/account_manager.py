"""
Account Manager — Scheduling brain for GeniusGTX content.

Pulls approved posts from Notion (Idea Pipeline + Long-Form Post Library),
schedules them via Typefully with smart cadence rules, and tracks everything.

Cadence rules:
- 4 posts/day across 4 time slots (morning, midday, afternoon, evening EST)
- Urgent posts get priority, then by priority number
- Format diversity: avoids scheduling same format back-to-back
- Looks ahead 2 days to keep the queue full

Link tracking:
- Injects UTM parameters into product links for conversion attribution
- Pairs with weekly_report.py link_clicks metric for funnel analysis

Usage:
    python -m pipeline.account_manager --once           # schedule next batch
    python -m pipeline.account_manager --poll            # continuous polling (1hr)
    python -m pipeline.account_manager --status          # show queue status
    python -m pipeline.account_manager --dry-run         # preview without scheduling
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.notion_client import (
    get_approved_ideas,
    get_approved_library_posts,
    mark_idea_scheduled,
    mark_library_post_scheduled,
)
from tools.typefully_client import (
    get_scheduled_times,
    schedule_draft,
    get_draft,
    list_drafts,
)

# ── Config ──────────────────────────────────────────────────────────────────

POSTS_PER_DAY = 4
POLL_INTERVAL_SECONDS = 3600  # 1 hour
LOOKAHEAD_DAYS = 2  # schedule up to 2 days ahead

# Time slots in EST (UTC-5) / EDT (UTC-4). We use US/Eastern via offset.
# These are the optimal posting times for the GeniusGTX audience.
TIME_SLOTS_EST = [
    (8, 30),   # Morning:   8:30 AM EST
    (12, 0),   # Midday:   12:00 PM EST
    (16, 30),  # Afternoon: 4:30 PM EST
    (20, 0),   # Evening:   8:00 PM EST
]

# UTM source tag for product links
UTM_SOURCE = "geniusgtx"
UTM_MEDIUM = "social"
UTM_CAMPAIGN = "content"

# Domain patterns that should get UTM tracking (your product domains)
PRODUCT_LINK_PATTERNS = [
    r"geniusgtx\.com",
    r"geniusthinking\.com",
    r"2t1c\.com",
]


# ── Timezone helpers ────────────────────────────────────────────────────────

def _est_offset() -> timezone:
    """Return EST (UTC-5) timezone. Simplified — doesn't handle DST."""
    return timezone(timedelta(hours=-5))


def _now_est() -> datetime:
    """Current time in EST."""
    return datetime.now(_est_offset())


def _to_iso(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string for Typefully."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


# ── UTM Link Injection ─────────────────────────────────────────────────────

def inject_utm_params(text: str, post_id: str = "") -> str:
    """
    Find product links in post text and append UTM parameters for tracking.

    Only modifies links matching PRODUCT_LINK_PATTERNS. Leaves all other
    links untouched. Adds utm_source, utm_medium, utm_campaign, and
    utm_content (set to the post_id for per-post attribution).
    """
    if not any(re.search(p, text) for p in PRODUCT_LINK_PATTERNS):
        return text  # no product links, skip

    url_pattern = r'(https?://[^\s\)\"\']+)'

    def _add_utm(match: re.Match) -> str:
        url = match.group(1)
        # Only tag product links
        if not any(re.search(p, url) for p in PRODUCT_LINK_PATTERNS):
            return url

        separator = "&" if "?" in url else "?"
        utm = (
            f"{separator}utm_source={UTM_SOURCE}"
            f"&utm_medium={UTM_MEDIUM}"
            f"&utm_campaign={UTM_CAMPAIGN}"
        )
        if post_id:
            utm += f"&utm_content={post_id}"
        return url + utm

    return re.sub(url_pattern, _add_utm, text)


# ── Slot Computation ───────────────────────────────────────────────────────

def compute_open_slots(
    already_scheduled: list[str],
    lookahead_days: int = LOOKAHEAD_DAYS,
) -> list[datetime]:
    """
    Compute available posting slots for the next N days.

    Compares TIME_SLOTS_EST against already_scheduled timestamps.
    Returns a sorted list of open datetime slots.
    """
    est = _est_offset()
    now = _now_est()

    # Parse already-scheduled times into EST date+hour for comparison
    booked = set()
    for ts in already_scheduled:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            dt_est = dt.astimezone(est)
            # Key: date + hour (we consider a slot "taken" if same date+hour)
            booked.add((dt_est.date(), dt_est.hour))
        except (ValueError, AttributeError):
            continue

    open_slots = []
    for day_offset in range(lookahead_days + 1):
        date = (now + timedelta(days=day_offset)).date()
        for hour, minute in TIME_SLOTS_EST:
            slot = datetime(date.year, date.month, date.day, hour, minute, tzinfo=est)
            # Skip slots in the past (need at least 15 min buffer)
            if slot <= now + timedelta(minutes=15):
                continue
            # Skip slots already booked
            if (date, hour) in booked:
                continue
            open_slots.append(slot)

    return sorted(open_slots)


# ── Post Prioritization ───────────────────────────────────────────────────

def prioritize_posts(posts: list[dict]) -> list[dict]:
    """
    Sort approved posts by scheduling priority:
    1. Urgent posts first
    2. Then by priority number (lower = higher priority)
    3. Then by source (idea_pipeline before library for variety)
    """
    def _sort_key(post: dict) -> tuple:
        urgency = post.get("urgency", "")
        is_urgent = 0 if urgency and urgency.lower() in ("urgent", "high", "breaking") else 1
        priority = post.get("priority") or 999
        source_order = 0 if post.get("source") == "idea_pipeline" else 1
        return (is_urgent, priority, source_order)

    return sorted(posts, key=_sort_key)


def diversify_format_order(posts: list[dict]) -> list[dict]:
    """
    Reorder posts to avoid scheduling the same format back-to-back.
    Uses a simple greedy approach: pick the next post whose format
    differs from the previous one.
    """
    if len(posts) <= 1:
        return posts

    result = [posts[0]]
    remaining = list(posts[1:])

    while remaining:
        last_format = _get_format(result[-1])
        # Try to find a post with a different format
        different = [p for p in remaining if _get_format(p) != last_format]
        if different:
            pick = different[0]
        else:
            pick = remaining[0]
        result.append(pick)
        remaining.remove(pick)

    return result


def _get_format(post: dict) -> str:
    """Extract format name from a post dict (works for both sources)."""
    if post.get("source") == "library":
        return post.get("format", "")
    # Idea Pipeline: use first assigned format
    formats = post.get("assigned_formats", [])
    return formats[0] if formats else ""


# ── Core Scheduling ────────────────────────────────────────────────────────

def gather_approved_posts() -> list[dict]:
    """
    Pull approved posts from both Notion sources.
    Returns a unified list with 'source' field indicating origin.
    """
    ideas = get_approved_ideas()
    library_posts = get_approved_library_posts()

    # Normalize library posts to have consistent fields
    for post in library_posts:
        post["idea"] = post.get("title", "Untitled")

    all_posts = ideas + library_posts
    print(f"  Found {len(ideas)} approved ideas + {len(library_posts)} approved library posts = {len(all_posts)} total")
    return all_posts


def schedule_batch(dry_run: bool = False) -> list[dict]:
    """
    Main scheduling function. Pulls approved posts, assigns them to open
    time slots, and schedules via Typefully.

    Returns list of scheduled post dicts with slot info.
    """
    print("Account Manager — Scheduling run")
    print("=" * 60)

    # 1. Gather approved posts
    print("\n[1/4] Gathering approved posts from Notion...")
    posts = gather_approved_posts()
    if not posts:
        print("  No approved posts to schedule.")
        return []

    # 2. Check existing schedule
    print("\n[2/4] Checking existing Typefully schedule...")
    already_scheduled = get_scheduled_times()
    print(f"  {len(already_scheduled)} posts already scheduled")

    # 3. Compute open slots
    open_slots = compute_open_slots(already_scheduled)
    print(f"  {len(open_slots)} open slots available (next {LOOKAHEAD_DAYS} days)")

    if not open_slots:
        print("  No open slots — queue is full!")
        return []

    # 4. Prioritize and diversify
    print("\n[3/4] Prioritizing and diversifying format order...")
    posts = prioritize_posts(posts)
    posts = diversify_format_order(posts)

    # Only schedule as many as we have slots for
    to_schedule = posts[:len(open_slots)]
    print(f"  Scheduling {len(to_schedule)} posts into {len(open_slots)} slots")

    # 5. Schedule each post
    print(f"\n[4/4] {'DRY RUN — ' if dry_run else ''}Scheduling posts via Typefully...")
    results = []

    for post, slot in zip(to_schedule, open_slots):
        draft_id = post.get("typefully_draft_id", "")
        title = post.get("idea", post.get("title", "Untitled"))
        fmt = _get_format(post)
        slot_str = slot.strftime("%b %d %I:%M %p EST")

        if not draft_id:
            print(f"  SKIP: '{title[:50]}' — no Typefully draft ID")
            continue

        print(f"  [{fmt or 'unknown'}] {title[:50]}")
        print(f"    → Slot: {slot_str} | Draft: {draft_id}")

        if dry_run:
            print(f"    → DRY RUN: would schedule at {_to_iso(slot)}")
            results.append({
                "post_id": post["id"],
                "title": title,
                "format": fmt,
                "draft_id": draft_id,
                "scheduled_at": _to_iso(slot),
                "slot_display": slot_str,
                "source": post.get("source", "unknown"),
                "dry_run": True,
            })
            continue

        try:
            schedule_draft(draft_id, _to_iso(slot))

            # Update Notion status
            if post.get("source") == "idea_pipeline":
                mark_idea_scheduled(post["id"])
            else:
                mark_library_post_scheduled(post["id"])

            print(f"    → Scheduled + Notion updated")

            results.append({
                "post_id": post["id"],
                "title": title,
                "format": fmt,
                "draft_id": draft_id,
                "scheduled_at": _to_iso(slot),
                "slot_display": slot_str,
                "source": post.get("source", "unknown"),
            })

        except Exception as e:
            print(f"    → ERROR: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SCHEDULED: {len(results)} posts")
    for r in results:
        prefix = "[DRY] " if r.get("dry_run") else ""
        print(f"  {prefix}{r['slot_display']:20s} | [{r['format']}] {r['title'][:40]}")
    print(f"{'=' * 60}")

    return results


# ── Status View ────────────────────────────────────────────────────────────

def show_status():
    """Show current scheduling status: what's queued, what's approved, open slots."""
    print("Account Manager — Queue Status")
    print("=" * 60)

    # Approved posts waiting
    posts = gather_approved_posts()

    # Scheduled drafts
    scheduled = get_scheduled_times()
    print(f"\nScheduled in Typefully:  {len(scheduled)}")

    # Open slots
    open_slots = compute_open_slots(scheduled)
    print(f"Open slots (next {LOOKAHEAD_DAYS} days): {len(open_slots)}")

    if open_slots:
        print("\nNext open slots:")
        for slot in open_slots[:8]:
            print(f"  {slot.strftime('%a %b %d %I:%M %p EST')}")

    if posts:
        print(f"\nApproved posts waiting ({len(posts)}):")
        for p in posts[:10]:
            title = p.get("idea", p.get("title", "Untitled"))
            fmt = _get_format(p)
            urgency = p.get("urgency", "")
            tag = f" [URGENT]" if urgency and urgency.lower() in ("urgent", "high", "breaking") else ""
            print(f"  [{fmt}] {title[:50]}{tag}")

    # Capacity check
    capacity_per_day = POSTS_PER_DAY
    days_of_content = len(scheduled) / capacity_per_day if capacity_per_day else 0
    print(f"\nDays of content scheduled: {days_of_content:.1f}")
    if days_of_content < 1:
        print("  WARNING: Less than 1 day of content scheduled!")
    elif days_of_content < 2:
        print("  Content buffer is thin — consider scheduling more.")
    else:
        print("  Content buffer is healthy.")

    print(f"{'=' * 60}")


# ── Poll Mode ──────────────────────────────────────────────────────────────

def run_poll(dry_run: bool = False):
    """Continuously poll for approved posts and schedule them."""
    print(f"Account Manager — Polling every {POLL_INTERVAL_SECONDS // 60} minutes")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            schedule_batch(dry_run=dry_run)
            print(f"\nSleeping {POLL_INTERVAL_SECONDS // 60}m until next check...\n")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nAccount Manager stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Account Manager — scheduling brain for GeniusGTX")
    parser.add_argument("--once", action="store_true", help="Schedule one batch and exit")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for approved posts")
    parser.add_argument("--status", action="store_true", help="Show queue status")
    parser.add_argument("--dry-run", action="store_true", help="Preview without actually scheduling")
    parser.add_argument("--lookahead", type=int, default=LOOKAHEAD_DAYS, help="Days to look ahead (default 2)")
    args = parser.parse_args()

    # Update module-level lookahead if overridden
    if args.lookahead != LOOKAHEAD_DAYS:
        import pipeline.account_manager as _self
        _self.LOOKAHEAD_DAYS = args.lookahead

    if args.status:
        show_status()
    elif args.poll:
        run_poll(dry_run=args.dry_run)
    elif args.once or args.dry_run:
        schedule_batch(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
