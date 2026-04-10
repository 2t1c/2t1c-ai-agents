"""
Format Pipeline — Unified content pipeline for ALL formats in the Idea Pipeline.

Replaces the need for separate pipelines per format. Each format has its own
writing rules (addendum), media requirements, and hook style — all defined in
format_definitions.py.

Pipeline flow (same for every format):
1. Query Notion for triggered ideas with a given format
2. Enrich with source context (tweet data, video transcript, etc.)
3. Jordan writes the hook (or format uses built-in opener)
4. Maya writes the body with format-specific addendum
5. Handle media (QRT, GIF, clip, both, or none)
6. Create Typefully draft
7. Update Notion status

Usage:
    python -m pipeline.format_pipeline --format "Bark QRT" --once
    python -m pipeline.format_pipeline --format "Stat Bomb" --once
    python -m pipeline.format_pipeline --format "Commentary Post" --idea-id <id>
    python -m pipeline.format_pipeline --all --once       # process all formats
    python -m pipeline.format_pipeline --poll              # continuous polling
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.notion_client import (
    get_triggered_ideas,
    update_idea_status,
    save_typefully_draft_id,
    get_idea_by_id,
)
from tools.typefully_client import create_draft, upload_media, pick_random_gif, enable_sharing
from tools.tweet_fetcher import fetch_tweet
from tools.clip_extractor import (
    fetch_transcript, format_transcript, extract_clip, upload_clip,
    build_snippet_analysis_prompt,
)
from pipeline.media_rules import determine_media_needs
from pipeline.format_definitions import get_format, list_all_formats, FORMAT_REGISTRY
from agents.maya.agent import write_thread
from agents.jordan.agent import generate_hooks
from tools.notion_client import get_library_entries_by_status, update_longform_post, create_longform_post

POLL_INTERVAL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Maya output cleanup
# ---------------------------------------------------------------------------

def _strip_maya_preamble(text: str) -> str:
    """Strip meta-text preamble from Maya's output.

    Maya sometimes prefixes her output with lines like:
      "Here is the full post body, following the hook:"
      "Here's the body:"
      "Here's the body (hook already provided by Jordan):"
    These should never appear in the published draft.
    """
    if not text:
        return text

    import re
    lines = text.split("\n")
    # Find first line that looks like actual content (not meta-text)
    preamble_patterns = [
        r"^here(?:'s| is) the (?:full )?(?:post )?body",
        r"^here(?:'s| is) the (?:full )?post",
        r"^here(?:'s| is) (?:my |the )?(?:draft|response|output)",
        r"^following the hook",
        r"^hook already provided",
        r"^below is the",
        r"^---$",  # separator after preamble
    ]
    combined = re.compile("|".join(preamble_patterns), re.IGNORECASE)

    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if combined.search(stripped):
            start = i + 1
        else:
            break

    # Skip any leading blank lines or "---" separators after preamble
    while start < len(lines) and (not lines[start].strip() or lines[start].strip() == "---"):
        start += 1

    cleaned = "\n".join(lines[start:]).strip()
    return cleaned if cleaned else text


# ---------------------------------------------------------------------------
# Jordan hook integration
# ---------------------------------------------------------------------------

def _parse_best_hook(jordan_output: str) -> str | None:
    """
    Parse Jordan's output to extract the best hook (Hook 1).
    Jordan returns 3 hooks with markers like HOOK 1, Hook 1, or 1.
    """
    if not jordan_output:
        return None

    # Try numbered markers: HOOK 1, Hook 1, HOOK [1]
    patterns = [
        r"(?:HOOK|Hook)\s*(?:\[)?1(?:\])?\s*[:\-—–]?\s*(.+?)(?=(?:HOOK|Hook)\s*(?:\[)?2|\Z)",
        r"(?:^|\n)1[.\)]\s*(.+?)(?=(?:^|\n)2[.\)]|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, jordan_output, re.DOTALL | re.IGNORECASE)
        if match:
            hook_text = match.group(1).strip()
            # Clean: remove certainty maps, trailing metadata
            lines = []
            for line in hook_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Stop at certainty map or metadata markers
                lower = line.lower()
                if any(marker in lower for marker in [
                    "certainty", "confidence", "rubric", "score",
                    "hook 2", "hook 3", "feedback", "---",
                ]):
                    break
                lines.append(line)
            if lines:
                result = "\n".join(lines).strip()
                if len(result) > 20:
                    return result

    # Fallback: first substantial paragraph
    paragraphs = [p.strip() for p in jordan_output.split("\n\n") if len(p.strip()) > 50]
    return paragraphs[0] if paragraphs else None


def generate_jordan_hook(idea: dict, format_def: dict) -> str | None:
    """
    Call Jordan to generate hooks for the idea, return the best one.
    Only called when format_def['hook_style'] == 'jordan'.
    """
    topic = idea.get("idea", "")
    if idea.get("content_angle"):
        topic += f" — Angle: {idea['content_angle']}"

    raw_facts_parts = []
    if idea.get("tweet_context"):
        raw_facts_parts.append(idea["tweet_context"])
    if idea.get("notes"):
        raw_facts_parts.append(f"Notes: {idea['notes']}")
    if idea.get("transcript_formatted"):
        # Only send first 2000 chars of transcript to avoid token bloat
        raw_facts_parts.append(f"Transcript excerpt:\n{idea['transcript_formatted'][:2000]}")

    raw_facts = "\n\n".join(raw_facts_parts)

    print("    Generating hook via Jordan...")
    jordan_output = generate_hooks(topic=topic, raw_facts=raw_facts)
    hook = _parse_best_hook(jordan_output)

    if hook:
        print(f"    Jordan hook ({len(hook)} chars): {hook[:80]}...")
    else:
        print("    WARN: Could not parse hook from Jordan's output")

    return hook


# ---------------------------------------------------------------------------
# Context enrichment
# ---------------------------------------------------------------------------

def enrich_with_tweet(idea: dict) -> dict:
    """
    If the idea has a tweet source URL, fetch tweet text and metadata.
    Traces QRTs back to the original post (never QRT the QRTer).
    """
    source_url = idea.get("source_url", "")
    if not source_url or ("x.com" not in source_url and "twitter.com" not in source_url):
        return idea

    try:
        tweet_data = fetch_tweet(source_url)
        context_parts = []
        context_parts.append(f"SOURCE TWEET by {tweet_data['handle']} ({tweet_data['author']}):")
        context_parts.append(f'"{tweet_data["text"]}"')

        if tweet_data.get("views"):
            context_parts.append(
                f"Engagement: {tweet_data['views']:,} views, "
                f"{tweet_data['likes']:,} likes, {tweet_data['retweets']:,} RTs"
            )

        idea = dict(idea)

        if tweet_data.get("quoted_tweet"):
            qt = tweet_data["quoted_tweet"]
            context_parts.append(f"\nORIGINAL QUOTED TWEET by {qt['handle']} ({qt['author']}):")
            context_parts.append(f'"{qt["text"]}"')

            # Trace back to original — QRT the source, not the QRTer
            if qt.get("url"):
                idea["qrt_source_url"] = qt["url"]
                print(f"    QRT traced → original: {qt['url']}")

        idea["tweet_context"] = "\n".join(context_parts)
        idea["tweet_data"] = tweet_data
        print(f"    Fetched tweet: {tweet_data['text'][:80]}...")

    except Exception as e:
        print(f"    WARN: Could not fetch tweet ({e})")

    return idea


def enrich_with_transcript(idea: dict) -> dict:
    """
    If the idea has a YouTube source URL, fetch transcript for clip context.
    Used by clip-based formats.
    """
    source_url = idea.get("source_url", "")
    if not source_url or "youtube.com" not in source_url and "youtu.be" not in source_url:
        return idea

    try:
        transcript = fetch_transcript(source_url)
        if transcript:
            formatted = format_transcript(transcript, chunk_seconds=30)
            idea = dict(idea)
            idea["transcript_formatted"] = formatted
            total_duration = transcript[-1]["start"] + transcript[-1].get("duration", 0)
            print(f"    Fetched transcript: {len(transcript)} segments, {total_duration/60:.1f}m")
    except Exception as e:
        print(f"    WARN: Could not fetch transcript ({e})")

    return idea


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_format_prompt(idea: dict, format_def: dict) -> str:
    """
    Build the full prompt for Maya based on format definition and idea context.
    """
    parts = [f"TOPIC: {idea['idea']}"]

    if idea.get("content_angle"):
        parts.append(f"ANGLE (use this as your editorial direction — do NOT include this text verbatim in the post): {idea['content_angle']}")

    if idea.get("tweet_context"):
        parts.append(idea["tweet_context"])

    if idea.get("source_url"):
        if format_def["pipeline_type"] == "qrt":
            qrt_target = idea.get("qrt_source_url", idea["source_url"])
            parts.append(f"QRT TARGET URL: {qrt_target}")
        else:
            parts.append(f"SOURCE: {idea['source_url']}")

    if idea.get("source_account"):
        parts.append(f"SOURCE ACCOUNT: {idea['source_account']}")

    if idea.get("notes"):
        parts.append(f"NOTES: {idea['notes']}")

    # Format-specific writing instructions
    parts.append(format_def["addendum"])

    # Output instruction
    if format_def["is_thread"]:
        parts.append("Write the full thread now. Separate each tweet with ---.\n\nIMPORTANT: Output ONLY the post text. No preamble, no 'Here is the body:', no 'Here's the post:', no meta-commentary. Just the raw post content ready to publish.")
    else:
        parts.append("Write the full post now. One continuous post, not a thread.\n\nIMPORTANT: Output ONLY the post text. No preamble, no 'Here is the body:', no 'Here's the post:', no meta-commentary. Just the raw post content ready to publish.")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Media handling
# ---------------------------------------------------------------------------

def _pick_best_clip_timestamps(idea: dict, post_text: str = "") -> tuple[str, str] | None:
    """
    Use an LLM call to pick the single best clip from the transcript that matches
    the post content. Returns (start, end) timestamps or None if it can't determine them.
    """
    import re as _re
    from anthropic import Anthropic as _Anthropic

    transcript_formatted = idea.get("transcript_formatted", "")
    video_url = idea.get("source_url", "")
    if not transcript_formatted or not video_url:
        return None

    _client = _Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Pick the SINGLE BEST clip from this transcript that matches the post below.

POST TEXT:
{post_text[:2000]}

TRANSCRIPT:
{transcript_formatted[:8000]}

VIDEO URL: {video_url}

Rules:
- Pick 1 clip, 1-3 minutes long
- The clip must be a self-contained moment that works on its own
- Start 5 seconds before the first word, end 3 seconds after the last word
- Prefer the section that most directly supports the post's argument

Reply with ONLY this format, nothing else:
START: [timestamp like 2:15 or 1:02:30]
END: [timestamp like 4:45 or 1:05:00]
REASON: [one sentence]"""

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    start_match = _re.search(r"START:\s*(\d+:[\d:]+)", text)
    end_match = _re.search(r"END:\s*(\d+:[\d:]+)", text)

    if start_match and end_match:
        return start_match.group(1), end_match.group(1)
    return None


def handle_media(idea: dict, format_def: dict, post_text: str = "") -> tuple[list[str], str | None]:
    """
    Handle media based on format requirements. Media is always attached inline —
    no deferred tagging.

    Returns:
        (media_ids, qrt_url) — media_ids is a list of uploaded media IDs,
        qrt_url is the URL to QRT (or None).
    """
    media_type = format_def["media_type"]
    source_url = idea.get("source_url", "")
    qrt_source_url = idea.get("qrt_source_url", "")
    media_ids = []
    qrt_url = None

    # Determine QRT URL
    # Rule: ANY Twitter source becomes a QRT, regardless of format
    is_twitter = "x.com" in source_url or "twitter.com" in source_url
    if media_type in ("qrt", "both") or is_twitter:
        qrt_url = qrt_source_url or ""
        if not qrt_url and is_twitter:
            qrt_url = source_url
        if not qrt_url:
            qrt_url = None

    # Handle GIF
    if media_type in ("gif", "both"):
        gif_path = pick_random_gif()
        if gif_path:
            try:
                print(f"    Uploading GIF: {gif_path.name[:50]}...")
                media_id = upload_media(gif_path)
                media_ids.append(media_id)
                print(f"    GIF uploaded: {media_id}")
            except Exception as e:
                print(f"    WARN: GIF upload failed ({e})")

    # Handle clip (for clip-based formats)
    if media_type == "clip":
        clip_start = idea.get("clip_start", "")
        clip_end = idea.get("clip_end", "")
        video_url = idea.get("source_url", "")
        is_youtube = video_url and ("youtube.com" in video_url or "youtu.be" in video_url)

        # If timestamps aren't pre-set, pick them from the transcript via LLM
        if not (clip_start and clip_end) and is_youtube and idea.get("transcript_formatted"):
            print("    Picking best clip timestamps from transcript...")
            timestamps = _pick_best_clip_timestamps(idea, post_text)
            if timestamps:
                clip_start, clip_end = timestamps
                idea["clip_start"] = clip_start
                idea["clip_end"] = clip_end
                print(f"    Selected clip: {clip_start} → {clip_end}")
            else:
                print("    WARN: Could not determine clip timestamps from transcript")

        # Extract and upload the clip
        if clip_start and clip_end and is_youtube:
            try:
                print(f"    Extracting clip: {clip_start} → {clip_end}")
                clip_path = extract_clip(video_url, clip_start, clip_end)
                media_id = upload_clip(clip_path)
                media_ids.append(media_id)
                print(f"    Clip uploaded: {media_id}")
            except Exception as e:
                print(f"    WARN: Clip extraction/upload failed ({e})")

        # Fallback: if clip failed, attach a GIF instead of deferring
        if not media_ids:
            print("    Falling back to GIF (clip unavailable)...")
            gif_path = pick_random_gif()
            if gif_path:
                try:
                    media_id = upload_media(gif_path)
                    media_ids.append(media_id)
                    print(f"    Fallback GIF uploaded: {media_id}")
                except Exception as e:
                    print(f"    WARN: Fallback GIF upload also failed ({e})")

    # No media
    if media_type == "none":
        print("    Media: none (text-only format)")

    return media_ids, qrt_url


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_idea(idea: dict, format_name: str) -> dict | None:
    """
    Process a single idea through the format pipeline.

    1. Look up format definition
    2. Enrich with source context
    3. Generate hook via Jordan (if format requires it)
    4. Generate post via Maya
    5. Handle media
    6. Create Typefully draft
    7. Update Notion
    """
    format_def = get_format(format_name)
    if not format_def:
        print(f"  ERROR: Unknown format '{format_name}'")
        return None

    idea_title = idea["idea"]
    idea_id = idea.get("id", "direct")
    source_url = idea.get("source_url", "")

    print(f"\n--- [{format_name}] Processing: {idea_title[:60]} ---")
    print(f"    Source: {source_url or 'none'}")
    print(f"    Pipeline: {format_def['pipeline_type']} | Media: {format_def['media_type']}")

    # Step 1: Enrich with context
    # Rule: if source is Twitter, ALWAYS enrich + QRT the source tweet
    # If the source tweet is itself a QRT, trace back to the original being quoted
    is_twitter_source = source_url and ("x.com" in source_url or "twitter.com" in source_url)
    is_youtube_source = source_url and ("youtube.com" in source_url or "youtu.be" in source_url)

    if is_twitter_source:
        idea = enrich_with_tweet(idea)
        # Force QRT for any Twitter-sourced content
        if not idea.get("qrt_source_url"):
            idea["qrt_source_url"] = source_url
        print(f"    QRT target: {idea.get('qrt_source_url', source_url)}")
    if is_youtube_source:
        idea = enrich_with_transcript(idea)

    # Step 2: Mark as Drafting
    if idea_id != "direct":
        update_idea_status(idea_id, "Drafting")
        print("    Status → Drafting")

    # Step 3: Generate hook via Jordan (TEMPORARILY DISABLED — Maya writes the full post)
    hook = ""
    # if format_def.get("hook_style") == "jordan":
    #     try:
    #         hook = generate_jordan_hook(idea, format_def) or ""
    #     except Exception as e:
    #         print(f"    WARN: Jordan hook failed ({e}). Falling back to Maya-only.")
    #         hook = ""

    # Step 4: Generate post via Maya
    prompt = build_format_prompt(idea, format_def)
    print(f"    Generating {format_name} post via Maya...")
    raw_post = write_thread(hook=hook, raw_facts="", topic=prompt)

    # Strip Maya's meta-text preamble (she sometimes includes "Here is the body:" etc.)
    post_text = _strip_maya_preamble(raw_post)

    if not post_text or len(post_text.strip()) < 50:
        print(f"    ERROR: Maya returned insufficient content ({len(post_text) if post_text else 0} chars)")
        if idea_id != "direct":
            update_idea_status(idea_id, "Triggered")  # revert
        return None

    print(f"    Generated {len(post_text)} chars")

    # Step 5: Handle media (inline — clips extracted and uploaded in this pass)
    media_ids, qrt_url = handle_media(idea, format_def, post_text=post_text)

    # Step 6: Create Typefully draft
    print("    Creating Typefully draft...")

    # Build scratchpad — keep it simple
    scratchpad_parts = []
    notion_url = f"https://www.notion.so/{idea_id.replace('-', '')}" if idea_id != "direct" else ""
    if notion_url:
        scratchpad_parts.append(f"Notion: {notion_url}")
    if source_url:
        scratchpad_parts.append(f"Source: {source_url}")
    # Include clip timestamps if available (for manual clipping)
    clip_start = idea.get("clip_start", "")
    clip_end = idea.get("clip_end", "")
    if clip_start and clip_end:
        scratchpad_parts.append(f"Clip: {clip_start} → {clip_end}")
    scratchpad = "\n".join(scratchpad_parts)

    try:
        draft = create_draft(
            post_text=post_text,
            qrt_url=qrt_url,
            media_ids=media_ids or None,
            draft_title=f"{format_name} — {idea_title[:80]}",
            scratchpad=scratchpad,
        )
        draft_id = str(draft.get("id", ""))
        print(f"    Draft created: {draft_id}")
    except Exception as e:
        print(f"    ERROR: Typefully draft creation failed: {e}")
        if idea_id != "direct":
            update_idea_status(idea_id, "Triggered")  # revert so it doesn't retry endlessly
            print("    Status reverted → Triggered")
        return None

    # Enable public sharing and get share URL
    share_url = ""
    if draft_id:
        try:
            share_url = enable_sharing(draft_id) or ""
            if share_url:
                print(f"    Share URL: {share_url}")
        except Exception as e:
            print(f"    WARN: Could not enable sharing ({e})")

    # Step 7: Update Notion — save draft ID + share URL + set status
    needs_media = format_def.get("media_type") in ("gif", "clip", "both") and not media_ids

    if draft_id and idea_id != "direct":
        save_typefully_draft_id(idea_id, draft_id, share_url=share_url)
        print("    Saved draft ID + Typefully Shared URL to Notion")

    if idea_id != "direct":
        if needs_media:
            update_idea_status(idea_id, "Needs Media")
            print("    Status → Needs Media (media agent will attach)")
        else:
            update_idea_status(idea_id, "Ready for Review")
            print("    Status → Ready for Review")

    # Step 8: Create Long-Form Post Library entry
    try:
        lf_post = create_longform_post(
            title=f"{format_name} — {idea_title[:80]}",
            video_url=source_url if "youtube.com" in source_url or "youtu.be" in source_url else "",
            clip_start=idea.get("clip_start", ""),
            clip_end=idea.get("clip_end", ""),
            content_angle=idea.get("content_angle", ""),
            post_text=post_text,
            status="Ready for Review",
            typefully_url=share_url,
            source_idea_url=idea_id if idea_id != "direct" else "",
        )
        print(f"    Long-Form Library entry created: {lf_post.get('id', '')[:20]}")
        print(f"    Source Idea relation linked")
    except Exception as e:
        print(f"    WARN: Could not create Long-Form Library entry ({e})")

    return {
        "idea_id": idea_id,
        "idea": idea_title,
        "format": format_name,
        "draft_id": draft_id,
        "post_length": len(post_text),
        "post_text": post_text,
        "qrt_url": qrt_url,
        "media_count": len(media_ids),
    }


# ---------------------------------------------------------------------------
# Library reader mode (Stage 2 — reads from Long-Form Post Library)
# ---------------------------------------------------------------------------

def process_library_entry(entry: dict) -> dict | None:
    """
    Process a single Long-Form Post Library entry through the format pipeline.
    Maps library entry fields to the idea dict that existing functions expect.
    """
    format_name = entry.get("format", "")
    if not format_name:
        print(f"  SKIP: Entry '{entry.get('title', '?')}' has no format assigned")
        return None

    format_def = get_format(format_name)
    if not format_def:
        print(f"  SKIP: Unknown format '{format_name}' on entry '{entry.get('title', '?')}'")
        return None

    entry_id = entry["id"]
    entry_title = entry.get("title", "Untitled")

    # Map library entry to idea-like dict
    idea = {
        "id": entry_id,
        "idea": entry_title,
        "content_angle": entry.get("content_angle", ""),
        "source_url": entry.get("source_url", ""),
        "source_account": entry.get("source_account", ""),
        "notes": entry.get("notes", ""),
        "urgency": entry.get("urgency", ""),
        "qrt_source_url": entry.get("qrt_url", ""),
    }

    print(f"\n--- [Library] [{format_name}] Processing: {entry_title[:60]} ---")
    print(f"    Source: {idea['source_url'] or 'none'}")

    # Enrich with context
    if format_def["pipeline_type"] == "qrt":
        idea = enrich_with_tweet(idea)
    elif format_def["pipeline_type"] == "clip":
        idea = enrich_with_tweet(idea)
        idea = enrich_with_transcript(idea)

    # Mark as Drafting in Library
    update_longform_post(entry_id, status="Drafting")
    print("    Library status → Drafting")

    # Jordan hook if needed
    hook = ""
    if format_def.get("hook_style") == "jordan":
        try:
            hook = generate_jordan_hook(idea, format_def) or ""
        except Exception as e:
            print(f"    WARN: Jordan hook failed ({e}). Falling back to Maya-only.")
            hook = ""

    # Generate post via Maya
    prompt = build_format_prompt(idea, format_def)
    print(f"    Generating {format_name} post via Maya...")
    post_text = write_thread(hook=hook, raw_facts="", topic=prompt)

    if not post_text or len(post_text.strip()) < 50:
        print(f"    ERROR: Maya returned insufficient content ({len(post_text) if post_text else 0} chars)")
        update_longform_post(entry_id, status="Angle Found")  # revert
        return None

    print(f"    Generated {len(post_text)} chars")

    # Handle media (inline — clips extracted and uploaded in this pass)
    media_ids, qrt_url = handle_media(idea, format_def, post_text=post_text)

    # Create Typefully draft
    print("    Creating Typefully draft...")
    draft = create_draft(
        post_text=post_text,
        qrt_url=qrt_url,
        media_ids=media_ids or None,
    )
    draft_id = str(draft.get("id", ""))
    print(f"    Draft created: {draft_id}")

    # Tag draft for Ellis QC review
    if draft_id:
        try:
            add_tag_to_draft(draft_id, "qc-review")
            print("    Tagged: qc-review")
        except Exception as e:
            print(f"    WARN: Could not tag draft ({e})")

    # Update Library entry — set to QC Review (Ellis evaluates before Toan sees it)
    update_longform_post(entry_id, status="QC Review", typefully_draft_id=draft_id)
    if qrt_url:
        update_longform_post(entry_id, qrt_url=qrt_url)
    print("    Library status → QC Review")

    return {
        "entry_id": entry_id,
        "title": entry_title,
        "format": format_name,
        "draft_id": draft_id,
        "post_length": len(post_text),
        "post_text": post_text,
        "qrt_url": qrt_url,
        "media_count": len(media_ids),
    }


def run_from_library(batch_size: int = 5) -> list[dict]:
    """
    Process Library entries with status='Angle Found'.
    Sorted by priority (lower = first), limited to batch_size.
    """
    entries = get_library_entries_by_status(status="Angle Found")
    if not entries:
        print("[Library] No 'Angle Found' entries to process.")
        return []

    # Sort by priority (None → end)
    entries.sort(key=lambda e: e.get("priority") or 999)
    batch = entries[:batch_size]

    print(f"[Library] Processing {len(batch)}/{len(entries)} entries (batch size {batch_size})")

    results = []
    for entry in batch:
        result = process_library_entry(entry)
        if result:
            results.append(result)

    print(f"\n=== [Library] Done: {len(results)}/{len(batch)} entries processed ===")
    for r in results:
        print(f"  [{r['format']}] {r['title'][:50]} → draft {r['draft_id']}")

    return results


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_format(format_name: str, idea_id: str | None = None) -> list[dict]:
    """Process all triggered ideas for a specific format, or a single idea."""
    format_def = get_format(format_name)
    if not format_def:
        print(f"Unknown format: {format_name}")
        print(f"Available: {', '.join(list_all_formats())}")
        return []

    if idea_id:
        idea = get_idea_by_id(idea_id)
        if not idea:
            print(f"Idea {idea_id} not found.")
            return []
        results = [process_idea(idea, format_name)]
    else:
        ideas = get_triggered_ideas(assigned_format=format_name)
        if not ideas:
            print(f"No triggered '{format_name}' ideas found.")
            return []
        print(f"Found {len(ideas)} triggered '{format_name}' idea(s)")
        results = [process_idea(idea, format_name) for idea in ideas]

    successful = [r for r in results if r is not None]
    print(f"\n=== [{format_name}] Done: {len(successful)}/{len(results)} processed ===")
    return successful


def run_all_formats() -> list[dict]:
    """Process triggered ideas across ALL formats."""
    all_results = []
    for format_name in FORMAT_REGISTRY:
        if format_name == "Tuki QRT":
            continue  # Tuki has its own pipeline — skip to avoid double-processing

        ideas = get_triggered_ideas(assigned_format=format_name)
        if ideas:
            print(f"\n{'='*60}")
            print(f"FORMAT: {format_name} ({len(ideas)} triggered)")
            print(f"{'='*60}")
            for idea in ideas:
                result = process_idea(idea, format_name)
                if result:
                    all_results.append(result)

    if not all_results:
        print("No triggered ideas found for any format.")
    else:
        print(f"\n{'='*60}")
        print(f"ALL FORMATS DONE: {len(all_results)} posts created")
        for r in all_results:
            print(f"  [{r['format']}] {r['idea'][:50]} → draft {r['draft_id']}")
        print(f"{'='*60}")

    return all_results


def run_poll():
    """Continuously poll for triggered ideas across all formats."""
    print(f"Format Pipeline — polling every {POLL_INTERVAL_SECONDS}s")
    print(f"Monitoring formats: {', '.join(f for f in FORMAT_REGISTRY if f != 'Tuki QRT')}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            results = run_all_formats()
            # Also process Library entries (Stage 2)
            library_results = run_from_library(batch_size=5)
            if library_results:
                results.extend(library_results) if isinstance(results, list) else None
            if not results:
                print("[POLL] No triggered ideas. Sleeping...")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nPipeline stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Format Pipeline — unified content generation")
    parser.add_argument("--format", type=str, help="Format name (e.g. 'Bark QRT', 'Stat Bomb')")
    parser.add_argument("--all", action="store_true", help="Process all formats")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--idea-id", type=str, help="Process a specific idea by Notion page ID")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for triggered ideas")
    parser.add_argument("--list", action="store_true", help="List all available formats")
    parser.add_argument("--from-library", action="store_true", help="Process 'Angle Found' entries from Long-Form Post Library")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for --from-library mode (default 5)")
    args = parser.parse_args()

    if args.list:
        print("Available formats:")
        for name, fmt in FORMAT_REGISTRY.items():
            print(f"  {name:25s} | {fmt['pipeline_type']:5s} | media: {fmt['media_type']:5s} | {'thread' if fmt['is_thread'] else 'post'}")
        return

    if args.from_library:
        run_from_library(batch_size=args.batch_size)
        return

    if args.poll:
        run_poll()
    elif args.all:
        run_all_formats()
    elif args.format:
        run_format(args.format, idea_id=args.idea_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
