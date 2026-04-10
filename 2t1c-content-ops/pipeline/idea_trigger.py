"""
Idea Trigger — Move ready ideas from "New" to "Triggered" in the Idea Pipeline.

An idea is "ready to trigger" when it has:
  - Assigned Formats (multi_select is not empty)
  - Either a Content Angle OR an Extraction Plan (rich_text not empty)

Usage:
    python -m pipeline.idea_trigger                # trigger all ready ideas
    python -m pipeline.idea_trigger --dry-run      # preview without changing anything
    python -m pipeline.idea_trigger --limit 10     # max ideas to trigger
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.notion_client import (
    IDEA_PIPELINE_DB_ID,
    _query_database,
    _get_title,
    _get_rich_text,
    _get_select,
    _get_multi_select,
    update_idea_status,
)


def get_new_ideas() -> list[dict]:
    """Query the Idea Pipeline for all ideas with Status='New'."""
    filters = {"property": "Status", "select": {"equals": "New"}}
    response = _query_database(IDEA_PIPELINE_DB_ID, {"filter": filters})

    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "extraction_plan": _get_rich_text(props.get("Extraction Plan", {})),
        })
    return ideas


def check_readiness(idea: dict) -> tuple[bool, list[str]]:
    """
    Check if an idea is ready to trigger.

    Returns (is_ready, list_of_missing_reasons).
    """
    missing = []

    if not idea["assigned_formats"]:
        missing.append("no Assigned Formats")

    has_angle = bool(idea["content_angle"].strip())
    has_plan = bool(idea["extraction_plan"].strip())

    if not has_angle and not has_plan:
        missing.append("no Content Angle and no Extraction Plan")

    return (len(missing) == 0, missing)


def run_trigger(dry_run: bool = False, limit: int | None = None) -> dict:
    """
    Main trigger logic. Returns a summary dict.
    """
    print("Fetching ideas with Status='New'...")
    ideas = get_new_ideas()

    if not ideas:
        print("  No ideas with Status='New' found.")
        return {"triggered": 0, "skipped": 0, "total": 0}

    if limit:
        ideas = ideas[:limit]

    print(f"  Found {len(ideas)} idea(s) to evaluate.\n")

    triggered = 0
    skipped = 0
    skip_reasons: list[str] = []

    for idea in ideas:
        title = idea["idea"] or "(untitled)"
        is_ready, missing = check_readiness(idea)

        if is_ready:
            if dry_run:
                print(f"  [DRY RUN] Would trigger: {title}")
                print(f"             Formats: {', '.join(idea['assigned_formats'])}")
            else:
                print(f"  Triggering: {title}")
                print(f"    Formats: {', '.join(idea['assigned_formats'])}")
                update_idea_status(idea["id"], "Triggered")
                print(f"    -> Status updated to 'Triggered'")
            triggered += 1
        else:
            reason_str = "; ".join(missing)
            print(f"  Skipping: {title} ({reason_str})")
            skip_reasons.append(f"{title}: {reason_str}")
            skipped += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY {'(DRY RUN) ' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"  Evaluated: {len(ideas)}")
    print(f"  Triggered: {triggered}")
    print(f"  Skipped:   {skipped}")
    if skip_reasons:
        print(f"\n  Skip reasons:")
        for reason in skip_reasons:
            print(f"    - {reason}")
    print(f"{'='*60}")

    return {"triggered": triggered, "skipped": skipped, "total": len(ideas)}


def main():
    parser = argparse.ArgumentParser(
        description="Move ready ideas from 'New' to 'Triggered' in the Idea Pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be triggered without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of ideas to trigger",
    )
    args = parser.parse_args()

    run_trigger(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
