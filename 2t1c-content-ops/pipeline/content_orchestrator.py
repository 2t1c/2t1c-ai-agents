"""
Content Orchestrator — Parses Extraction Plans from triggered ideas and creates
Long-Form Post Library entries for each angle.

This is Stage 1 of the autonomous pipeline:
  Kai creates idea → Orchestrator fans out angles → Format Pipeline writes each one

Usage:
    python -m pipeline.content_orchestrator --once              # all triggered ideas with plans
    python -m pipeline.content_orchestrator --idea-id <id>      # specific idea
    python -m pipeline.content_orchestrator --poll               # continuous polling
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.notion_client import (
    get_triggered_ideas_with_plans,
    get_idea_by_id_full,
    create_longform_from_angle,
    update_idea_status,
    get_library_entries_by_status,
)

POLL_INTERVAL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Extraction Plan parser
# ---------------------------------------------------------------------------

def parse_extraction_plan(plan_text: str) -> list[dict]:
    """
    Parse Kai's structured Extraction Plan into a list of angle dicts.

    Expected input format:
        ANGLE EXTRACTION:
        1. Straight: brief text here → Format: Tuki QRT
        2. Systems lens: brief text → Format: Thread
        3. Contrarian: N/A
        ...
        PRIORITY ORDER: [1, 5, 6, 2, 3, 8]
        TOTAL POSTS: 5

    Returns list of dicts:
        [{"angle_number": 1, "angle_name": "Straight", "brief": "...",
          "format": "Tuki QRT", "priority": 1}, ...]
    """
    if not plan_text or not plan_text.strip():
        return []

    # Parse angle lines (skip N/A)
    angle_pattern = re.compile(
        r"(\d+)\.\s*([\w][\w\s]*?):\s*(.+?)\s*→\s*Format:\s*(.+?)$",
        re.MULTILINE,
    )
    angles = []
    for match in angle_pattern.finditer(plan_text):
        num, name, brief, fmt = match.groups()
        brief = brief.strip()
        if "N/A" in brief:
            continue
        angles.append({
            "angle_number": int(num),
            "angle_name": name.strip(),
            "brief": brief,
            "format": fmt.strip(),
        })

    # Parse priority order
    priority_match = re.search(r"PRIORITY ORDER:\s*\[?([0-9,\s]+)\]?", plan_text)
    if priority_match:
        try:
            order = [int(x.strip()) for x in priority_match.group(1).split(",") if x.strip()]
            # Assign priority based on position in order list
            for angle in angles:
                if angle["angle_number"] in order:
                    angle["priority"] = order.index(angle["angle_number"]) + 1
                else:
                    angle["priority"] = len(order) + 1
        except ValueError:
            # Fallback: use angle number as priority
            for i, angle in enumerate(angles):
                angle["priority"] = i + 1
    else:
        for i, angle in enumerate(angles):
            angle["priority"] = i + 1

    return angles


def parse_content_map(map_text: str) -> list[dict]:
    """
    Parse Kai's Content Map into time slot assignments.

    Expected input format:
        CONTENT MAP — Title
        Source: URL
        Total: N posts

        T+0: Tuki QRT — Straight — description
        T+Same day: Stat Bomb — Human impact — description
        T+Day 1: Thread — Systems lens — description

    Returns list of dicts:
        [{"slot": "T+0", "format": "Tuki QRT", "angle": "Straight", "description": "..."}, ...]
    """
    if not map_text or not map_text.strip():
        return []

    slot_pattern = re.compile(
        r"(T\+[\w\s\-–]+?):\s*(.+?)\s*[—–-]+\s*(.+?)\s*[—–-]+\s*(.+?)$",
        re.MULTILINE,
    )
    slots = []
    for match in slot_pattern.finditer(map_text):
        slot, fmt, angle, desc = match.groups()
        slots.append({
            "slot": slot.strip(),
            "format": fmt.strip(),
            "angle": angle.strip(),
            "description": desc.strip(),
        })

    return slots


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def orchestrate_idea(idea: dict) -> list[dict]:
    """
    Parse an idea's Extraction Plan and create Library entries for each angle.

    1. Parse Extraction Plan → list of angles
    2. Parse Content Map → match slots to angles
    3. Check for existing entries (prevent duplicates)
    4. Create Long-Form Post Library entry per angle
    5. Update parent idea → "Drafting"
    """
    idea_id = idea["id"]
    idea_title = idea["idea"]
    plan_text = idea.get("extraction_plan", "")
    map_text = idea.get("content_map", "")

    print(f"\n--- Orchestrating: {idea_title[:60]} ---")
    print(f"    Idea ID: {idea_id}")

    # Step 1: Parse Extraction Plan
    angles = parse_extraction_plan(plan_text)
    if not angles:
        print("    ERROR: No parseable angles in Extraction Plan. Skipping.")
        return []

    print(f"    Found {len(angles)} angles: {[a['angle_name'] for a in angles]}")

    # Step 2: Parse Content Map for slot assignments
    slots = parse_content_map(map_text)
    slot_lookup = {}
    for slot in slots:
        # Match by angle name (case-insensitive)
        slot_lookup[slot["angle"].lower()] = slot["slot"]

    # Step 3: Check for existing entries to prevent duplicates
    existing = get_library_entries_by_status("Angle Found")
    existing_angles = set()
    for entry in existing:
        # Check if entry's source idea matches this idea
        # We check by title match as a heuristic (relation check would need extra API call)
        if entry.get("content_angle", "").strip():
            existing_angles.add(f"{idea_title}::{entry['content_angle']}")

    # Step 4: Create Library entries
    created = []
    for angle in angles:
        # Build title: "Angle Name — Idea Title"
        entry_title = f"{angle['angle_name']} — {idea_title[:80]}"
        content_angle = f"{angle['angle_name']}: {angle['brief']}"

        # Duplicate check
        dedup_key = f"{idea_title}::{content_angle}"
        if dedup_key in existing_angles:
            print(f"    SKIP (duplicate): {angle['angle_name']}")
            continue

        # Get publish slot from Content Map
        publish_slot = slot_lookup.get(angle["angle_name"].lower(), "")

        print(f"    Creating: {angle['angle_name']} → {angle['format']} (P{angle['priority']}, {publish_slot or 'no slot'})")

        try:
            page = create_longform_from_angle(
                title=entry_title,
                source_idea_id=idea_id,
                assigned_format=angle["format"],
                content_angle=content_angle,
                source_url=idea.get("source_url", ""),
                source_account=idea.get("source_account", ""),
                publish_slot=publish_slot,
                urgency=idea.get("urgency", ""),
                priority=angle["priority"],
                parent_idea_title=idea_title,
                parent_idea_notes=idea.get("notes", ""),
            )
            created.append({
                "id": page["id"],
                "angle": angle["angle_name"],
                "format": angle["format"],
                "priority": angle["priority"],
                "slot": publish_slot,
            })
        except Exception as e:
            print(f"    ERROR creating {angle['angle_name']}: {e}")

    # Step 5: Update parent idea → Drafting
    if created:
        update_idea_status(idea_id, "Drafting")
        print(f"    Parent status → Drafting")
        print(f"    Created {len(created)}/{len(angles)} Library entries")
    else:
        print("    No entries created (all duplicates or errors)")

    return created


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_once(idea_id: str | None = None):
    """Process a single idea or all triggered ideas with Extraction Plans."""
    if idea_id:
        idea = get_idea_by_id_full(idea_id)
        if not idea:
            print(f"Idea {idea_id} not found.")
            return
        if not idea.get("extraction_plan"):
            print(f"Idea {idea_id} has no Extraction Plan.")
            return
        results = orchestrate_idea(idea)
        total = len(results)
    else:
        ideas = get_triggered_ideas_with_plans()
        if not ideas:
            print("No triggered ideas with Extraction Plans found.")
            return
        print(f"Found {len(ideas)} triggered idea(s) with Extraction Plans")
        results = []
        for idea in ideas:
            entries = orchestrate_idea(idea)
            results.extend(entries)
        total = len(results)

    print(f"\n=== Orchestrator Done: {total} Library entries created ===")
    for r in results:
        print(f"  [{r['format']}] {r['angle']} (P{r['priority']}) → {r.get('slot', 'no slot')}")


def run_poll():
    """Continuously poll for triggered ideas with Extraction Plans."""
    print(f"Content Orchestrator — polling every {POLL_INTERVAL_SECONDS}s")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            ideas = get_triggered_ideas_with_plans()
            if ideas:
                print(f"[POLL] Found {len(ideas)} triggered idea(s) with Extraction Plans")
                for idea in ideas:
                    orchestrate_idea(idea)
            else:
                print("[POLL] No triggered ideas with plans. Sleeping...")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nOrchestrator stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Content Orchestrator — fan out Extraction Plans to Library entries")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--idea-id", type=str, help="Process a specific idea by Notion page ID")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for triggered ideas")
    args = parser.parse_args()

    if args.poll:
        run_poll()
    elif args.once or args.idea_id:
        run_once(idea_id=args.idea_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
