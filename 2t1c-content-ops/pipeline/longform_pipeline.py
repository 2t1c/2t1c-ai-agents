"""
Long-Form Pipeline — Processes YouTube videos from the Video Backlog into
publication-ready long-form posts with video clips and QRT chains.

Pipeline flow:
1. Video Backlog → fetch transcript → snippet analysis (scaled to video type + duration)
2. Angle expansion → each snippet assessed for which formats it supports
3. Create Post Library entries with angles, formats, and timestamps
4. Write posts in batches of 3-5 via Maya (format-aware: uses the right addendum per format)
5. Extract clips (scaled length) for posts that need them
6. Add QRT chain (find recent relevant tweet + bridge line)
7. Create Typefully drafts with clip + QRT
8. Mark as Ready for Review

Key design decisions:
- Snippet count scales with video duration and type (podcast vs normal)
- One snippet can produce multiple posts across different formats
- Batch size (3-5) is a REVIEW CADENCE, not a total cap
- Format addendum comes from format_definitions.py so every post type has correct writing rules

Usage:
    python -m pipeline.longform_pipeline --process           # process next video in backlog
    python -m pipeline.longform_pipeline --url <youtube-url>  # process a specific URL
    python -m pipeline.longform_pipeline --write-batch <video-id>  # write next batch for analyzed video
    python -m pipeline.longform_pipeline --attach-clips       # extract & attach clips to drafts
    python -m pipeline.longform_pipeline --poll               # continuous polling
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.notion_client import (
    get_backlog_videos,
    update_video_status,
    create_longform_post,
    get_longform_posts,
    update_longform_post,
)
from tools.typefully_client import create_draft, upload_media
from tools.clip_extractor import (
    fetch_transcript,
    format_transcript,
    build_snippet_analysis_prompt,
    build_angle_expansion_prompt,
    extract_clip,
    upload_clip,
)
from pipeline.format_definitions import get_format, FORMAT_REGISTRY
from agents.maya.agent import write_thread

# For snippet analysis we call Claude directly
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env", override=True)

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ANALYSIS_MODEL = "claude-sonnet-4-6"

POLL_INTERVAL_SECONDS = 600  # 10 minutes
BATCH_SIZE = 5  # Review cadence — write 3-5 at a time for fast feedback loops


# ---------------------------------------------------------------------------
# Step 1: Analyze video — transcript → snippet analysis → structured snippets
# ---------------------------------------------------------------------------

def analyze_video(video_url: str, video_type: str = "Normal", notes: str = "") -> list[dict]:
    """
    Fetch transcript and identify clip-worthy snippets.
    Snippet count and clip length scale dynamically based on video type + duration.

    Returns a list of snippet dicts:
        [{
            "number": 1,
            "type": "Insight",
            "topic": "...",
            "start": "2:15",
            "end": "4:30",
            "duration": "2 minutes 15 seconds",
            "key_quote": "...",
            "why": "...",
            "priority": 1,
        }, ...]
    """
    print(f"\n=== ANALYZING VIDEO ===")
    print(f"URL: {video_url}")
    print(f"Type: {video_type}")

    # Fetch transcript
    print("  Fetching transcript...")
    transcript = fetch_transcript(video_url)
    if not transcript:
        print("  ERROR: No transcript available.")
        return []

    total_duration = transcript[-1]["start"] + transcript[-1].get("duration", 0)
    print(f"  Transcript: {len(transcript)} segments, {total_duration/60:.1f} minutes total")

    # Format transcript for analysis
    formatted = format_transcript(transcript, chunk_seconds=30)

    # Build type context
    type_context = ""
    if video_type.lower() == "podcast":
        type_context = (
            "This is a PODCAST (2-way conversation). "
            "Focus on the strongest standalone insights from either speaker. "
            "The clip should feature the most impactful speaker on the given point."
        )
    if notes:
        type_context += f"\nADDITIONAL CONTEXT: {notes}"

    # Build snippet analysis prompt — now scales with video type + duration
    prompt = build_snippet_analysis_prompt(
        formatted,
        video_url,
        topic_context=type_context,
        video_type=video_type,
        total_duration_seconds=total_duration,
    )

    # Run through Claude for analysis
    print("  Running snippet analysis via Claude...")
    response = anthropic_client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    analysis_text = response.content[0].text
    print(f"  Analysis complete ({len(analysis_text)} chars)")

    # Parse snippets from analysis
    snippets = _parse_snippets(analysis_text, video_url)
    print(f"  Found {len(snippets)} snippets")
    for s in snippets:
        print(f"    [{s['number']}] {s['type']}: {s['topic'][:60]} ({s['start']} → {s['end']})")

    return snippets


def _parse_snippets(analysis_text: str, video_url: str) -> list[dict]:
    """Parse the structured snippet output from Claude's analysis."""
    snippets = []

    # Split by SNIPPET markers
    blocks = re.split(r"SNIPPET\s+\[?(\d+)\]?", analysis_text)

    # Expanded type list to include podcast types
    valid_types = (
        "Insight|Evidence|Story|Confrontation|Prediction"
        "|Disagreement|Revelation|Say That Again|Host Reaction"
    )

    for i in range(1, len(blocks), 2):
        number = int(blocks[i])
        block = blocks[i + 1] if i + 1 < len(blocks) else ""

        # Extract type
        type_match = re.search(rf"—\s*({valid_types})", block)
        snippet_type = type_match.group(1) if type_match else "Insight"

        # Extract timestamp range
        ts_match = re.search(r"Timestamp[:\s]+(\d+:\d+(?::\d+)?)\s*[→—-]+\s*(\d+:\d+(?::\d+)?)", block)
        start = ts_match.group(1) if ts_match else ""
        end = ts_match.group(2) if ts_match else ""

        # Extract duration
        dur_match = re.search(r"Duration[:\s]+(.+?)(?:\n|$)", block)
        duration = dur_match.group(1).strip() if dur_match else ""

        # Extract topic
        topic_match = re.search(r"Topic[:\s]+(.+?)(?:\n|$)", block)
        topic = topic_match.group(1).strip() if topic_match else ""

        # Extract key quote
        quote_match = re.search(r'Key quote[:\s]+"([^"]+)"', block)
        key_quote = quote_match.group(1) if quote_match else ""

        # Extract why this works
        why_match = re.search(r"Why this works[:\s]+(.+?)(?:\n\n|\nCLIP|\Z)", block, re.DOTALL)
        why = why_match.group(1).strip() if why_match else ""

        if start and end:
            snippets.append({
                "number": number,
                "type": snippet_type,
                "topic": topic,
                "start": start,
                "end": end,
                "duration": duration,
                "key_quote": key_quote,
                "why": why,
                "video_url": video_url,
            })

    # Parse extraction priority to set priority order
    priority_section = re.search(r"EXTRACTION PRIORITY(.*?)$", analysis_text, re.DOTALL)
    if priority_section:
        priority_lines = re.findall(r"(\d+)\.\s*\[?(\d+)\]?", priority_section.group(1))
        priority_map = {int(snippet_num): rank for rank, (_, snippet_num) in enumerate(priority_lines, 1)}
        for s in snippets:
            s["priority"] = priority_map.get(s["number"], 99)
    else:
        for i, s in enumerate(snippets):
            s["priority"] = i + 1

    snippets.sort(key=lambda s: s["priority"])
    return snippets


# ---------------------------------------------------------------------------
# Step 2: Angle expansion — each snippet → multiple format-specific angles
# ---------------------------------------------------------------------------

def expand_angles(snippets: list[dict], video_type: str = "Normal") -> list[dict]:
    """
    Take parsed snippets and expand them into format-specific content angles.

    This is the bridge between snippet analysis (about the VIDEO) and
    post creation (about the CONTENT STRATEGY).

    Returns a list of angle dicts:
        [{
            "angle_number": 1,
            "source_snippet": 2,
            "format": "Clip Commentary",
            "uses_clip": True,
            "angle": "Why this insight changes how we think about...",
            "why_format": "The commentary format lets us...",
            "strength": "High",
            "priority": 1,
            "snippet": { ... },  # reference to the source snippet
        }, ...]
    """
    print(f"\n=== ANGLE EXPANSION ({len(snippets)} snippets) ===")

    prompt = build_angle_expansion_prompt(snippets, video_type=video_type)

    response = anthropic_client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    expansion_text = response.content[0].text
    print(f"  Expansion complete ({len(expansion_text)} chars)")

    # Parse angles
    angles = _parse_angles(expansion_text, snippets)
    print(f"  Expanded into {len(angles)} angles")

    # Stats
    with_clip = sum(1 for a in angles if a["uses_clip"])
    text_only = len(angles) - with_clip
    high = sum(1 for a in angles if a["strength"] == "High")
    print(f"    With clip: {with_clip} | Text-only: {text_only}")
    print(f"    High strength: {high} | Medium: {len(angles) - high}")

    for a in angles:
        clip_tag = "🎬" if a["uses_clip"] else "📝"
        print(f"    [{a['angle_number']}] {clip_tag} {a['format']}: {a['angle'][:60]}... [{a['strength']}]")

    return angles


def _parse_angles(expansion_text: str, snippets: list[dict]) -> list[dict]:
    """Parse the structured angle output from Claude's expansion."""
    angles = []

    # Build snippet lookup
    snippet_map = {s["number"]: s for s in snippets}

    # Split by ANGLE markers
    blocks = re.split(r"ANGLE\s+\[?(\d+)\]?", expansion_text)

    for i in range(1, len(blocks), 2):
        angle_number = int(blocks[i])
        block = blocks[i + 1] if i + 1 < len(blocks) else ""

        # Extract source snippet
        src_match = re.search(r"Source snippet[:\s]+\[?(\d+)\]?", block)
        source_snippet = int(src_match.group(1)) if src_match else 1

        # Extract format
        fmt_match = re.search(r"Format[:\s]+(.+?)(?:\n|$)", block)
        format_name = fmt_match.group(1).strip() if fmt_match else "Clip Commentary"

        # Extract uses_clip
        clip_match = re.search(r"Uses clip[:\s]+(Yes|No)", block, re.IGNORECASE)
        uses_clip = clip_match.group(1).lower() == "yes" if clip_match else True

        # Extract angle
        angle_match = re.search(r"Angle[:\s]+(.+?)(?:\n|$)", block)
        angle = angle_match.group(1).strip() if angle_match else ""

        # Extract why this format
        why_match = re.search(r"Why this format[:\s]+(.+?)(?:\n|$)", block)
        why_format = why_match.group(1).strip() if why_match else ""

        # Extract strength
        str_match = re.search(r"Strength[:\s]+(High|Medium)", block, re.IGNORECASE)
        strength = str_match.group(1).capitalize() if str_match else "Medium"

        angles.append({
            "angle_number": angle_number,
            "source_snippet": source_snippet,
            "format": format_name,
            "uses_clip": uses_clip,
            "angle": angle,
            "why_format": why_format,
            "strength": strength,
            "snippet": snippet_map.get(source_snippet, snippets[0] if snippets else {}),
        })

    # Parse production priority
    priority_section = re.search(r"PRODUCTION PRIORITY(.*?)$", expansion_text, re.DOTALL)
    if priority_section:
        priority_lines = re.findall(r"(\d+)\.\s*Angle\s*\[?(\d+)\]?", priority_section.group(1))
        priority_map = {int(angle_num): rank for rank, (_, angle_num) in enumerate(priority_lines, 1)}
        for a in angles:
            a["priority"] = priority_map.get(a["angle_number"], 99)
    else:
        for i, a in enumerate(angles):
            a["priority"] = i + 1

    angles.sort(key=lambda a: a["priority"])
    return angles


# ---------------------------------------------------------------------------
# Step 3: Create Notion entries for each angle
# ---------------------------------------------------------------------------

def create_post_entries(angles: list[dict], video_title: str = "", video_id: str | None = None) -> list[dict]:
    """
    Create Long-Form Post Library entries in Notion for each angle.

    Returns list of created page dicts with their Notion IDs.
    """
    print(f"\n=== CREATING POST ENTRIES ({len(angles)} angles) ===")

    created = []
    for a in angles:
        snippet = a["snippet"]
        title = f"{a['angle'][:80]}" if a["angle"] else f"Angle {a['angle_number']} — {a['format']}"

        page = create_longform_post(
            title=title,
            video_id=video_id,
            video_url=snippet.get("video_url", ""),
            snippet_type=snippet.get("type", ""),
            clip_start=snippet.get("start", "") if a["uses_clip"] else "",
            clip_end=snippet.get("end", "") if a["uses_clip"] else "",
            content_angle=a["angle"],
            assigned_format=a["format"],
            strength=a["strength"],
            uses_clip=a["uses_clip"],
            status="Angle Found",
        )
        page_id = page.get("id", "")
        clip_tag = "🎬" if a["uses_clip"] else "📝"
        print(f"  {clip_tag} Created: [{a['format']}] {title[:50]}... → {page_id}")
        created.append({
            "page_id": page_id,
            "angle": a,
            "snippet": snippet,
        })

    return created


# ---------------------------------------------------------------------------
# Step 4: Write posts in batch via Maya — FORMAT-AWARE
# ---------------------------------------------------------------------------

PODCAST_HOOK_ADDENDUM = """
PODCAST STYLE: This insight comes from a podcast conversation.
Use a podcast-style hook variant. Pull from the swipe file podcast hooks:
- "[Speaker] just said something on [Podcast] that changes everything.."
- "this conversation between [A] and [B] just revealed something most people miss.."
- "i just listened to [X] explain [topic] and it flipped my perspective.."
"""


def write_post_batch(entries: list[dict], video_type: str = "Normal", batch_size: int = BATCH_SIZE) -> list[dict]:
    """
    Write posts for a batch of Post Library entries.
    Uses the format-specific addendum from format_definitions.py for each post.

    Batch size is a REVIEW CADENCE — write 3-5 at a time so feedback can be
    incorporated before the next batch. Total posts are driven by how many
    strong angles exist, not this cap.

    Args:
        entries: List of dicts with 'page_id', 'angle', and 'snippet' keys.
        video_type: "Podcast" or "Normal" — affects hook style.
        batch_size: Max posts per review cycle (default 5).

    Returns list of results with page_id, post_text, success flag.
    """
    batch = entries[:batch_size]
    remaining = len(entries) - len(batch)
    print(f"\n=== WRITING BATCH ({len(batch)} posts, {remaining} remaining) ===")

    results = []
    for entry in batch:
        angle = entry["angle"]
        snippet = entry["snippet"]
        page_id = entry["page_id"]
        format_name = angle["format"]

        print(f"\n  Writing [{format_name}]: {angle['angle'][:50]}...")

        # Get format-specific writing addendum from registry
        format_def = get_format(format_name)
        if format_def:
            format_addendum = format_def["addendum"]
        else:
            # Fallback to generic long-form addendum
            format_addendum = """
IMPORTANT: You are writing a LONG-FORM SINGLE POST for X/Twitter (15-40+ lines).
This post should deliver the insight in GeniusGTX voice — editorial, intelligent, makes the reader think.
"""

        # Build the topic prompt for Maya
        topic_parts = [
            f"TOPIC: {snippet.get('topic', angle['angle'])}",
            f"CONTENT ANGLE: {angle['angle']}",
            f"KEY QUOTE from source: \"{snippet.get('key_quote', '')}\"",
            f"WHY THIS WORKS: {snippet.get('why', '')}",
            f"SNIPPET TYPE: {snippet.get('type', '')}",
            f"ASSIGNED FORMAT: {format_name}",
        ]

        # Add format-specific addendum
        topic_parts.append(format_addendum)

        # Add podcast hook style if applicable
        if video_type.lower() == "podcast":
            topic_parts.append(PODCAST_HOOK_ADDENDUM)

        topic_parts.append(f"Write the full {format_name} post now.")

        topic = "\n\n".join(topic_parts)

        try:
            post_text = write_thread(hook="", raw_facts="", topic=topic)

            if not post_text or len(post_text.strip()) < 100:
                print(f"    ERROR: Maya returned insufficient content ({len(post_text)} chars)")
                results.append({"page_id": page_id, "post_text": "", "success": False, "format": format_name})
                continue

            # Update Notion with the post text and format
            update_longform_post(page_id, status="Drafting")

            print(f"    Written: {len(post_text)} chars [{format_name}]")
            results.append({"page_id": page_id, "post_text": post_text, "success": True, "format": format_name})

        except Exception as e:
            print(f"    ERROR writing post: {e}")
            results.append({"page_id": page_id, "post_text": "", "success": False, "format": format_name})

    successful = sum(1 for r in results if r["success"])
    print(f"\n  Batch complete: {successful}/{len(batch)} posts written")
    if remaining > 0:
        print(f"  → {remaining} more posts queued. Run --write-batch again after review.")
    return results


# ---------------------------------------------------------------------------
# Step 5: Extract clip + upload to Typefully
# ---------------------------------------------------------------------------

def extract_and_attach_clip(post: dict) -> dict | None:
    """
    Extract a clip for a post and upload to Typefully.

    Args:
        post: Dict from get_longform_posts() with video_url, clip_start, clip_end.

    Returns dict with clip_path, media_id, or None on failure.
    """
    video_url = post.get("video_url", "")
    clip_start = post.get("clip_start", "")
    clip_end = post.get("clip_end", "")

    if not video_url or not clip_start or not clip_end:
        print(f"  SKIP: Missing clip info for {post.get('title', 'unknown')}")
        return None

    print(f"\n  Extracting clip: {clip_start} → {clip_end}")
    try:
        clip_path = extract_clip(video_url, clip_start, clip_end)
        print(f"  Clip saved: {clip_path}")

        media_id = upload_clip(clip_path)
        print(f"  Uploaded: {media_id}")

        return {"clip_path": str(clip_path), "media_id": media_id}

    except Exception as e:
        print(f"  ERROR extracting/uploading clip: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 6: Create Typefully draft with post + clip + QRT
# ---------------------------------------------------------------------------

def create_longform_draft(
    post_text: str,
    media_id: str | None = None,
    qrt_url: str | None = None,
    bridge_line: str | None = None,
) -> dict:
    """
    Create a Typefully draft for a long-form post.

    If qrt_url and bridge_line are provided, appends the bridge line
    to the post text before creating the draft.
    """
    final_text = post_text

    # Add bridge line before the QRT
    if qrt_url and bridge_line:
        final_text = f"{post_text.rstrip()}\n\n{bridge_line}"

    media_ids = [media_id] if media_id else None

    draft = create_draft(
        post_text=final_text,
        qrt_url=qrt_url,
        media_ids=media_ids,
    )
    return draft


# ---------------------------------------------------------------------------
# Main orchestration: process a full video end-to-end
# ---------------------------------------------------------------------------

def process_video(video: dict) -> list[dict]:
    """
    Process a single video from the backlog through the full pipeline:
    1. Analyze (snippet analysis, scaled to video)
    2. Expand (angle expansion — snippets → format-specific angles)
    3. Create entries (Notion posts for each angle)
    4. Write batch (first batch of 3-5 posts)

    Steps 5 (clip) and 6 (QRT chain + Typefully draft) are triggered separately
    after human review of the written posts.

    Returns list of created post entries.
    """
    video_url = video.get("video_url", "")
    video_type = video.get("video_type", "Normal")
    video_title = video.get("title", "")
    video_id = video.get("id")

    if not video_url:
        print(f"SKIP: No URL for video '{video_title}'")
        return []

    print(f"\n{'='*60}")
    print(f"PROCESSING: {video_title}")
    print(f"Type: {video_type}")
    print(f"{'='*60}")

    # Mark as Processing
    if video_id:
        update_video_status(video_id, "Processing")

    # Step 1: Analyze — find clip-worthy snippets (scaled to video)
    snippets = analyze_video(video_url, video_type=video_type, notes=video.get("notes", ""))
    if not snippets:
        print("  No viable snippets found. Marking as Processed (empty).")
        if video_id:
            update_video_status(video_id, "Processed")
        return []

    # Step 2: Expand — turn snippets into format-specific content angles
    angles = expand_angles(snippets, video_type=video_type)
    if not angles:
        print("  No viable angles found from snippets.")
        if video_id:
            update_video_status(video_id, "Processed")
        return []

    # Step 3: Create Notion entries for each angle
    entries = create_post_entries(angles, video_title=video_title, video_id=video_id)

    # Step 4: Write first batch (review cadence — 3-5 at a time)
    write_results = write_post_batch(entries, video_type=video_type, batch_size=BATCH_SIZE)

    # Update post entries with write status
    for result in write_results:
        if result["success"]:
            update_longform_post(result["page_id"], status="Ready for Review")

    # Mark video as processed
    if video_id:
        update_video_status(video_id, "Processed")

    successful = [r for r in write_results if r["success"]]
    total_angles = len(angles)
    print(f"\n{'='*60}")
    print(f"DONE: {len(successful)} posts written (batch 1/{-(-total_angles // BATCH_SIZE)})")
    print(f"Total angles: {total_angles} | Remaining to write: {total_angles - len(successful)}")
    print(f"Run --write-batch to continue after review.")
    print(f"{'='*60}")

    return entries


def finalize_posts(status: str = "Approved") -> list[dict]:
    """
    Finalize approved posts: extract clips, add QRT chains, create Typefully drafts.

    This runs AFTER human review. Only processes posts with status = 'Approved'.
    """
    posts = get_longform_posts(status=status)
    if not posts:
        print("No approved posts to finalize.")
        return []

    print(f"\n=== FINALIZING {len(posts)} APPROVED POSTS ===")

    results = []
    for post in posts:
        post_id = post["id"]
        title = post.get("title", "unknown")
        uses_clip = post.get("uses_clip", True)
        print(f"\n--- Finalizing: {title[:60]} ---")

        # Step 5: Extract clip (only for posts that need one)
        media_id = None
        if uses_clip:
            clip_result = extract_and_attach_clip(post)
            media_id = clip_result["media_id"] if clip_result else None
        else:
            print(f"  Text-only format — skipping clip extraction")

        # Step 6: QRT chain will be handled by the account manager or cowork session
        qrt_url = post.get("qrt_url")

        update_longform_post(post_id, status="Ready to Post")
        print(f"  → Ready to Post")

        results.append({
            "post_id": post_id,
            "title": title,
            "media_id": media_id,
            "qrt_url": qrt_url,
            "format": post.get("assigned_format", "unknown"),
        })

    print(f"\n=== Finalized {len(results)} posts ===")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Long-Form Pipeline — YouTube → Posts")
    parser.add_argument("--process", action="store_true", help="Process next video from backlog")
    parser.add_argument("--url", type=str, help="Process a specific YouTube URL directly")
    parser.add_argument("--type", type=str, default="Normal", choices=["Normal", "Podcast"],
                        help="Video type (default: Normal)")
    parser.add_argument("--write-batch", action="store_true",
                        help="Write next batch of posts for videos with unwritten angles")
    parser.add_argument("--finalize", action="store_true", help="Finalize approved posts (clip + draft)")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for new videos")
    args = parser.parse_args()

    if args.url:
        # Direct URL processing
        video = {
            "id": None,
            "title": f"Direct: {args.url}",
            "video_url": args.url,
            "video_type": args.type,
            "notes": "",
        }
        process_video(video)

    elif args.process:
        # Process next video from Notion backlog
        videos = get_backlog_videos(status="Backlog")
        if not videos:
            print("No videos in backlog.")
            return
        print(f"Found {len(videos)} video(s) in backlog. Processing first...")
        process_video(videos[0])

    elif args.write_batch:
        # Write next batch of unwritten posts
        posts = get_longform_posts(status="Angle Found")
        if not posts:
            print("No unwritten angles found.")
            return
        print(f"Found {len(posts)} unwritten angles. Writing next batch...")
        # Group by video and write batch
        entries = [{"page_id": p["id"], "angle": p, "snippet": p} for p in posts]
        write_post_batch(entries, batch_size=BATCH_SIZE)

    elif args.finalize:
        finalize_posts()

    elif args.poll:
        print(f"Long-Form Pipeline — polling every {POLL_INTERVAL_SECONDS}s")
        print("Press Ctrl+C to stop.\n")
        while True:
            try:
                videos = get_backlog_videos(status="Backlog")
                if videos:
                    print(f"[POLL] Found {len(videos)} video(s) in backlog")
                    process_video(videos[0])
                else:
                    print("[POLL] No videos in backlog. Sleeping...")
                time.sleep(POLL_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                print("\nPipeline stopped.")
                break
            except Exception as e:
                print(f"[POLL ERROR] {e}")
                time.sleep(POLL_INTERVAL_SECONDS)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
