"""
Typefully Sync — Two-way sync between Typefully draft status and Notion Idea Pipeline.

Direction 1 (Typefully -> Notion):
  Checks drafts that Notion marks as "Approved" or "Scheduled" with a Typefully Draft ID.
  If Typefully shows published -> update Notion to "Published".
  If Typefully shows scheduled -> update Notion to "Scheduled" (if not already).

Direction 2 (Notion -> Typefully):
  For "Approved" ideas with a Typefully Draft ID, schedule the draft on Typefully
  and update Notion to "Scheduled".

Usage:
    python -m pipeline.typefully_sync --sync       # run both directions once
    python -m pipeline.typefully_sync --poll       # run sync every 5 minutes continuously
    python -m pipeline.typefully_sync --dry-run    # preview without making changes
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.notion_client import (
    IDEA_PIPELINE_DB_ID,
    LONGFORM_POST_DB_ID,
    _query_database,
    _get_title,
    _get_rich_text,
    _get_select,
    _get_multi_select,
    update_idea_status,
    update_longform_post,
)

# ── Config ──────────────────────────────────────────────────────────────────

TYPEFULLY_API_KEY = os.getenv("TYPEFULLY_API_KEY")
TYPEFULLY_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))
TYPEFULLY_API_BASE = "https://api.typefully.com/v2"

POLL_INTERVAL = 300  # 5 minutes


# ── Typefully API helpers ──────────────────────────────────────────────────

def _typefully_headers() -> dict:
    return {
        "Authorization": f"Bearer {TYPEFULLY_API_KEY}",
        "Content-Type": "application/json",
    }


def get_typefully_draft(draft_id: str) -> dict | None:
    """
    Fetch a single Typefully draft by ID.

    Returns the draft dict or None on error.
    The draft status field indicates: 'draft', 'scheduled', 'published', 'publishing', 'error'.
    """
    url = f"{TYPEFULLY_API_BASE}/social-sets/{TYPEFULLY_SOCIAL_SET_ID}/drafts/{draft_id}"
    try:
        resp = requests.get(url, headers=_typefully_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print(f"    Draft {draft_id} not found on Typefully (404)")
        else:
            print(f"    Error fetching draft {draft_id}: {e}")
        return None
    except Exception as e:
        print(f"    Error fetching draft {draft_id}: {e}")
        return None


def schedule_typefully_draft(draft_id: str) -> bool:
    """
    Schedule a Typefully draft by adding it to the next available queue slot.

    Returns True on success, False on failure.
    """
    url = f"{TYPEFULLY_API_BASE}/social-sets/{TYPEFULLY_SOCIAL_SET_ID}/drafts/{draft_id}/add-to-queue"
    try:
        resp = requests.post(url, headers=_typefully_headers(), timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"    Error scheduling draft {draft_id}: {e}")
        return False


# ── Notion query helpers ───────────────────────────────────────────────────

def get_ideas_with_draft_id(statuses: list[str]) -> list[dict]:
    """
    Query Idea Pipeline for ideas matching given statuses that have a Typefully Draft ID.
    """
    # Notion API doesn't allow nested or-inside-and, so query each status separately
    all_results = []
    for status in statuses:
        filters = {
            "and": [
                {"property": "Status", "select": {"equals": status}},
                {"property": "Typefully Draft ID", "rich_text": {"is_not_empty": True}},
            ]
        }
        try:
            response = _query_database(IDEA_PIPELINE_DB_ID, {"filter": filters})
            all_results.extend(response.get("results", []))
        except Exception:
            pass

    ideas = []
    for page in all_results:
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "source": "idea_pipeline",
        })
    return ideas


def get_library_posts_with_draft_id(statuses: list[str]) -> list[dict]:
    """
    Query Long-Form Post Library for posts matching given statuses that have a Typefully Draft ID.
    """
    all_results = []
    for status in statuses:
        filters = {
            "and": [
                {"property": "Status", "select": {"equals": status}},
                {"property": "Typefully Draft ID", "rich_text": {"is_not_empty": True}},
            ]
        }
        try:
            response = _query_database(LONGFORM_POST_DB_ID, {"filter": filters})
            all_results.extend(response.get("results", []))
        except Exception:
            pass

    posts = []
    for page in all_results:
        props = page["properties"]
        posts.append({
            "id": page["id"],
            "idea": _get_title(props.get("Post Title", {})),
            "status": _get_select(props.get("Status", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "source": "library",
        })
    return posts


# ── Sync logic ─────────────────────────────────────────────────────────────

def sync_typefully_to_notion(dry_run: bool = False) -> dict:
    """
    Direction 1: Typefully -> Notion.

    Check Approved/Scheduled items with Typefully Draft IDs.
    Update Notion status based on Typefully draft status.
    """
    print("\n--- Direction 1: Typefully -> Notion ---")

    # Gather entries from both databases
    ideas = get_ideas_with_draft_id(["Approved", "Scheduled"])
    library = get_library_posts_with_draft_id(["Approved", "Scheduled"])
    entries = ideas + library

    if not entries:
        print("  No Approved/Scheduled entries with Typefully Draft IDs found.")
        return {"published": 0, "scheduled": 0, "unchanged": 0, "errors": 0}

    print(f"  Found {len(entries)} entries to check against Typefully.\n")

    published = 0
    scheduled = 0
    unchanged = 0
    errors = 0

    for entry in entries:
        title = entry["idea"] or "(untitled)"
        draft_id = entry["typefully_draft_id"].strip()
        notion_status = entry["status"]
        source = entry["source"]

        if not draft_id:
            continue

        draft = get_typefully_draft(draft_id)
        if draft is None:
            errors += 1
            continue

        tf_status = draft.get("status", "unknown")

        if tf_status == "published" and notion_status != "Published":
            if dry_run:
                print(f"  [DRY RUN] Would update to Published: {title} (was {notion_status})")
            else:
                print(f"  Updating to Published: {title} (was {notion_status})")
                if source == "idea_pipeline":
                    update_idea_status(entry["id"], "Published")
                else:
                    update_longform_post(entry["id"], status="Published")
            published += 1

        elif tf_status == "scheduled" and notion_status != "Scheduled":
            if dry_run:
                print(f"  [DRY RUN] Would update to Scheduled: {title} (was {notion_status})")
            else:
                print(f"  Updating to Scheduled: {title} (was {notion_status})")
                if source == "idea_pipeline":
                    update_idea_status(entry["id"], "Scheduled")
                else:
                    update_longform_post(entry["id"], status="Scheduled")
            scheduled += 1

        else:
            print(f"  No change: {title} (Notion={notion_status}, Typefully={tf_status})")
            unchanged += 1

    return {"published": published, "scheduled": scheduled, "unchanged": unchanged, "errors": errors}


def sync_notion_to_typefully(dry_run: bool = False) -> dict:
    """
    Direction 2: Notion -> Typefully.

    For Approved entries with a Typefully Draft ID, schedule the draft on Typefully
    and update Notion status to Scheduled.
    """
    print("\n--- Direction 2: Notion -> Typefully ---")

    ideas = get_ideas_with_draft_id(["Approved"])
    library = get_library_posts_with_draft_id(["Approved"])
    entries = ideas + library

    if not entries:
        print("  No Approved entries with Typefully Draft IDs to schedule.")
        return {"scheduled": 0, "failed": 0}

    print(f"  Found {len(entries)} Approved entries to schedule on Typefully.\n")

    scheduled = 0
    failed = 0

    for entry in entries:
        title = entry["idea"] or "(untitled)"
        draft_id = entry["typefully_draft_id"].strip()
        source = entry["source"]

        if not draft_id:
            continue

        if dry_run:
            print(f"  [DRY RUN] Would schedule on Typefully: {title} (draft {draft_id})")
            scheduled += 1
            continue

        print(f"  Scheduling on Typefully: {title} (draft {draft_id})")
        success = schedule_typefully_draft(draft_id)

        if success:
            print(f"    -> Scheduled on Typefully")
            if source == "idea_pipeline":
                update_idea_status(entry["id"], "Scheduled")
            else:
                update_longform_post(entry["id"], status="Scheduled")
            print(f"    -> Notion updated to 'Scheduled'")
            scheduled += 1
        else:
            print(f"    -> Failed to schedule on Typefully")
            failed += 1

    return {"scheduled": scheduled, "failed": failed}


TAG_TO_STATUS = {
    "qc-review": "QC Review",
    "ready-for-review": "Ready for Review",
    "ready-to-post": "Approved",
    "scheduled": "Scheduled",
}

# Status hierarchy — only sync forward, never backward
STATUS_ORDER = ["New", "Triggered", "Drafting", "QC Review", "Ready for Review", "Approved", "Scheduled", "Published"]


def _status_rank(status: str) -> int:
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


def sync_tags_to_notion(dry_run: bool = False) -> dict:
    """
    Direction 3: Typefully tags → Notion status.

    Maps Typefully tags to Notion statuses:
      qc-review       → QC Review
      ready-for-review → Ready for Review
      ready-to-post    → Approved
      scheduled        → Scheduled

    Only updates forward (never moves status backward).
    """
    print("\n--- Direction 3: Typefully tags -> Notion status ---")

    from tools.typefully_client import list_drafts

    synced = 0
    for tag, target_status in TAG_TO_STATUS.items():
        # Check both draft and scheduled statuses
        all_drafts = []
        for tf_status in ["draft", "scheduled"]:
            try:
                all_drafts.extend(list_drafts(tag=[tag], status=tf_status))
            except Exception:
                pass

        # Deduplicate by ID
        seen = set()
        drafts = []
        for d in all_drafts:
            did = d.get("id")
            if did and did not in seen:
                seen.add(did)
                drafts.append(d)

        if not drafts:
            continue

        print(f"  Tag '{tag}': {len(drafts)} draft(s)")

        for draft in drafts:
            draft_id = str(draft.get("id", ""))
            if not draft_id:
                continue

            try:
                body = {
                    "filter": {
                        "property": "Typefully Draft ID",
                        "rich_text": {"equals": draft_id},
                    },
                    "page_size": 1,
                }
                response = _query_database(IDEA_PIPELINE_DB_ID, body)
                results = response.get("results", [])
                if not results:
                    continue

                page = results[0]
                current_status = _get_select(page["properties"].get("Status", {}))
                idea_title = _get_title(page["properties"].get("Idea", {}))

                # Only update forward
                if _status_rank(target_status) > _status_rank(current_status):
                    if dry_run:
                        print(f"    [DRY] {idea_title[:50]}: {current_status} → {target_status}")
                    else:
                        update_idea_status(page["id"], target_status)
                        print(f"    {idea_title[:50]}: {current_status} → {target_status}")
                    synced += 1
            except Exception:
                continue

    return {"synced": synced}


def run_sync(dry_run: bool = False) -> dict:
    """Run both sync directions once and print summary."""
    print(f"{'='*60}")
    print(f"TYPEFULLY SYNC {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")

    # Direction 1: Typefully -> Notion
    tf_to_notion = sync_typefully_to_notion(dry_run=dry_run)

    # Direction 2: Notion -> Typefully (scheduling)
    notion_to_tf = sync_notion_to_typefully(dry_run=dry_run)

    # Direction 3 removed — no more Typefully tags. Notion is the single source of truth.

    # Summary
    print(f"\n{'='*60}")
    print(f"SYNC SUMMARY {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"  Typefully -> Notion:")
    print(f"    Published:  {tf_to_notion['published']}")
    print(f"    Scheduled:  {tf_to_notion['scheduled']}")
    print(f"    Unchanged:  {tf_to_notion['unchanged']}")
    print(f"    Errors:     {tf_to_notion['errors']}")
    print(f"  Notion -> Typefully:")
    print(f"    Scheduled:  {notion_to_tf['scheduled']}")
    print(f"    Failed:     {notion_to_tf['failed']}")
    print(f"{'='*60}")

    return {"typefully_to_notion": tf_to_notion, "notion_to_typefully": notion_to_tf, "updated": tf_to_notion.get("published", 0) + tf_to_notion.get("scheduled", 0)}


def run_poll(dry_run: bool = False):
    """Run sync every POLL_INTERVAL seconds continuously."""
    print(f"Typefully Sync — Poll Mode (every {POLL_INTERVAL // 60}m)")
    print("  Press Ctrl+C to stop.\n")

    while True:
        try:
            run_sync(dry_run=dry_run)
            print(f"\n[POLL] Sleeping {POLL_INTERVAL // 60}m...")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nSync stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            traceback.print_exc()
            time.sleep(POLL_INTERVAL)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Two-way sync between Typefully draft status and Notion Idea Pipeline",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run both sync directions once",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Run sync every 5 minutes continuously",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Notion or Typefully",
    )
    args = parser.parse_args()

    if args.poll:
        run_poll(dry_run=args.dry_run)
    elif args.sync:
        run_sync(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
