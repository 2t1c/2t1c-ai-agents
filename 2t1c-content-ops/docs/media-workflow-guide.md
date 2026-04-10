# 🎬 Media Workflow Guide

> Source of truth: Notion page `33004fca-1794-81e3-bd37-d73e13b82d25`
> Last synced: 2026-03-28

The complete workflow for every media type used across GeniusGTX content formats. Agents read this before producing any post that requires media.

Four media types. Four workflows. The agent determines which applies based on the format, then executes the correct process.

---

## Media Decision Tree

Before writing any post, determine the media type:

```
Does this format require a GIF by design?
→ Formats 1, 3, 4, 5 → Run GIF Workflow

Does this format require a video clip?
→ Formats 6, 7, 8, 9 → Run Clip Workflow

Does this format require a two-panel image?
→ Not in use. Format 6 moved to clip workflow.

None of the above?
→ No media. Declare MEDIA: None and proceed.
```

---

## WORKFLOW 1 — No Media

**Formats that use this:** Format 2 (Let Me Get This Straight), Format 10 (Long-Form Text Only), and any format where the writing carries the full weight.

**Process:** Agent declares `MEDIA: None` in the output. No further action.

---

## WORKFLOW 2 — GIF

**Formats that use this:** Format 1 (Let Me Explain), Format 3 (One-Liner Observation), Format 4 (Tuki Style), Format 5 (Daily Roundup).

**Current state:** GIFs are pulled from a personal library. The library is a flat collection browsed manually.

**What the agent does:**

At the end of every post that requires a GIF, the agent outputs a GIF brief:

```
GIF BRIEF
Mood: [one word — dread / shock / disbelief / dark realization / contempt / exhaustion]
Visual style: [describe the scene — close-up eyes, person staring at screens, slow collapse, building burning, etc.]
Avoid: [funny / lighthearted / meme-style — always]
Search terms: [2-3 keywords to try in the library]
```

**GIF style rules (non-negotiable across all formats):**
- Always dark/cinematic — serious movie scenes, investigation footage, contemplative moments
- Never funny meme GIFs — wrong tone for every format
- Duration: 0:01 to 0:13 seconds
- The GIF amplifies the mood of the closer — it never contradicts it

**GIF mood by topic:**
- Crime / fraud / insider trading → detective or investigation scenes (reading documents, screens)
- War / geopolitics / conflict → apocalyptic or tension scenes (person before fire, city at night)
- Death / philosophical → contemplative movie scenes (man alone, slow zoom)
- Security / surveillance / hack → physical trap or mechanism GIFs
- Institutional betrayal / systemic failure → person staring in disbelief, slow collapse

**Upgrade path:** When the library gets tagged by mood, the agent can reference specific GIFs by mood tag directly.

---

## WORKFLOW 3 — Images

Not in use. AI image generation removed. Format 6 moved to the clip workflow.

---

## WORKFLOW 4 — Video Clips

**Formats that use this:** Format 6 (One-Tweet News + Clip), Format 7 (Short Caption + Video), Format 8 (Quote-Extract + Video), Format 9 (Educational Long-Form + Video).

### Step-by-Step: Single Clip (Long-Form Posts)

**Step 0 — Snippet Analysis (find the right section)**

Before writing a clip brief, run snippet analysis on the source video. This is the intelligence step that identifies which 2-4 minute sections are worth clipping.

```
1. Fetch the transcript:
   python3 -m tools.clip_extractor transcript "<youtube-url>"

2. Run snippet analysis (generates the full prompt):
   python3 -m tools.clip_extractor snippets "<youtube-url>" --topic "optional content angle"

3. Claude reads the transcript and identifies 2-5 clip-worthy snippets
```

Five snippet types (priority order):
1. **The Insight** — Reframes how you see the topic. The "oh shit" moment.
2. **The Evidence** — Stacked specifics that prove something surprising.
3. **The Story** — Contained narrative with a person, a moment, a consequence.
4. **The Confrontation** — Directly challenges a widely held belief.
5. **The Prediction** — Specific claim about what happens next.

Snippet rules:
- Each snippet must be **2-4 minutes** long. Not shorter.
- Must start and end clean (complete thoughts, not mid-sentence).
- Must stand alone without context from earlier in the video.
- Add 5s buffer before start, 3s buffer after end.

**Step 1 — Agent writes clip brief (from snippet analysis)**

```
CLIP BRIEF
Source video: [YouTube URL or video title + channel name]
Transcript excerpt: [paste the exact section of transcript that should be clipped]
Timestamp range (if known): [HH:MM:SS — HH:MM:SS]
Why this section: [one sentence — what makes this the right clip for this post]
Target length: 2-4 minutes
```

**Step 2 — Claude Code executes extraction**

The clip tool extracts the identified section from the source video:
```
python3 -m tools.clip_extractor clip "<youtube-url>" "<start>" "<end>"
```

**Step 3 — Typefully pipeline runs**

```
1. Call upload endpoint → receive presigned S3 URL
2. Upload clip to S3 using presigned URL
   ⚠️ Timing constraint: URL expires in 1 hour — upload must complete within this window
3. Poll for media_id (wait for Typefully to confirm upload)
4. Create Typefully draft with:
   - media_id
   - post text (the full post body)
   - tags
   - publish_at (scheduled time)
```

### Multiple Clips (Threads Only)

```
1. Run Steps 1-2 of the clip brief for each clip
2. Loop Steps 3a-3c (upload → poll) for EACH clip
3. Collect ALL media_ids before creating any drafts
4. Create all Typefully drafts in sequence with their respective media_ids
```

**Key rule:** Collect all media_ids first. Do not create drafts until all clips are uploaded and confirmed.

---

## Full Pipeline Reference (Clip → Typefully)

```
[Source video]
     ↓
[Clip extractor — transcript excerpt or timestamp]
     ↓
[Upload endpoint] → presigned S3 URL
     ↓
[Upload clip to S3] ← ⚠️ 1 hour window
     ↓
[Poll for media_id]
     ↓
[Create Typefully draft]
  → media_id
  → post text
  → tags
  → publish_at
     ↓
[Typefully draft: video attached + scheduled + tagged]
```

---

*Version 1.2 — Updated March 2026 — Image workflow removed. Format 6 moved to clip workflow. Three active media types: No Media, GIF, Clip.*
