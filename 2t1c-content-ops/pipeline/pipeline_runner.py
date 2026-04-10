"""
Pipeline Runner — Unified entry point for the GeniusGTX content production cycle.

Consolidates all pipeline stages into a single script:
  Stage 1: Kai research sweep (optional, runs on longer interval)
  Stage 2: Content Orchestrator — fan out Extraction Plans to Library entries
  Stage 3: Format Pipeline — write posts from Library + triggered ideas
  Stage 4: Media Attacher — attach GIFs to drafts tagged 'needs-media'

Usage:
    python -m pipeline.pipeline_runner --cycle          # one full production cycle (stages 2-4)
    python -m pipeline.pipeline_runner --full            # full cycle INCLUDING Kai research
    python -m pipeline.pipeline_runner --poll            # continuous polling
    python -m pipeline.pipeline_runner --poll --with-kai # polling with periodic Kai sweeps
    python -m pipeline.pipeline_runner --stage orchestrator  # run a single stage
    python -m pipeline.pipeline_runner --stage writer        # run a single stage
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Stage intervals (seconds)
PRODUCTION_CYCLE_INTERVAL = 300   # 5 minutes — orchestrator + writer + media
KAI_SCAN_INTERVAL = 1800          # 30 minutes — research sweeps
BACKLOG_SWEEP_INTERVAL = 3600     # 60 minutes — backlog sweep + enrichment


# ---------------------------------------------------------------------------
# Stage runners (lazy imports to avoid loading everything upfront)
# ---------------------------------------------------------------------------

def run_kai_scan(topic: str | None = None) -> dict:
    """Stage 1: Kai research sweep."""
    print(f"\n{'='*60}")
    print(f"STAGE 1: Kai Research Sweep — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from agents.kai.agent import scan
        result = scan(topic=topic)
        return {"stage": "kai", "status": "ok", "summary": str(result)[:200]}
    except Exception as e:
        print(f"  ERROR: Kai scan failed: {e}")
        traceback.print_exc()
        return {"stage": "kai", "status": "error", "error": str(e)}


def run_orchestrator() -> dict:
    """Stage 2: Content Orchestrator — parse Extraction Plans → Library entries."""
    print(f"\n{'='*60}")
    print(f"STAGE 2: Content Orchestrator — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.content_orchestrator import (
            get_triggered_ideas_with_plans,
            orchestrate_idea,
        )

        ideas = get_triggered_ideas_with_plans()
        if not ideas:
            print("  No triggered ideas with Extraction Plans.")
            return {"stage": "orchestrator", "status": "ok", "entries_created": 0}

        total_created = 0
        for idea in ideas:
            entries = orchestrate_idea(idea)
            total_created += len(entries)

        print(f"  Orchestrator done: {total_created} Library entries created")
        return {"stage": "orchestrator", "status": "ok", "entries_created": total_created}

    except Exception as e:
        print(f"  ERROR: Orchestrator failed: {e}")
        traceback.print_exc()
        return {"stage": "orchestrator", "status": "error", "error": str(e)}


def run_writer(batch_size: int = 5) -> dict:
    """Stage 3: Format Pipeline — process Library entries + triggered ideas."""
    print(f"\n{'='*60}")
    print(f"STAGE 3: Format Pipeline (Writer) — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.format_pipeline import run_all_formats, run_from_library

        # 3a: Process all triggered ideas across formats (direct Notion → Typefully)
        print("  [3a] Processing triggered ideas...")
        format_results = run_all_formats()

        # 3b: Process Library entries (orchestrator output → Typefully)
        print(f"  [3b] Processing Library entries (batch={batch_size})...")
        library_results = run_from_library(batch_size=batch_size)

        total = len(format_results) + len(library_results)
        print(f"  Writer done: {len(format_results)} from triggers + {len(library_results)} from library = {total} total")

        return {
            "stage": "writer",
            "status": "ok",
            "from_triggers": len(format_results),
            "from_library": len(library_results),
            "total": total,
        }

    except Exception as e:
        print(f"  ERROR: Writer failed: {e}")
        traceback.print_exc()
        return {"stage": "writer", "status": "error", "error": str(e)}


def run_tuki() -> dict:
    """Stage 3b: Tuki Pipeline — process Tuki QRT ideas specifically."""
    print(f"\n{'='*60}")
    print(f"STAGE 3b: Tuki Pipeline — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.tuki_pipeline import run_once
        run_once()
        return {"stage": "tuki", "status": "ok"}

    except Exception as e:
        print(f"  ERROR: Tuki pipeline failed: {e}")
        traceback.print_exc()
        return {"stage": "tuki", "status": "error", "error": str(e)}


def run_media_attacher() -> dict:
    """Stage 4: Media Attacher — attach GIFs to 'needs-media' drafts."""
    print(f"\n{'='*60}")
    print(f"STAGE 4: Media Attacher — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.media_attacher import process_all_needs_media
        count = process_all_needs_media()
        print(f"  Media attacher done: {count} drafts processed")
        return {"stage": "media", "status": "ok", "processed": count}

    except ImportError:
        # media_attacher might not have process_all_needs_media — try alternate
        try:
            from pipeline.media_attacher import run_once
            run_once()
            return {"stage": "media", "status": "ok"}
        except Exception as e:
            print(f"  WARN: Media attacher not available ({e}). Skipping.")
            return {"stage": "media", "status": "skipped", "reason": str(e)}

    except Exception as e:
        print(f"  ERROR: Media attacher failed: {e}")
        traceback.print_exc()
        return {"stage": "media", "status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# New stages: Idea Trigger + Typefully Sync
# ---------------------------------------------------------------------------

def run_idea_trigger() -> dict:
    """Stage 0: Move ready ideas from New → Triggered."""
    print(f"\n{'='*60}")
    print(f"STAGE 0: Idea Trigger — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.idea_trigger import run_trigger
        result = run_trigger()
        triggered = result.get("triggered", 0)
        skipped = result.get("skipped", 0)
        print(f"  Idea trigger done: {triggered} triggered, {skipped} skipped")
        return {"stage": "idea_trigger", "status": "ok", "triggered": triggered, "skipped": skipped}
    except Exception as e:
        print(f"  ERROR: Idea trigger failed: {e}")
        traceback.print_exc()
        return {"stage": "idea_trigger", "status": "error", "error": str(e)}


def run_backlog_sweep(enrich: bool = True) -> dict:
    """Stage 6: Daily backlog sweep — catch stuck ideas, enrich missing angles."""
    print(f"\n{'='*60}")
    print(f"STAGE 6: Backlog Sweep — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.backlog_sweep import run_sweep
        result = run_sweep(enrich=enrich)
        triggered = result.get("triggered", 0)
        enriched = result.get("enriched", 0)
        flagged = result.get("flagged", 0)
        print(f"  Sweep done: {triggered} triggered, {enriched} enriched, {flagged} flagged")
        return {"stage": "backlog_sweep", "status": "ok", "triggered": triggered, "enriched": enriched, "flagged": flagged}
    except Exception as e:
        print(f"  ERROR: Backlog sweep failed: {e}")
        traceback.print_exc()
        return {"stage": "backlog_sweep", "status": "error", "error": str(e)}


def run_ellis_qc() -> dict:
    """Stage 4.5: Ellis QC — evaluate drafts in 'QC Review', pass/fail/revise."""
    print(f"\n{'='*60}")
    print(f"STAGE 4.5: Ellis QC — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.ellis_runner import run_once
        result = run_once()
        passed = result.get("passed", 0)
        failed = result.get("failed", 0)
        escalated = result.get("escalated", 0)
        print(f"  Ellis done: {passed} passed, {failed} failed, {escalated} escalated")
        return {"stage": "ellis_qc", "status": "ok", "passed": passed, "failed": failed, "escalated": escalated}
    except Exception as e:
        print(f"  ERROR: Ellis QC failed: {e}")
        traceback.print_exc()
        return {"stage": "ellis_qc", "status": "error", "error": str(e)}


def run_typefully_sync() -> dict:
    """Stage 5: Sync Typefully draft statuses back to Notion."""
    print(f"\n{'='*60}")
    print(f"STAGE 5: Typefully ↔ Notion Sync — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    try:
        from pipeline.typefully_sync import run_sync
        result = run_sync()
        updated = result.get("updated", 0)
        print(f"  Sync done: {updated} statuses updated")
        return {"stage": "typefully_sync", "status": "ok", "updated": updated}
    except Exception as e:
        print(f"  ERROR: Typefully sync failed: {e}")
        traceback.print_exc()
        return {"stage": "typefully_sync", "status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Cycle runners
# ---------------------------------------------------------------------------

def run_production_cycle(batch_size: int = 5) -> list[dict]:
    """
    Run one full production cycle (Stages 0-5):
    Idea Trigger → Orchestrator → Writer → Tuki → Media Attacher → Typefully Sync
    """
    print(f"\n{'#'*60}")
    print(f"PRODUCTION CYCLE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    results = []

    # Stage 0: Trigger ready ideas (New → Triggered)
    results.append(run_idea_trigger())

    # Stage 2: Orchestrator
    results.append(run_orchestrator())

    # Stage 3: Writer (all formats from Library + direct triggers)
    results.append(run_writer(batch_size=batch_size))

    # Stage 3b: Tuki (separate because it has its own pipeline)
    results.append(run_tuki())

    # Stage 4: Media attachment
    results.append(run_media_attacher())

    # Stage 4.5: Ellis QC — TEMPORARILY DISABLED
    # results.append(run_ellis_qc())

    # Stage 5: Sync Typefully ↔ Notion
    results.append(run_typefully_sync())

    # Summary
    print(f"\n{'#'*60}")
    print("CYCLE SUMMARY:")
    for r in results:
        status_icon = "✅" if r["status"] == "ok" else "⚠️" if r["status"] == "skipped" else "❌"
        print(f"  {status_icon} {r['stage']}: {r['status']}")
    print(f"{'#'*60}")

    return results


def run_full_cycle(topic: str | None = None, batch_size: int = 5) -> list[dict]:
    """Run full cycle INCLUDING Kai research (Stages 1-4)."""
    results = [run_kai_scan(topic=topic)]
    results.extend(run_production_cycle(batch_size=batch_size))
    return results


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def run_poll(with_kai: bool = False, topic: str | None = None, batch_size: int = 5):
    """
    Continuously poll. Full autonomous pipeline:
      - Production cycle (trigger + write + media + sync): every 5 min
      - Kai research: every 30 min
      - Backlog sweep + enrichment: every 60 min
    """
    print(f"Pipeline Runner — Autonomous Mode")
    print(f"  Production cycle: every {PRODUCTION_CYCLE_INTERVAL // 60}m")
    if with_kai:
        print(f"  Kai research: every {KAI_SCAN_INTERVAL // 60}m")
    print(f"  Backlog sweep: every {BACKLOG_SWEEP_INTERVAL // 60}m")
    print("  Press Ctrl+C to stop.\n")

    last_kai_run = 0
    last_sweep_run = 0

    while True:
        try:
            now = time.time()

            # Kai scan (if enabled and interval elapsed)
            if with_kai and (now - last_kai_run) >= KAI_SCAN_INTERVAL:
                run_kai_scan(topic=topic)
                last_kai_run = time.time()

            # Backlog sweep (every hour — enriches missing angles, catches stuck ideas)
            if (now - last_sweep_run) >= BACKLOG_SWEEP_INTERVAL:
                run_backlog_sweep(enrich=True)
                last_sweep_run = time.time()

            # Production cycle (trigger → orchestrate → write → media → sync)
            run_production_cycle(batch_size=batch_size)

            print(f"\n[POLL] Sleeping {PRODUCTION_CYCLE_INTERVAL // 60}m...")
            time.sleep(PRODUCTION_CYCLE_INTERVAL)

        except KeyboardInterrupt:
            print("\nPipeline stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            traceback.print_exc()
            time.sleep(PRODUCTION_CYCLE_INTERVAL)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Runner — unified GeniusGTX content production",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Stages:
  kai          Research sweep (Tavily → Notion ideas)
  orchestrator Fan out Extraction Plans → Library entries
  writer       Jordan hooks + Maya posts → Typefully drafts
  tuki         Tuki QRT pipeline
  media        Attach GIFs to 'needs-media' drafts

Examples:
  %(prog)s --cycle                    # one production cycle (stages 2-4)
  %(prog)s --full                     # full cycle with Kai (stages 1-4)
  %(prog)s --poll                     # continuous production polling
  %(prog)s --poll --with-kai          # continuous with Kai sweeps
  %(prog)s --stage orchestrator       # run just the orchestrator
  %(prog)s --stage writer             # run just the writer
""",
    )
    parser.add_argument("--cycle", action="store_true", help="Run one production cycle (stages 2-4)")
    parser.add_argument("--full", action="store_true", help="Run full cycle including Kai research (stages 1-4)")
    parser.add_argument("--poll", action="store_true", help="Continuous polling mode")
    parser.add_argument("--with-kai", action="store_true", help="Include Kai research in polling")
    parser.add_argument("--stage", type=str, choices=["kai", "orchestrator", "writer", "tuki", "media"],
                        help="Run a single stage")
    parser.add_argument("--topic", type=str, help="Focus Kai research on a specific topic")
    parser.add_argument("--batch-size", type=int, default=5, help="Writer batch size (default 5)")
    args = parser.parse_args()

    if args.stage:
        stage_map = {
            "kai": lambda: run_kai_scan(topic=args.topic),
            "orchestrator": run_orchestrator,
            "writer": lambda: run_writer(batch_size=args.batch_size),
            "tuki": run_tuki,
            "media": run_media_attacher,
        }
        stage_map[args.stage]()
    elif args.full:
        run_full_cycle(topic=args.topic, batch_size=args.batch_size)
    elif args.cycle:
        run_production_cycle(batch_size=args.batch_size)
    elif args.poll:
        run_poll(with_kai=args.with_kai, topic=args.topic, batch_size=args.batch_size)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
