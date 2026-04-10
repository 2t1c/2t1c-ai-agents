---
name: media-attacher
description: >
  Attach reaction GIFs and QRT media to Typefully drafts. Triggered when:
  drafts are tagged 'needs-media', or when told to "attach media", "add GIF",
  or "process media queue". Uses the local reaction GIF folder and Typefully API.
---

# Media Attacher

You handle media attachment for GeniusGTX content. Every long-form post needs at least one
media element unless it's a text-only format.

## Media Priority Rules

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 — QRT | Source is a tweet (x.com or twitter.com URL) | Attach as Quote Retweet |
| 2 — GIF | No QRT available | Pick random GIF from local folder |
| 3 — Both | Breaking news or Tuki format | QRT + GIF together |

## Text-Only Exceptions (no media required)
- "Let Me Get This Straight" format
- "Long-Form Text Only" format
- "X Article" format (uses thumbnail)

## How to Attach Media

### Option A: Run the pipeline script
```bash
cd /Users/toantruong/Desktop/AI Agents/2t1c-content-ops
python -m pipeline.media_attacher --once
```
This processes ALL drafts tagged `needs-media` in one pass.

### Option B: Process a specific draft
```bash
python -m pipeline.media_attacher --draft-id <DRAFT_ID>
```

### Option C: Manual via Typefully MCP
1. List drafts with `typefully_list_drafts` filtered by tag `needs-media`
2. For each draft, determine media needs using the priority rules above
3. If GIF needed: pick from `skills/writing-system/Reaction GIF for twitter content/`
4. Upload via `typefully_create_media_upload`
5. Edit draft to attach media via `typefully_edit_draft`
6. Update tag from `needs-media` to `ready-for-review`

## GIF Folder
Location: `skills/writing-system/Reaction GIF for twitter content/`
Contains: 14 reaction GIFs (.mp4) and images (.jpg)
Selection: Random is fine. Match mood to the post's closer tone if possible.

## Formats Requiring BOTH QRT + GIF
- Tuki QRT
- Summary QRT + GIF (Tuki Style)
- Any post with urgency "Breaking"
