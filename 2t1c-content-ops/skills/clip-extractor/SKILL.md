---
name: clip-extractor
description: >
  Extract video clips from YouTube and attach to Typefully drafts.
  Triggered when: a post requires a video clip (Formats 6, 7, 8, 9),
  or when told to "extract clip", "clip this video", "get the clip",
  or "run clip workflow". Uses yt-dlp + ffmpeg via local clip.sh tool.
---

# Clip Extractor — YouTube Video → Typefully Draft

You extract clips from YouTube videos and attach them to Typefully drafts.
This is the complete clip workflow from the Media Workflow Guide.

## When to Use This

Formats that require video clips:
- Format 6: One-Tweet News + Clip
- Format 7: Short Caption + Video
- Format 8: Quote-Extract + Video
- Format 9: Educational Long-Form + Video

## The Full Pipeline

```
[Source video URL]
     ↓
[Fetch transcript → identify clip-worthy section]
     ↓
[Extract clip via clip.sh — yt-dlp + ffmpeg]
     ↓
[Upload to Typefully → get presigned S3 URL]
     ↓
[Upload clip to S3] ← ⚠️ 1 hour window
     ↓
[Create/edit Typefully draft with media_id]
```

## Step-by-Step Execution

### Step 1 — Fetch Transcript & Identify Clip

Use the clip_extractor tool to get the transcript:

```python
from tools.clip_extractor import fetch_transcript, format_transcript

transcript = fetch_transcript("https://youtube.com/watch?v=VIDEO_ID")
formatted = format_transcript(transcript, chunk_seconds=30)
```

Or via CLI:
```bash
cd /Users/toantruong/Desktop/AI Agents/2t1c-content-ops
python3 -c "from tools.clip_extractor import fetch_transcript, format_transcript; t = fetch_transcript('VIDEO_URL'); print(format_transcript(t))"
```

Read the transcript. Identify the best clip-worthy section using these criteria:
1. **THE INSIGHT** — reframes understanding (highest priority)
2. **THE EVIDENCE** — packed with specific facts/numbers
3. **THE STORY** — contained narrative with payoff
4. **THE CONFRONTATION** — challenges widely held belief
5. **THE PREDICTION** — specific claim about what happens next

### Step 2 — Write Clip Brief

Output this structure:
```
CLIP BRIEF
Source video: [YouTube URL]
Transcript excerpt: [exact text of the section to clip]
Timestamp range: [START — END]
Why this section: [what makes it the right clip]
Target length: 2-5 minutes
```

### Step 3 — Extract Clip

Use clip.sh (the local extraction tool):

```bash
export PATH="$HOME/.local/bin:$PATH"
bash ~/Downloads/YouTube\ Clipper\ FAST/clip.sh "VIDEO_URL" "START" "END"
```

Arguments:
- VIDEO_URL: Full YouTube URL
- START: Timestamp like "2:15" or "1:02:30"
- END: Timestamp like "4:30" or "1:05:00"

Output goes to: `~/ytclipper-fast/clips/VIDEO_ID_START_END.mp4`

Or via Python:
```python
from tools.clip_extractor import extract_clip
clip_path = extract_clip("VIDEO_URL", "2:15", "4:30")
```

### Step 4 — Upload to Typefully

Use the Typefully MCP tools:

1. **Get presigned URL:**
   Call `typefully_create_media_upload` with `file_name: "clip.mp4"`

2. **Upload raw bytes:**
   ```bash
   curl -T /path/to/clip.mp4 "PRESIGNED_URL"
   ```
   ⚠️ No extra headers — plain PUT with raw bytes only. URL expires in 1 hour.

3. **Create/edit draft** with the returned `media_id`

### Step 5 — Tag Draft

Tag the draft as `ready-for-review`. All content goes through Toản.

## Tool Locations

| Tool | Path |
|------|------|
| clip.sh | `~/Downloads/YouTube Clipper FAST/clip.sh` |
| yt-dlp | `~/.local/bin/yt-dlp` |
| ffmpeg | `~/.local/bin/ffmpeg` |
| clip_extractor.py | `tools/clip_extractor.py` (Python module) |
| Clips output | `~/ytclipper-fast/clips/` |
| Temp downloads | `~/ytclipper-fast/temp/` |

## Multiple Clips (Threads)

For threads with one clip per tweet:
1. Extract ALL clips first
2. Upload ALL clips and collect ALL media_ids
3. THEN create all Typefully drafts with their respective media_ids
4. Never create drafts until all clips are uploaded

## Clip Rules

- Target length: 2-5 minutes (flexible)
- Single posts: max 1 clip
- Threads: 1 clip per tweet where needed
- Always start 5 seconds before the speaker begins the thought
- Always end 3 seconds after the thought concludes
- Clip must stand alone — no external context required
