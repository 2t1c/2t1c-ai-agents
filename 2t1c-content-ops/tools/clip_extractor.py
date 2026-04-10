"""
Clip Extractor — YouTube video → timestamped clip → Typefully upload.

Three-step workflow:
1. Fetch transcript with timestamps (for identifying clip-worthy sections)
2. Extract clip via local clip.sh (yt-dlp + ffmpeg)
3. Upload clip to Typefully and return media_id

Usage:
    from tools.clip_extractor import fetch_transcript, extract_clip, upload_clip

    # Step 1: Get transcript to find the right section
    transcript = fetch_transcript("https://youtube.com/watch?v=abc123")

    # Step 2: Extract the clip locally
    clip_path = extract_clip("https://youtube.com/watch?v=abc123", "2:15", "2:45")

    # Step 3: Upload to Typefully
    media_id = upload_clip(clip_path)
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

CLIP_SH = Path.home() / "Downloads" / "Apps & Installers" / "YouTube Clipper FAST" / "clip.sh"
FFMPEG_PATH = Path.home() / "Downloads" / "Apps & Installers" / "YouTube Clipper FAST" / "YouTube Clipper Source Code" / "quote clipper" / "node_modules" / "ffmpeg-static" / "ffmpeg"
CLIPS_DIR = Path.home() / "ytclipper-fast" / "clips"
TEMP_DIR = Path.home() / "ytclipper-fast" / "temp"


def _extract_video_id(url: str) -> str:
    """Extract the 11-character YouTube video ID from a URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")


def fetch_transcript(url: str, languages: list[str] | None = None) -> list[dict]:
    """
    Fetch the transcript for a YouTube video with timestamps.

    Returns a list of segments:
        [{"start": 0.0, "duration": 3.2, "text": "..."}, ...]

    Each segment includes start time in seconds, duration, and text.
    Use this to identify which sections are worth clipping.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = _extract_video_id(url)
    langs = languages or ["en"]

    ytt = YouTubeTranscriptApi()
    fetched = ytt.fetch(video_id, languages=langs)

    # Normalize to list of dicts (the new API returns FetchedTranscript objects)
    transcript = [
        {"start": seg.start, "duration": seg.duration, "text": seg.text}
        for seg in fetched
    ]
    return transcript


def format_transcript(transcript: list[dict], chunk_seconds: int = 30) -> str:
    """
    Format a transcript into readable chunks with timestamp markers.

    Groups segments into chunks (default 30s) for easier scanning.
    Output format:
        [0:00 - 0:30]
        The text of what was said in this window...

        [0:30 - 1:00]
        Next chunk of text...
    """
    if not transcript:
        return "(empty transcript)"

    lines = []
    chunk_start = 0.0
    chunk_texts = []

    for seg in transcript:
        seg_start = seg["start"]

        if seg_start >= chunk_start + chunk_seconds and chunk_texts:
            ts_start = _seconds_to_timestamp(chunk_start)
            ts_end = _seconds_to_timestamp(chunk_start + chunk_seconds)
            lines.append(f"[{ts_start} - {ts_end}]")
            lines.append(" ".join(chunk_texts))
            lines.append("")
            chunk_start += chunk_seconds
            chunk_texts = []

        chunk_texts.append(seg["text"])

    if chunk_texts:
        ts_start = _seconds_to_timestamp(chunk_start)
        ts_end = _seconds_to_timestamp(transcript[-1]["start"] + transcript[-1].get("duration", 0))
        lines.append(f"[{ts_start} - {ts_end}]")
        lines.append(" ".join(chunk_texts))

    return "\n".join(lines)


def _seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or H:MM:SS format."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _get_scaling_params(video_type: str, total_duration_seconds: float) -> dict:
    """
    Determine snippet count range and clip length range based on video type and duration.

    Returns dict with: snippet_min, snippet_max, clip_min_minutes, clip_max_minutes
    """
    duration_minutes = total_duration_seconds / 60

    if video_type.lower() == "podcast":
        # Podcasts: ~1 snippet per 10-15 min of content, clips can be longer
        snippet_min = max(2, int(duration_minutes / 15))
        snippet_max = max(4, int(duration_minutes / 10))
        clip_min = 2
        clip_max = 6
    else:
        # Normal videos: ~1 snippet per 8-10 min, tighter clips
        snippet_min = max(1, int(duration_minutes / 10))
        snippet_max = max(2, int(duration_minutes / 8))
        clip_min = 1
        clip_max = 3

    # Hard caps
    snippet_max = min(snippet_max, 15)
    snippet_min = min(snippet_min, snippet_max)

    return {
        "snippet_min": snippet_min,
        "snippet_max": snippet_max,
        "clip_min": clip_min,
        "clip_max": clip_max,
    }


def build_snippet_analysis_prompt(
    formatted_transcript: str,
    video_url: str,
    topic_context: str = "",
    video_type: str = "Normal",
    total_duration_seconds: float = 0,
) -> str:
    """
    Build the prompt for Claude to analyze a transcript and identify clip-worthy snippets.

    This is the intelligence layer. Feed the output to Claude, and it returns
    structured CLIP BRIEFs with timestamps ready for extract_clip().

    Snippet count and clip length scale dynamically based on video type and duration.

    Args:
        formatted_transcript: Output from format_transcript()
        video_url: The YouTube URL (included in the brief for extraction)
        topic_context: Optional context about what angle you're writing about
        video_type: "Normal" or "Podcast" — affects snippet types and scaling
        total_duration_seconds: Video duration in seconds — drives snippet count scaling
    """
    # Scale snippet/clip targets to video size
    params = _get_scaling_params(video_type, total_duration_seconds)
    duration_minutes = total_duration_seconds / 60

    context_line = ""
    if topic_context:
        context_line = f"\nCONTENT ANGLE: {topic_context}\nPrioritize snippets that serve this angle. But flag any other standout moments too.\n"

    # Base snippet types (both formats)
    snippet_types = """
1. THE INSIGHT — A section where the speaker explains something that reframes how you see the topic. The "oh shit" moment where the viewer's mental model shifts. This is the highest-value clip because it delivers the kind of thinking GeniusGTX is built around. Look for: a clear before/after in understanding, a counterintuitive explanation, a connection most people miss.

2. THE EVIDENCE — A section packed with specific facts, numbers, dates, or examples that prove something surprising. Not the opinion. The proof. Look for: stacked specifics, data that contradicts common belief, historical details that make the pattern undeniable.

3. THE STORY — A section where the speaker tells a contained narrative with a beginning, middle, and payoff. A person, a moment, a consequence. Look for: named individuals, specific dates/places, dramatic tension, a clear resolution or twist.

4. THE CONFRONTATION — A section where the speaker challenges a widely held belief head-on. Not a gentle suggestion. A direct "here's why that's wrong." Look for: explicit disagreement with mainstream view, strong language, the moment the speaker gets genuinely animated.

5. THE PREDICTION — A section where the speaker makes a specific claim about what happens next. Not vague "things will change." Specific. Look for: timelines, named institutions, described mechanisms for how it unfolds."""

    # Podcast-specific snippet types (appended for podcasts)
    if video_type.lower() == "podcast":
        snippet_types += """

6. THE DISAGREEMENT — A section where the two speakers clash or push back on each other. Not polite nodding — genuine tension. Look for: "I actually disagree," interruptions, the moment the energy shifts. The clip should capture both sides.

7. THE REVELATION — A section where a speaker shares something personal, surprising, or previously unknown. An admission, a behind-the-scenes detail, a "I've never told this publicly" moment. Look for: the shift in tone, the pause before they say it.

8. THE "SAY THAT AGAIN" MOMENT — A section where something is said so clearly and powerfully that it deserves to be replayed. Often a single sentence that captures an entire philosophy. Look for: the moment where even the host reacts — laughs, goes quiet, or says "wait."

9. THE HOST REACTION — A section where the host's response IS the content. Their mind visibly changes, they connect two ideas the guest didn't, or they challenge the guest in a way that elevates the conversation. Look for: genuine surprise, reframing, the host adding value not just asking questions."""

    return f"""SNIPPET ANALYSIS — Identify clip-worthy moments from this transcript.

VIDEO: {video_url}
TYPE: {video_type.upper()} ({duration_minutes:.0f} minutes)
TARGET SNIPPETS: {params['snippet_min']}-{params['snippet_max']} (scaled to video length)
TARGET CLIP LENGTH: {params['clip_min']}-{params['clip_max']} minutes each
{context_line}
---

TRANSCRIPT:
{formatted_transcript}

---

YOUR JOB: Identify {params['snippet_min']}-{params['snippet_max']} clip-worthy snippets from this {duration_minutes:.0f}-minute {video_type.lower()}. Each snippet should be {params['clip_min']}-{params['clip_max']} minutes long.

WHAT MAKES A GOOD SNIPPET:

A good snippet is a self-contained moment that would make someone stop scrolling. It needs to work on its own without the rest of the video. The viewer should feel like they just learned something or saw something they can't unsee.

Snippet types to look for (in priority order):
{snippet_types}

SNIPPET SELECTION RULES:
- Each snippet must be {params['clip_min']}-{params['clip_max']} minutes. The viewer needs enough time to be pulled in.
- The snippet must START clean. Find the sentence where the thought begins, not the middle of a transition. Add 5 seconds of buffer before the first word.
- The snippet must END clean. Find the natural pause after the thought concludes. Not mid-sentence. Add 3 seconds of buffer after the last word.
- Every snippet must stand alone. If it requires context from earlier in the video to make sense, it's not a good snippet.
- Overlapping snippets are fine. The same section can serve different angles.
- QUALITY FLOOR: If there are fewer than {params['snippet_min']} genuinely strong moments, say so. Do NOT pad with weak snippets to hit the target. A video with 2 great clips beats one with 5 mediocre ones.

OUTPUT FORMAT — For each snippet, output this exact structure:

```
SNIPPET [number] — [type: Insight / Evidence / Story / Confrontation / Prediction{' / Disagreement / Revelation / Say That Again / Host Reaction' if video_type.lower() == 'podcast' else ''}]

Timestamp: [START] → [END]
Duration: [X minutes Y seconds]
Topic: [one-line description of what this section covers]

Key quote: "[the single most powerful sentence from this section]"

Why this works: [one sentence — what makes this snippet stand alone as content]

CLIP BRIEF
Source video: {video_url}
Timestamp range: [START] — [END]
Why this section: [what makes it the right clip]
Target length: [duration]
```

After all snippets, add:

```
EXTRACTION PRIORITY
1. [snippet number] — [one-line reason this is the best clip]
2. [snippet number] — [reason]
...
```

If the transcript has fewer than {params['snippet_min']} viable snippets, say so. Don't force it."""


def build_angle_expansion_prompt(snippets: list[dict], video_type: str = "Normal") -> str:
    """
    Build the prompt for Claude to expand snippets into format-specific content angles.

    This is the bridge between snippet analysis (about the VIDEO) and post creation
    (about the CONTENT STRATEGY). One snippet can produce multiple posts across formats.

    Args:
        snippets: Parsed snippet dicts from _parse_snippets()
        video_type: "Normal" or "Podcast"
    """
    # Build snippet summary for the prompt
    snippet_lines = []
    for s in snippets:
        snippet_lines.append(
            f"SNIPPET {s['number']} — {s['type']}\n"
            f"  Topic: {s['topic']}\n"
            f"  Key quote: \"{s['key_quote']}\"\n"
            f"  Why it works: {s['why']}\n"
            f"  Clip: {s['start']} → {s['end']}"
        )
    snippet_block = "\n\n".join(snippet_lines)

    return f"""ANGLE EXPANSION — Turn these video snippets into content angles.

You have {len(snippets)} clip-worthy snippets from a {video_type.lower()}. Your job is to figure out what POSTS each snippet can support.

One snippet can produce multiple posts across different formats. The goal is maximum high-quality content from every strong moment.

---

SNIPPETS:
{snippet_block}

---

AVAILABLE FORMATS (choose from these):

WITH CLIP (the video clip is attached to the post):
- Video Clip Post — 10-20 lines. The clip does the heavy lifting; text frames it. Good for visually compelling moments.
- Clip Commentary — 15-30 lines. Editorial commentary where the clip supports the argument. Good for insight-heavy snippets.
- Clip Thread — 3-7 tweets, each with a clip moment. Good when multiple snippets tell a sequential story.

TEXT-ONLY (no clip, the snippet's IDEA is extracted into standalone content):
- Commentary Post — 15-30 lines, editorial reaction. Good when the idea is strong but the clip isn't visually necessary.
- Explainer — 15-35 lines, educational breakdown. Good for complex topics that need step-by-step explanation.
- Contrarian Take — 15-25 lines, challenges mainstream view. Good when the snippet directly contradicts common belief.
- Stat Bomb — 10-25 lines, data-driven. Good when the snippet is packed with numbers and facts.
- Thread — 4-10 tweets, narrative arc. Good when the topic needs more room to breathe.

RULES:
1. Every snippet should produce AT LEAST 1 post with clip (Video Clip Post or Clip Commentary).
2. Strong snippets should ALSO produce 1-2 text-only formats — different angle, same insight.
3. Don't force formats. If a snippet only supports 1 post, that's fine. If it supports 4, that's fine too.
4. Each angle must feel DISTINCT. Two posts from the same snippet should not feel like the same post with different formatting.
5. Weak snippets get 1 post. Strong snippets get 2-4.
6. For Clip Threads: only suggest this if 2+ snippets naturally form a sequential narrative.

OUTPUT FORMAT:

For each angle, output this structure:

```
ANGLE [number]
Source snippet: [snippet number]
Format: [format name from list above]
Uses clip: Yes / No
Angle: [one sentence — what specific take/perspective does this post take?]
Why this format: [one sentence — why this format is the right vessel for this angle]
Strength: High / Medium  (High = stop-scrolling potential, Medium = solid but not a banger)
```

After all angles, add:

```
SUMMARY
Total angles: [count]
With clip: [count]
Text-only: [count]
High strength: [count]
Medium strength: [count]

PRODUCTION PRIORITY (write these first):
1. Angle [number] — [reason]
2. Angle [number] — [reason]
...
```

Be aggressive about finding angles but honest about strength. 3 high-strength angles > 8 medium ones."""


def extract_clip(url: str, start: str, end: str) -> Path:
    """
    Extract a clip from a YouTube video using the local clip.sh tool.

    Args:
        url: YouTube video URL
        start: Start timestamp (e.g., "2:15" or "1:02:30")
        end: End timestamp (e.g., "2:45" or "1:03:00")

    Returns:
        Path to the extracted clip file.

    Raises:
        FileNotFoundError: If clip.sh is not found.
        RuntimeError: If clip extraction fails.
    """
    if not CLIP_SH.exists():
        raise FileNotFoundError(
            f"clip.sh not found at {CLIP_SH}. "
            "Expected at ~/Downloads/YouTube Clipper FAST/clip.sh"
        )

    video_id = _extract_video_id(url)
    start_safe = start.replace(":", "-")
    end_safe = end.replace(":", "-")
    expected_output = CLIPS_DIR / f"{video_id}_{start_safe}_{end_safe}.mp4"

    print(f"Extracting clip: {start} → {end}")
    print(f"Video: {url}")
    print(f"Expected output: {expected_output}")

    result = subprocess.run(
        ["bash", str(CLIP_SH), url, start, end],
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"clip.sh failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    if not expected_output.exists():
        raise RuntimeError(
            f"Clip extraction appeared to succeed but file not found at {expected_output}\n"
            f"stdout: {result.stdout}"
        )

    size_mb = expected_output.stat().st_size / (1024 * 1024)
    print(f"Clip saved: {expected_output} ({size_mb:.1f} MB)")
    return expected_output


def upload_clip(clip_path: Path, social_set_id: int | None = None) -> str:
    """
    Upload a clip to Typefully and return the media_id.

    Uses the existing typefully_client upload pipeline.

    Args:
        clip_path: Path to the .mp4 clip file.
        social_set_id: Typefully social set ID. Defaults to GeniusGTX_2.

    Returns:
        The Typefully media_id string.
    """
    from tools.typefully_client import upload_media

    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    print(f"Uploading to Typefully: {clip_path.name}")
    media_id = upload_media(clip_path, social_set_id=social_set_id)
    print(f"Upload complete. Media ID: {media_id}")
    return media_id


def list_clips() -> list[Path]:
    """List all clips in the clips directory, sorted by modification time (newest first)."""
    if not CLIPS_DIR.exists():
        return []
    clips = sorted(CLIPS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return clips


def clean_temp() -> int:
    """Remove downloaded full videos from temp dir to save space. Returns bytes freed."""
    if not TEMP_DIR.exists():
        return 0
    freed = 0
    for f in TEMP_DIR.iterdir():
        if f.is_file():
            freed += f.stat().st_size
            f.unlink()
    return freed


# --- CLI interface ---

def main():
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Clip Extractor")
    sub = parser.add_subparsers(dest="command")

    # transcript
    t = sub.add_parser("transcript", help="Fetch and display video transcript")
    t.add_argument("url", help="YouTube video URL")
    t.add_argument("--chunk", type=int, default=30, help="Chunk size in seconds (default 30)")

    # snippets (transcript + analysis prompt)
    s = sub.add_parser("snippets", help="Fetch transcript and output snippet analysis prompt")
    s.add_argument("url", help="YouTube video URL")
    s.add_argument("--topic", default="", help="Content angle to prioritize")

    # clip
    c = sub.add_parser("clip", help="Extract a clip from a video")
    c.add_argument("url", help="YouTube video URL")
    c.add_argument("start", help="Start timestamp (e.g. 2:15)")
    c.add_argument("end", help="End timestamp (e.g. 2:45)")

    # upload
    u = sub.add_parser("upload", help="Upload a clip to Typefully")
    u.add_argument("path", help="Path to clip file")

    # list
    sub.add_parser("list", help="List existing clips")

    # clean
    sub.add_parser("clean", help="Remove temp downloads")

    args = parser.parse_args()

    if args.command == "transcript":
        transcript = fetch_transcript(args.url)
        print(format_transcript(transcript, chunk_seconds=args.chunk))

    elif args.command == "snippets":
        transcript = fetch_transcript(args.url)
        formatted = format_transcript(transcript, chunk_seconds=30)
        prompt = build_snippet_analysis_prompt(formatted, args.url, topic_context=args.topic)
        print(prompt)

    elif args.command == "clip":
        path = extract_clip(args.url, args.start, args.end)
        print(f"\nClip ready: {path}")

    elif args.command == "upload":
        media_id = upload_clip(Path(args.path))
        print(f"\nMedia ID: {media_id}")

    elif args.command == "list":
        clips = list_clips()
        if not clips:
            print("No clips found.")
        else:
            for clip in clips:
                size_mb = clip.stat().st_size / (1024 * 1024)
                print(f"  {clip.name} ({size_mb:.1f} MB)")

    elif args.command == "clean":
        freed = clean_temp()
        print(f"Freed {freed / (1024*1024):.1f} MB from temp directory.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
