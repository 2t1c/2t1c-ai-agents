"""
Ellis Runner — Automated QC gate for the GeniusGTX content pipeline.

Polls for drafts in "QC Review" status (Notion) or tagged "qc-review" (Typefully),
runs Ellis's 12-point rubric evaluation, and either:
  - PASS → applies direct fixes, promotes to "Ready for Review", tags "ready-for-review"
  - FAIL → sends feedback to Maya for revision, re-evaluates (max 2 rounds)

Usage:
    python -m pipeline.ellis_runner --once       # process all QC Review items once
    python -m pipeline.ellis_runner --poll       # continuous polling every 2 minutes
    python -m pipeline.ellis_runner --dry-run    # preview without changes
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

from agents.ellis.agent import evaluate, apply_direct_fixes
from agents.maya.agent import revise_post
from tools.notion_client import (
    _query_database,
    IDEA_PIPELINE_DB_ID,
    update_idea_status,
    _get_title,
    _get_rich_text,
    _get_select,
    _get_multi_select,
)
from tools.typefully_client import (
    get_draft,
    edit_draft_text,
    add_tag_to_draft,
    list_drafts,
)

POLL_INTERVAL = 120  # 2 minutes
MAX_REVISION_ROUNDS = 2


# ── Notion queries ─────────────────────────────────────────────────────────

def get_qc_review_ideas() -> list[dict]:
    """Get all ideas with Status='QC Review' from the Idea Pipeline."""
    body = {
        "filter": {"property": "Status", "select": {"equals": "QC Review"}},
        "page_size": 50,
    }
    response = _query_database(IDEA_PIPELINE_DB_ID, body)
    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "source_url": props.get("Source URL", {}).get("url", "") or "",
        })
    return ideas


def get_qc_drafts_from_typefully() -> list[dict]:
    """Get drafts tagged 'qc-review' from Typefully that might not be in Notion yet."""
    try:
        drafts = list_drafts(tag=["qc-review"], status="draft")
        return drafts
    except Exception as e:
        print(f"  Warning: Could not fetch Typefully qc-review drafts: {e}")
        return []


# ── Draft text extraction ──────────────────────────────────────────────────

def get_draft_text(draft_id: str) -> str:
    """Get the full text of a Typefully draft."""
    try:
        draft = get_draft(draft_id)
        # Extract text from posts array
        posts = draft.get("posts", [])
        if not posts:
            # Try platforms.x.posts
            platforms = draft.get("platforms", {})
            x_data = platforms.get("x", {})
            posts = x_data.get("posts", [])

        text_parts = []
        for post in posts:
            if isinstance(post, dict):
                text_parts.append(post.get("text", ""))
            elif isinstance(post, str):
                text_parts.append(post)

        return "\n\n---\n\n".join(text_parts) if text_parts else str(draft)
    except Exception as e:
        print(f"    Error fetching draft {draft_id}: {e}")
        return ""


# ── Core QC flow ───────────────────────────────────────────────────────────

def process_qc_item(
    idea: dict,
    dry_run: bool = False,
) -> dict:
    """
    Run Ellis QC on a single item. Handles the full pass/fail/revise loop.

    Returns dict with: idea_id, verdict, score, rounds, action_taken
    """
    idea_name = idea["idea"][:60]
    draft_id = idea.get("typefully_draft_id", "")
    format_name = idea["assigned_formats"][0] if idea["assigned_formats"] else ""
    source_url = idea.get("source_url", "")

    if not draft_id:
        print(f"  Skip: {idea_name} — no Typefully Draft ID")
        return {"idea_id": idea["id"], "verdict": "skip", "reason": "no draft ID"}

    # Get draft text
    post_text = get_draft_text(draft_id)
    if not post_text:
        print(f"  Skip: {idea_name} — could not fetch draft text")
        return {"idea_id": idea["id"], "verdict": "skip", "reason": "empty draft"}

    print(f"\n  Evaluating: {idea_name}")
    print(f"    Format: {format_name} | Draft: {draft_id}")

    # Revision loop
    current_text = post_text
    for round_num in range(1, MAX_REVISION_ROUNDS + 2):  # +1 for initial, +1 for final check
        print(f"    Round {round_num}: Running Ellis evaluation...")

        # Evaluate
        result = evaluate(
            post_text=current_text,
            format_name=format_name,
            source_url=source_url,
            has_media=True,  # Assume media attached at this stage
        )

        score = result.get("score", 0)
        verdict = result.get("verdict", "FAIL")
        failures = result.get("failures", [])
        direct_fixes = result.get("direct_fixes", [])
        feedback = result.get("feedback", "")

        print(f"    Result: {verdict} ({score}/12)")

        if verdict == "PASS":
            # Apply direct fixes if any
            if direct_fixes and not dry_run:
                fixed_text, changes = apply_direct_fixes(current_text, direct_fixes)
                if changes:
                    print(f"    Applying {len(changes)} direct fix(es):")
                    for c in changes:
                        print(f"      - {c}")
                    # Update Typefully draft
                    try:
                        posts = [{"text": t.strip()} for t in fixed_text.split("\n\n---\n\n") if t.strip()]
                        if not posts:
                            posts = [{"text": fixed_text}]
                        edit_draft_text(draft_id, posts)
                    except Exception as e:
                        print(f"    Warning: Could not update draft text: {e}")

            # Promote to Ready for Review
            if not dry_run:
                update_idea_status(idea["id"], "Ready for Review")
                try:
                    add_tag_to_draft(draft_id, "ready-for-review")
                except Exception:
                    pass
                print(f"    ✅ PASSED — promoted to Ready for Review")
            else:
                print(f"    [DRY] Would promote to Ready for Review")

            return {
                "idea_id": idea["id"],
                "verdict": "PASS",
                "score": score,
                "rounds": round_num,
                "fixes_applied": len(direct_fixes) if direct_fixes else 0,
            }

        else:
            # FAIL — check if we have revision rounds left
            if round_num > MAX_REVISION_ROUNDS:
                # Max rounds exceeded — escalate to Toan with note
                if not dry_run:
                    update_idea_status(idea["id"], "Ready for Review")
                    try:
                        add_tag_to_draft(draft_id, "ready-for-review")
                        add_tag_to_draft(draft_id, "qc-escalated")
                    except Exception:
                        pass
                print(f"    ⚠️ ESCALATED after {MAX_REVISION_ROUNDS} rounds — sending to Toan with QC notes")
                return {
                    "idea_id": idea["id"],
                    "verdict": "ESCALATED",
                    "score": score,
                    "rounds": round_num,
                    "failures": failures,
                }

            # Try revision
            if failures:
                for f in failures[:3]:
                    print(f"      ❌ {f[:80]}")

            if dry_run:
                print(f"    [DRY] Would send to Maya for revision (round {round_num})")
                return {
                    "idea_id": idea["id"],
                    "verdict": "FAIL",
                    "score": score,
                    "rounds": round_num,
                    "failures": failures,
                }

            # Apply direct fixes first
            if direct_fixes:
                fixed_text, changes = apply_direct_fixes(current_text, direct_fixes)
                if changes:
                    current_text = fixed_text
                    print(f"    Applied {len(changes)} direct fix(es), re-evaluating...")
                    continue  # Re-evaluate without counting as a Maya revision

            # Send to Maya for revision
            print(f"    Sending to Maya for revision (feedback: {feedback[:80]}...)")
            try:
                revised = revise_post(
                    original_post=current_text,
                    feedback=feedback,
                )
                if revised and revised != current_text:
                    current_text = revised
                    # Update Typefully draft with revised text
                    try:
                        posts = [{"text": t.strip()} for t in current_text.split("\n\n---\n\n") if t.strip()]
                        if not posts:
                            posts = [{"text": current_text}]
                        edit_draft_text(draft_id, posts)
                    except Exception as e:
                        print(f"      Warning: Could not update draft: {e}")
                    print(f"    Maya revised — re-evaluating...")
                else:
                    print(f"    Maya returned no changes — escalating")
                    break
            except Exception as e:
                print(f"    Maya revision failed: {e}")
                break

    # If we get here, something went wrong — escalate
    if not dry_run:
        update_idea_status(idea["id"], "Ready for Review")
    return {
        "idea_id": idea["id"],
        "verdict": "ESCALATED",
        "score": score,
        "rounds": MAX_REVISION_ROUNDS,
    }


# ── Main runner ────────────────────────────────────────────────────────────

def run_once(dry_run: bool = False) -> dict:
    """Process all QC Review items once."""
    print(f"\n{'='*60}")
    print(f"ELLIS QC RUNNER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Get items from Notion
    ideas = get_qc_review_ideas()
    print(f"  Found {len(ideas)} idea(s) in QC Review")

    if not ideas:
        print("  Nothing to review.")
        return {"processed": 0, "passed": 0, "failed": 0, "escalated": 0}

    results = {"processed": 0, "passed": 0, "failed": 0, "escalated": 0}

    for idea in ideas:
        try:
            result = process_qc_item(idea, dry_run=dry_run)
            results["processed"] += 1
            verdict = result.get("verdict", "")
            if verdict == "PASS":
                results["passed"] += 1
            elif verdict == "ESCALATED":
                results["escalated"] += 1
            elif verdict == "FAIL":
                results["failed"] += 1
        except Exception as e:
            print(f"  Error processing {idea['idea'][:40]}: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("QC SUMMARY")
    print(f"{'='*60}")
    print(f"  Processed:  {results['processed']}")
    print(f"  Passed:     {results['passed']}")
    print(f"  Failed:     {results['failed']}")
    print(f"  Escalated:  {results['escalated']}")
    print(f"{'='*60}")

    return results


def run_poll(dry_run: bool = False):
    """Continuously poll for QC Review items."""
    print(f"Ellis QC Runner — Polling Mode (every {POLL_INTERVAL // 60}m)")
    print("  Press Ctrl+C to stop.\n")

    while True:
        try:
            run_once(dry_run=dry_run)
            print(f"\n[POLL] Sleeping {POLL_INTERVAL // 60}m...")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nEllis stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            traceback.print_exc()
            time.sleep(POLL_INTERVAL)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ellis QC Runner — automated quality gate")
    parser.add_argument("--once", action="store_true", help="Process all QC Review items once")
    parser.add_argument("--poll", action="store_true", help="Continuous polling every 2 minutes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    if args.poll:
        run_poll(dry_run=args.dry_run)
    else:
        run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
