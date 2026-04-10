"""
QC Pipeline — Ellis's automated quality control loop.

Sits between the format pipeline and the Telegram review bot:
    Format Pipeline → Notion status "QC Review" + Typefully tag "qc-review"
    → Ellis evaluates → PASS or FAIL
    PASS → status "Ready for Review" + tag "ready-for-review" → Telegram bot picks up
    FAIL → Maya revises with Ellis's feedback → edits draft in place → re-evaluate
    Max 3 revision rounds, then escalate to Toan anyway.

Usage:
    python -m pipeline.qc_pipeline --once       # one QC pass
    python -m pipeline.qc_pipeline --poll        # continuous polling (5 min)
    python -m pipeline.qc_pipeline --dry-run     # evaluate without updating anything
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

from agents.ellis.agent import evaluate, apply_direct_fixes
from agents.maya.agent import revise_post
from tools.notion_client import (
    get_library_entries_by_status,
    update_longform_post,
    get_triggered_ideas,
    update_idea_status,
)
from tools.typefully_client import (
    get_draft,
    edit_draft_text,
    add_tag_to_draft,
    enable_sharing,
)

POLL_INTERVAL = 300  # 5 minutes
MAX_REVISION_ROUNDS = 2  # keep it tight — 2 Maya revisions max, then escalate

# Track revision state per draft: draft_id → {round, prev_score, prev_text}
_revision_state: dict[str, dict] = {}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_posts_and_text(draft: dict) -> tuple[list[dict], str]:
    """Extract posts array and combined text from a Typefully draft."""
    platforms = draft.get("platforms", {})
    x_data = platforms.get("x", {})
    posts = x_data.get("posts", [])
    text = "\n\n---\n\n".join(p.get("text", "") for p in posts)
    return posts, text


def _get_format_from_title(title: str) -> str:
    """Guess the format name from the draft title."""
    title_lower = title.lower()
    if "tuki" in title_lower:
        return "Tuki QRT"
    elif "bark" in title_lower:
        return "Bark QRT"
    elif "commentary" in title_lower:
        return "Commentary Post"
    elif "stat bomb" in title_lower:
        return "Stat Bomb"
    elif "explainer" in title_lower:
        return "Explainer"
    elif "thread" in title_lower:
        return "Thread"
    elif "contrarian" in title_lower:
        return "Contrarian Take"
    elif "long-form" in title_lower or "long form" in title_lower:
        return "Long-Form"
    return ""


# ── QC Evaluation + Revision Loop ──────────────────────────────────────────

def qc_draft(
    draft_id: str,
    notion_id: str = "",
    notion_source: str = "library",
    format_name: str = "",
    source_url: str = "",
    dry_run: bool = False,
) -> dict:
    """
    Run Ellis's QC on a single Typefully draft.

    If it fails, triggers Maya to revise and re-evaluates (up to MAX_REVISION_ROUNDS).
    On pass or max rounds, updates Notion + Typefully status.

    Returns the final evaluation result.
    """
    round_num = _revision_counts.get(draft_id, 0)

    # 1. Fetch the draft
    try:
        draft = get_draft(draft_id)
    except Exception as e:
        print(f"    ERROR: Could not fetch draft {draft_id}: {e}")
        return {"verdict": "ERROR", "notes": str(e)}

    title = draft.get("draft_title", "Untitled")
    posts, post_text = _extract_posts_and_text(draft)

    if not post_text:
        print(f"    SKIP: Draft {draft_id} has no text")
        return {"verdict": "SKIP", "notes": "Empty draft"}

    if not format_name:
        format_name = _get_format_from_title(title)

    print(f"\n  [{format_name or 'Unknown'}] {title[:60]}")
    print(f"    Draft: {draft_id} | Round: {round_num + 1}/{MAX_REVISION_ROUNDS}")

    # 2. Check media
    has_media = False
    for post in posts:
        if post.get("media_ids"):
            has_media = True
            break

    # 3. Ellis evaluates
    print("    Ellis evaluating...")
    result = evaluate(post_text, format_name, source_url, has_media=has_media)
    score = result.get("score", 0)
    verdict = result.get("verdict", "FAIL")

    print(f"    Score: {score}/12 → {verdict}")
    if result.get("failures"):
        for f in result["failures"][:3]:
            print(f"      - {f}")

    # 4. Handle PASS
    if verdict == "PASS":
        print("    PASSED QC")
        if not dry_run:
            _promote_to_review(draft_id, notion_id, notion_source)
        return result

    # 5. FAIL — check if Ellis can fix it directly (small mechanical fixes)
    direct_fixes = result.get("direct_fixes", [])
    feedback = result.get("feedback", "")
    needs_maya = bool(feedback and feedback.strip())

    if direct_fixes and not dry_run:
        fixed_text, changes = apply_direct_fixes(post_text, direct_fixes)
        if changes:
            print(f"    Ellis applying {len(changes)} direct fix(es):")
            for c in changes:
                print(f"      - {c}")

            # Update the draft in place
            try:
                if len(posts) == 1:
                    updated_posts = [dict(posts[0])]
                    updated_posts[0]["text"] = fixed_text
                else:
                    fixed_parts = [p.strip() for p in fixed_text.split("---") if p.strip()]
                    updated_posts = []
                    for i, part in enumerate(fixed_parts):
                        if i < len(posts):
                            up = dict(posts[i])
                            up["text"] = part
                        else:
                            up = {"text": part}
                        updated_posts.append(up)

                edit_draft_text(draft_id, updated_posts)
                print("    Draft updated with direct fixes")
                post_text = fixed_text  # update for re-evaluation
            except Exception as e:
                print(f"    WARN: Direct fix update failed: {e}")

        # If there was no feedback for Maya, re-evaluate after direct fixes
        if not needs_maya and changes:
            print("    Re-evaluating after direct fixes...")
            return qc_draft(draft_id, notion_id, notion_source, format_name, source_url, dry_run)

    # 6. FAIL — needs Maya for bigger changes
    round_num += 1
    _revision_counts[draft_id] = round_num

    if round_num >= MAX_REVISION_ROUNDS:
        print(f"    MAX ROUNDS ({MAX_REVISION_ROUNDS}) — escalating to Toan")
        if not dry_run:
            _promote_to_review(
                draft_id, notion_id, notion_source,
                note=f"QC escalated after {MAX_REVISION_ROUNDS} rounds. Score: {score}/12. Issues: {'; '.join(result.get('failures', [])[:3])}"
            )
        return result

    if not feedback:
        feedback = "; ".join(result.get("failures", ["Improve overall quality"]))

    print(f"    Sending to Maya for revision (round {round_num})...")
    print(f"    Feedback: {feedback[:150]}")

    if dry_run:
        print("    DRY RUN — skipping revision")
        return result

    try:
        revised_text = revise_post(post_text, feedback)
        if not revised_text or len(revised_text.strip()) < 50:
            print("    WARN: Maya revision too short, keeping original")
            _promote_to_review(draft_id, notion_id, notion_source,
                               note=f"QC failed ({score}/10) but Maya revision failed. Escalating.")
            return result
    except Exception as e:
        print(f"    ERROR: Maya revision failed: {e}")
        _promote_to_review(draft_id, notion_id, notion_source,
                           note=f"QC failed ({score}/10) but Maya revision errored. Escalating.")
        return result

    # 5. Edit the draft in place (preserves media)
    try:
        if len(posts) == 1:
            updated_posts = [dict(posts[0])]
            updated_posts[0]["text"] = revised_text
        else:
            revised_parts = [p.strip() for p in revised_text.split("---") if p.strip()]
            updated_posts = []
            for i, part in enumerate(revised_parts):
                if i < len(posts):
                    post = dict(posts[i])
                    post["text"] = part
                else:
                    post = {"text": part}
                updated_posts.append(post)

        edit_draft_text(draft_id, updated_posts)
        print(f"    Draft updated in place ({len(post_text)} → {len(revised_text)} chars)")
    except Exception as e:
        print(f"    ERROR: Could not update draft: {e}")
        return result

    # 6. Re-evaluate (recursive, bounded by MAX_REVISION_ROUNDS)
    print("    Re-evaluating after revision...")
    return qc_draft(draft_id, notion_id, notion_source, format_name, source_url, dry_run)


def _promote_to_review(
    draft_id: str,
    notion_id: str,
    notion_source: str,
    note: str = "",
):
    """Move a draft from QC Review to Ready for Review."""
    try:
        # Update Typefully: swap tag from qc-review to ready-for-review
        add_tag_to_draft(draft_id, "ready-for-review")
        # Enable sharing so Telegram bot can link to it
        enable_sharing(draft_id)
        print("    Typefully: tagged ready-for-review + sharing enabled")
    except Exception as e:
        print(f"    WARN: Typefully update failed: {e}")

    if notion_id:
        try:
            if notion_source == "idea_pipeline":
                update_idea_status(notion_id, "Ready for Review")
            else:
                update_longform_post(notion_id, status="Ready for Review")
            print("    Notion: status → Ready for Review")
        except Exception as e:
            print(f"    WARN: Notion update failed: {e}")


# ── Polling ────────────────────────────────────────────────────────────────

def gather_qc_items() -> list[dict]:
    """
    Pull items that need QC from both Notion sources.
    These are items with status "QC Review".
    """
    items = []

    # Library entries with QC Review status
    try:
        library = get_library_entries_by_status(status="QC Review")
        for entry in library:
            items.append({
                "notion_id": entry["id"],
                "source": "library",
                "title": entry.get("title", ""),
                "format": entry.get("format", ""),
                "draft_id": entry.get("typefully_draft_id", ""),
                "source_url": entry.get("source_url", ""),
            })
    except Exception as e:
        print(f"  WARN: Could not query Library for QC items: {e}")

    # Idea Pipeline entries with QC Review status
    try:
        ideas = get_triggered_ideas.__wrapped__(status="QC Review") if hasattr(get_triggered_ideas, '__wrapped__') else []
    except Exception:
        ideas = []

    # Fallback: query ideas with QC Review status directly
    if not ideas:
        try:
            from tools.notion_client import _query_database, IDEA_PIPELINE_DB_ID, _get_title, _get_select, _get_url, _get_rich_text, _get_multi_select
            filters = {"property": "Status", "select": {"equals": "QC Review"}}
            response = _query_database(IDEA_PIPELINE_DB_ID, {"filter": filters})
            for page in response.get("results", []):
                props = page["properties"]
                items.append({
                    "notion_id": page["id"],
                    "source": "idea_pipeline",
                    "title": _get_title(props.get("Idea", {})),
                    "format": ", ".join(_get_multi_select(props.get("Assigned Formats", {}))),
                    "draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
                    "source_url": _get_url(props.get("Source URL", {})),
                })
        except Exception as e:
            print(f"  WARN: Could not query Ideas for QC items: {e}")

    return items


def run_once(dry_run: bool = False) -> list[dict]:
    """Run one QC pass over all items with status "QC Review"."""
    print("Ellis QC Pipeline — Running")
    print("=" * 60)

    items = gather_qc_items()
    if not items:
        print("  No items in QC Review.")
        return []

    print(f"  Found {len(items)} items for QC")

    results = []
    for item in items:
        draft_id = item.get("draft_id", "")
        if not draft_id:
            print(f"  SKIP: '{item.get('title', '?')}' has no draft ID")
            continue

        result = qc_draft(
            draft_id=draft_id,
            notion_id=item.get("notion_id", ""),
            notion_source=item.get("source", "library"),
            format_name=item.get("format", ""),
            source_url=item.get("source_url", ""),
            dry_run=dry_run,
        )
        results.append({**item, **result})

    # Summary
    passed = sum(1 for r in results if r.get("verdict") == "PASS")
    failed = sum(1 for r in results if r.get("verdict") == "FAIL")
    print(f"\n{'=' * 60}")
    print(f"QC COMPLETE: {passed} passed, {failed} failed, {len(results)} total")
    print(f"{'=' * 60}")

    return results


def run_poll(dry_run: bool = False):
    """Continuously poll for QC Review items."""
    print(f"Ellis QC Pipeline — Polling every {POLL_INTERVAL // 60} minutes")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_once(dry_run=dry_run)
            print(f"\nSleeping {POLL_INTERVAL // 60}m...\n")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nEllis QC stopped.")
            break
        except Exception as e:
            print(f"[QC ERROR] {e}")
            time.sleep(POLL_INTERVAL)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ellis QC Pipeline")
    parser.add_argument("--once", action="store_true", help="Run one QC pass and exit")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for QC items")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without updating")
    parser.add_argument("--draft", type=str, help="QC a specific Typefully draft ID")
    parser.add_argument("--format", type=str, default="", help="Format name for --draft mode")
    args = parser.parse_args()

    if args.draft:
        result = qc_draft(draft_id=args.draft, format_name=args.format, dry_run=args.dry_run)
        print(f"\nFinal: {result.get('verdict')} ({result.get('score', '?')}/10)")
    elif args.poll:
        run_poll(dry_run=args.dry_run)
    elif args.once or args.dry_run:
        run_once(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
