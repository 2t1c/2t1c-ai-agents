"""
Backlog Sweep — Lane 2: Catch ideas that fell through the cracks.

Runs daily to ensure no good idea rots in "New" forever. For each old idea:
  - Missing angle/formats? → Claude enriches it
  - Has everything? → Auto-trigger
  - Stale/duplicate? → Kill it
  - Evergreen gold? → Priority trigger

Also sweeps other stuck statuses:
  - "Triggered" for >3 days with no draft → re-trigger or investigate
  - "QC Review" for >2 days → flag for attention
  - "Drafting" for >2 days → likely stuck, flag it

Usage:
    python -m pipeline.backlog_sweep                # sweep all stuck ideas
    python -m pipeline.backlog_sweep --dry-run      # preview without changes
    python -m pipeline.backlog_sweep --enrich       # also enrich ideas missing angles
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.notion_client import (
    _query_database,
    IDEA_PIPELINE_DB_ID,
    update_idea_status,
    _get_title,
    _get_rich_text,
    _get_select,
    _get_multi_select,
)

# For enrichment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
MODEL = "claude-sonnet-4-6"

# Thresholds
STALE_DAYS_NEW = 3       # Ideas in "New" for this long get swept
STALE_DAYS_TRIGGERED = 3  # Triggered but no draft after this long
STALE_DAYS_DRAFTING = 2   # Stuck in drafting
STALE_DAYS_QC = 2         # Stuck in QC review


def get_ideas_by_status(status: str) -> list[dict]:
    """Get all ideas with a given status, including created time."""
    body = {
        "filter": {"property": "Status", "select": {"equals": status}},
        "page_size": 100,
    }
    response = _query_database(IDEA_PIPELINE_DB_ID, body)
    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "extraction_plan": _get_rich_text(props.get("Extraction Plan", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "created_time": page.get("created_time", ""),
        })
    return ideas


def is_older_than(created_time: str, days: int) -> bool:
    """Check if a created_time string is older than N days."""
    if not created_time:
        return True
    try:
        created = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
        cutoff = datetime.now(created.tzinfo) - timedelta(days=days)
        return created < cutoff
    except Exception:
        return True


def enrich_idea(idea: dict) -> dict | None:
    """Use Claude to generate a Content Angle and suggest formats for an idea missing them."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": f"""You are a content strategist for GeniusGTX, an X/Twitter account covering ancient civilizations, systemic shifts, hidden figures, cognitive science, business strategy, and geopolitics.

This idea needs a content angle and format assignment:

IDEA: {idea['idea']}
URGENCY: {idea.get('urgency', 'unknown')}

Respond in JSON only:
{{
    "content_angle": "1-2 sentence specific angle/spin for this idea",
    "assigned_formats": ["format1", "format2"],
    "rationale": "why this angle and these formats"
}}

Available formats: Tuki QRT, Bark QRT, Commentary Post, Stat Bomb, Explainer, Contrarian Take, Multi-Source Explainer, Thread, Video Clip Post, Clip Commentary, Clip Thread

Pick 2-4 formats that fit best. Return ONLY valid JSON."""}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None


def update_idea_enrichment(idea_id: str, angle: str, formats: list[str]):
    """Update an idea's Content Angle and Assigned Formats in Notion."""
    from notion_client import Client
    notion = Client(auth=NOTION_API_KEY)

    properties = {}
    if angle:
        properties["Content Angle"] = {"rich_text": [{"text": {"content": angle}}]}
    if formats:
        properties["Assigned Formats"] = {"multi_select": [{"name": f} for f in formats]}

    notion.pages.update(page_id=idea_id, properties=properties)


def sweep_new_ideas(dry_run: bool = False, enrich: bool = False) -> dict:
    """Sweep ideas stuck in 'New' status."""
    ideas = get_ideas_by_status("New")
    results = {"triggered": 0, "enriched": 0, "killed": 0, "skipped": 0}

    print(f"\n  Sweeping {len(ideas)} ideas in 'New'...")

    for idea in ideas:
        name = idea["idea"][:70]
        has_formats = len(idea["assigned_formats"]) > 0
        has_angle = bool(idea["content_angle"]) or bool(idea["extraction_plan"])
        is_old = is_older_than(idea["created_time"], STALE_DAYS_NEW)

        if has_formats and has_angle:
            # Ready to trigger
            if dry_run:
                print(f"    [DRY] Would trigger: {name}")
            else:
                update_idea_status(idea["id"], "Triggered")
                print(f"    Triggered: {name}")
            results["triggered"] += 1

        elif not has_angle and enrich:
            # Missing angle — enrich it
            print(f"    Enriching: {name}...")
            enrichment = enrich_idea(idea)
            if enrichment and not dry_run:
                update_idea_enrichment(
                    idea["id"],
                    enrichment.get("content_angle", ""),
                    enrichment.get("assigned_formats", []),
                )
                update_idea_status(idea["id"], "Triggered")
                print(f"      → Enriched + Triggered: {enrichment.get('content_angle', '')[:60]}")
                results["enriched"] += 1
            elif enrichment and dry_run:
                print(f"      [DRY] Would enrich: {enrichment.get('content_angle', '')[:60]}")
                results["enriched"] += 1
            else:
                print(f"      Failed to enrich, skipping")
                results["skipped"] += 1
        else:
            if is_old and not has_formats and not has_angle:
                # Old, no formats, no angle — likely low quality
                print(f"    Skipped (missing angle+formats): {name}")
            else:
                print(f"    Skipped (missing {'angle' if not has_angle else 'formats'}): {name}")
            results["skipped"] += 1

    return results


def sweep_stuck_statuses(dry_run: bool = False) -> dict:
    """Flag ideas stuck in intermediate statuses too long."""
    results = {"flagged": 0}

    for status, days, action in [
        ("Triggered", STALE_DAYS_TRIGGERED, "re-check — may need manual attention"),
        ("Drafting", STALE_DAYS_DRAFTING, "writer may have errored"),
    ]:
        try:
            ideas = get_ideas_by_status(status)
        except Exception:
            continue
        stuck = [i for i in ideas if is_older_than(i["created_time"], days)]

        if stuck:
            print(f"\n  ⚠️  {len(stuck)} ideas stuck in '{status}' for >{days} days ({action}):")
            for idea in stuck[:5]:
                print(f"      - {idea['idea'][:70]}")
            if len(stuck) > 5:
                print(f"      ... and {len(stuck) - 5} more")
            results["flagged"] += len(stuck)

    return results


def run_sweep(dry_run: bool = False, enrich: bool = False) -> dict:
    """Run the full backlog sweep."""
    print("=" * 60)
    print(f"BACKLOG SWEEP — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Lane 2a: New ideas
    new_results = sweep_new_ideas(dry_run=dry_run, enrich=enrich)

    # Lane 2b: Stuck statuses
    stuck_results = sweep_stuck_statuses(dry_run=dry_run)

    # Summary
    print(f"\n{'=' * 60}")
    print("SWEEP SUMMARY")
    print(f"{'=' * 60}")
    print(f"  New ideas triggered:  {new_results['triggered']}")
    print(f"  New ideas enriched:   {new_results['enriched']}")
    print(f"  New ideas skipped:    {new_results['skipped']}")
    print(f"  Stuck ideas flagged:  {stuck_results['flagged']}")
    print(f"{'=' * 60}")

    return {**new_results, **stuck_results}


def main():
    parser = argparse.ArgumentParser(description="Backlog sweep — catch stuck ideas")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--enrich", action="store_true", help="Use Claude to enrich ideas missing angles")
    args = parser.parse_args()

    run_sweep(dry_run=args.dry_run, enrich=args.enrich)


if __name__ == "__main__":
    main()
