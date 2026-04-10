"""
Typefully → Notion One-Way Sync

Polls Typefully for tag changes on drafts and updates the corresponding
Notion entry's status to match. Typefully is the authority, Notion follows.

Tag → Status mapping:
    qc-review        → QC Review
    ready-for-review → Ready for Review
    ready-to-post    → Approved
    in-progress      → Drafting
    needs-media      → Needs Media

Usage:
    python -m pipeline.typefully_notion_sync --once       # one sync pass
    python -m pipeline.typefully_notion_sync --poll        # continuous (2 min)
    python -m pipeline.typefully_notion_sync --dry-run     # preview without updating Notion
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.typefully_client import list_drafts
from tools.notion_client import (
    update_idea_status,
    update_longform_post,
    _query_database,
    IDEA_PIPELINE_DB_ID,
    LONGFORM_POST_DB_ID,
    _get_rich_text,
)

POLL_INTERVAL = 120  # 2 minutes

# ── Tag → Status Mapping ───────────────────────────────────────────────────

TAG_TO_STATUS = {
    "qc-review": "QC Review",
    "ready-for-review": "Ready for Review",
    "ready-to-post": "Approved",
    "in-progress": "Drafting",
    "needs-media": "Needs Media",
}

# Tags we care about syncing (in priority order — highest priority first)
# If a draft has multiple tags, the highest priority one wins
SYNC_TAGS = ["ready-to-post", "ready-for-review", "qc-review", "needs-media", "in-progress"]

# Cache: draft_id → last known synced tag
_last_synced: dict[str, str] = {}


# ── Notion Lookup ──────────────────────────────────────────────────────────

def _find_notion_entry_by_draft_id(draft_id: str) -> dict | None:
    """
    Find the Notion page (Idea Pipeline or Library) that has this Typefully Draft ID.
    Returns {id, source} or None.
    """
    draft_id_str = str(draft_id)

    # Check Long-Form Post Library first (more likely)
    try:
        response = _query_database(LONGFORM_POST_DB_ID, {
            "filter": {
                "property": "Typefully Draft ID",
                "rich_text": {"equals": draft_id_str},
            }
        })
        results = response.get("results", [])
        if results:
            return {"id": results[0]["id"], "source": "library"}
    except Exception:
        pass

    # Check Idea Pipeline
    try:
        response = _query_database(IDEA_PIPELINE_DB_ID, {
            "filter": {
                "property": "Typefully Draft ID",
                "rich_text": {"equals": draft_id_str},
            }
        })
        results = response.get("results", [])
        if results:
            return {"id": results[0]["id"], "source": "idea_pipeline"}
    except Exception:
        pass

    return None


# ── Sync Logic ─────────────────────────────────────────────────────────────

def _get_primary_tag(tags: list[str]) -> str | None:
    """Pick the highest-priority sync tag from a draft's tag list."""
    for tag in SYNC_TAGS:
        if tag in tags:
            return tag
    return None


def sync_once(dry_run: bool = False) -> list[dict]:
    """
    One sync pass: fetch all Typefully drafts, compare tags to last known
    state, update Notion for any changes.
    """
    print("Typefully → Notion Sync")
    print("=" * 50)

    # 1. Fetch all drafts from Typefully
    print("  Fetching Typefully drafts...")
    try:
        drafts = list_drafts(status="draft")
    except Exception as e:
        print(f"  ERROR: Could not fetch Typefully drafts: {e}")
        return []

    print(f"  Found {len(drafts)} drafts")

    changes = []

    for draft in drafts:
        draft_id = str(draft.get("id", ""))
        if not draft_id:
            continue

        tags = draft.get("tags", [])
        title = draft.get("draft_title", "") or draft.get("preview", "")[:50]
        primary_tag = _get_primary_tag(tags)

        if not primary_tag:
            continue  # No sync-relevant tag on this draft

        # Check if tag changed since last sync
        last_tag = _last_synced.get(draft_id)
        if last_tag == primary_tag:
            continue  # No change

        target_status = TAG_TO_STATUS.get(primary_tag)
        if not target_status:
            continue

        print(f"\n  [{primary_tag}] {title[:50]}")
        print(f"    Tag: {last_tag or '(new)'} → {primary_tag}")
        print(f"    Notion status target: {target_status}")

        # Find the Notion entry
        entry = _find_notion_entry_by_draft_id(draft_id)
        if not entry:
            print(f"    SKIP: No Notion entry found for draft {draft_id}")
            _last_synced[draft_id] = primary_tag  # Don't keep retrying
            continue

        notion_id = entry["id"]
        source = entry["source"]
        print(f"    Notion: {notion_id[:12]}... ({source})")

        if dry_run:
            print(f"    DRY RUN: would update Notion to '{target_status}'")
        else:
            try:
                if source == "idea_pipeline":
                    update_idea_status(notion_id, target_status)
                else:
                    update_longform_post(notion_id, status=target_status)
                print(f"    Notion updated → {target_status}")
            except Exception as e:
                print(f"    ERROR: Notion update failed: {e}")
                continue

        _last_synced[draft_id] = primary_tag
        changes.append({
            "draft_id": draft_id,
            "title": title[:50],
            "tag": primary_tag,
            "status": target_status,
            "notion_id": notion_id,
            "source": source,
        })

    # Summary
    if changes:
        print(f"\n{'=' * 50}")
        print(f"SYNCED: {len(changes)} change(s)")
        for c in changes:
            print(f"  {c['title'][:40]:40s} → {c['status']}")
    else:
        print("  No changes to sync.")

    print(f"{'=' * 50}")
    return changes


def run_poll(dry_run: bool = False):
    """Continuously poll and sync."""
    print(f"Typefully → Notion Sync — Polling every {POLL_INTERVAL}s")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            sync_once(dry_run=dry_run)
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nSync stopped.")
            break
        except Exception as e:
            print(f"[SYNC ERROR] {e}")
            time.sleep(POLL_INTERVAL)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Typefully → Notion one-way sync")
    parser.add_argument("--once", action="store_true", help="Run one sync pass")
    parser.add_argument("--poll", action="store_true", help="Continuously poll (2 min)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating Notion")
    args = parser.parse_args()

    if args.poll:
        run_poll(dry_run=args.dry_run)
    elif args.once or args.dry_run:
        sync_once(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
