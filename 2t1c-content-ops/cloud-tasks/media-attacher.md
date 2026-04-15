# Task 3: Media Attacher Agent (LOCAL)

You are the media attachment agent for GeniusGTX. Your job: find posts that need media in Notion, extract video clips or find QRT tweets, attach them to Typefully drafts, and update Notion.

This task runs LOCALLY because it needs ffmpeg for clip extraction.

## Step 1: Find posts that need media

### Primary method — Chrome browser (Pipeline Board)

1. Get a tab with `mcp__Claude_in_Chrome__tabs_context_mcp` (createIfEmpty: true).
2. Navigate to the Pipeline Board:
   ```
   mcp__Claude_in_Chrome__navigate(url: "https://www.notion.so/c4fed84bf0a94459bad369c93f3de40a", tabId: <tabId>)
   ```
3. Take a screenshot with `mcp__Claude_in_Chrome__computer(action: "screenshot")` to visually confirm the board and see the "Needs Media" column with its item count.
4. Read the board text with `mcp__Claude_in_Chrome__get_page_text` to get the full item list.
5. For each card visible in the "Needs Media" column, click on it to open the page — the page ID appears in the URL (`?p=<page_id>`).
6. Immediately call `mcp__8c435ebc-a4fb-4d84-8d81-5f650405b5f9__notion-fetch` on that page ID to get full properties (Draft ID, Source URL, Source Type, Notes).
7. Press Escape to close the modal and repeat for the next card.

Cap at 10 qualifying ideas per run.

**Also scan "Ready for Review" posts for broken QRTs:**
After collecting "Needs Media" items, run a secondary scan on up to 5 posts currently in the `"Ready for Review"` status where `quote_post_url` is set. These will go through QC check 4b (live QRT verification) only — skip all other processing. If their QRT is found to be broken, apply the broken QRT remediation flow (see QC check 4b below) and leave them in "Ready for Review" after fixing. Cap this secondary scan at 5 items and count them separately from the 10 "Needs Media" items.

### Fallback — Notion API property filter

If Chrome is unavailable, use `mcp__notion__API-query-data-source` on the Idea Pipeline database (`c4fed84bf0a94459bad369c93f3de40a`) with a filter for `Status = "Needs Media"`.

### Fallback — Notion MCP search + fetch filter

If the API also fails, use `mcp__8c435ebc-a4fb-4d84-8d81-5f650405b5f9__notion-search` with:
- `data_source_url: collection://330aef7b-3feb-401e-abba-28452441a64d`
- `query: "Needs Media"`
- `page_size: 25`

Then for each result, call `notion-fetch` and keep only pages where `Status` = `"Needs Media"`.

### For each qualifying idea, read:
- Typefully Draft ID(s) — may be comma-separated if multiple drafts
- Source URL
- Source Type (YouTube / Twitter / Articles)
- Notes (may contain clip timestamps in format `"Clip: MM:SS → MM:SS"`)

---

## Step 2: Determine media type and process each draft

For ideas with multiple draft IDs, process only the drafts that need media (check scratchpad text for "CLIP NEEDED" or the Notes for `needs-media`).

---

### If Source Type = YouTube

**Check if a GIF placeholder is already on the draft:**
Call `typefully_get_draft` on the draft. If `media_ids` is non-empty AND the scratchpad says `"CLIP NEEDED"`, the existing media is a placeholder GIF — the clip must replace it.

**Clip selection — quality is the only criterion:**

The clip must contain the most insightful, surprising, or data-rich moment in the video that directly supports the post's core argument. Do NOT default to the opening segment just because it is easy to find. Intros, channel plugs, sponsor reads, and setup context are almost never the best clip.

**Selection process:**
1. Check Notes for explicit clip timestamps (`"Clip: MM:SS → MM:SS"`). Use those if present — they were hand-picked.
2. If no timestamps are given:
   a. Fetch the full YouTube transcript (use `mcp__tavily__tavily_extract` on the YouTube URL, or the clip script's transcript output if available).
   b. Read the draft post text carefully — identify the single strongest claim, stat, or insight the post is built around.
   c. Scan the transcript for the moment where that claim, stat, or insight is actually spoken or demonstrated. That is your target segment.
   d. Target length: **120–240 seconds (2–4 minutes)**. Prefer longer if the segment is genuinely substantive. Never truncate a compelling argument just to keep it short.
   e. Avoid: the first 60 seconds of any video (usually intro/hook), outro segments, and any section that is generic scene-setting without specific insight.
   f. If the transcript is unavailable, use the Notes timestamps as a guide and pick the segment described as the core argument or key data point — not "Opening thesis."

**Clip extraction:**
1. Extract the selected segment:
   ```bash
   bash "/Users/toantruong/Downloads/Apps & Installers/YouTube Clipper FAST/clip.sh" "<youtube_url>" "<start>" "<end>"
   ```
2. Clip saves to: `~/ytclipper-fast/clips/<video_id>_<start>_<end>.mp4`
3. Verify file exists and size > 100KB.
4. Upload to Typefully:
   ```
   typefully_create_media_upload(social_set_id: 151393, file_name: "<filename>")
   ```
5. PUT raw bytes to the returned `upload_url` (NO extra headers).
6. **If a GIF placeholder was present:** call `typefully_edit_draft` to set `media_ids: [<new_clip_id>]`, replacing the old GIF.
   **Otherwise:** attach `media_id` to the draft via `typefully_edit_draft`.
7. Record the chosen segment and the reason it was selected in the Notion Notes field (e.g., `"Clip: 8:08→11:45 — Dario Amodei nightmare scenario quote, core of post argument"`).

**If clip extraction fails (403 or any error) → Clip Failure Fallback:**
1. Search Tavily for a relevant trending tweet: `site:x.com [topic keywords from the idea]`
2. If a tweet is found: call `typefully_edit_draft` to set `quote_post_url` to the tweet URL.
3. Find 2 relevant images using Tavily image search or web search (`[topic] infographic OR chart OR image`). Download or locate URLs for the images.
4. Upload each image to Typefully:
   ```
   typefully_create_media_upload(social_set_id: 151393, file_name: "<image_filename>")
   ```
   PUT raw bytes to each returned `upload_url`.
5. Attach both image `media_id`s to the draft via `typefully_edit_draft`, replacing any existing placeholder GIF.
6. Note the clip failure + fallback used in the Notion Notes field.

---

### If Source Type = Articles (no video)

1. **QRT-first**: Search Tavily for a trending tweet on the same topic: `site:x.com [topic keywords]`
2. If found: call `typefully_edit_draft` to set `quote_post_url`. Save the tweet URL to Notion's `QRT Source URL` field.
3. If not found: add a note to Notion: `"No QRT found — needs manual GIF"` and leave Status as `"Needs Media"` for manual handling.

---

## Step 2.5: QC Gate — verify before promoting

Run this QC check on every draft **after** media attachment (or after confirming media was already attached). Re-fetch the draft with `typefully_get_draft` to get the live state, then work through the checklist. A draft only passes to Step 3 if **all** checks pass.

### QC Checklist

**1. Draft is alive**
- Draft fetch returns a valid response (not 404 / deleted).

**2. Post text is present and clean**
- `posts[0].text` is non-empty and ≥ 100 characters.
- Text does NOT contain any of: `TODO`, `CLIP NEEDED`, `[INSERT`, `PLACEHOLDER`, `[YOUR`, `...` at the very end (trailing ellipsis that signals cut-off content).

**3. Media is attached**
- At least one of the following must be true:
  - `quote_post_url` is set (non-empty string), OR
  - `media_ids` is non-empty.
- Both being empty is an automatic fail.

**4. QRT URL is a specific tweet (not a profile)**
- If `quote_post_url` is set, the URL must contain `/status/` (e.g. `x.com/user/status/123...`).
- A bare profile URL like `x.com/username` is NOT a valid QRT — flag as fail.

**4b. QRT URL resolves to a live, accessible tweet (broken QRT detection)**

This check catches the most common failure mode: the correct creator's handle is in the URL, but the specific tweet ID is wrong — so no Quote Retweet appears in Typefully.

Steps:
1. Extract the creator handle and tweet ID from `quote_post_url` (pattern: `x.com/<handle>/status/<tweet_id>`).
2. Navigate to the URL in Chrome: `mcp__Claude_in_Chrome__navigate(url: <quote_post_url>)`.
3. Take a screenshot and call `get_page_text` to check the result.
4. **Pass condition**: page loads and contains tweet text (visible post content).
5. **Fail conditions**:
   - Page 404s, shows "This post is unavailable", redirects to a profile, or shows an error.
   - Page loads but content is clearly unrelated to the post topic (wrong tweet from the right creator).

**If check 4b fails — Broken QRT Remediation:**
1. Note the creator handle from the broken URL.
2. Navigate to `x.com/<handle>` in Chrome and scroll through their recent tweets (take screenshots, use `get_page_text` to read tweet text).
3. Identify a tweet that is topically aligned with the post — match keywords, themes, or data points from the draft post text.
4. If found: call `typefully_edit_draft` to replace `quote_post_url` with the correct tweet URL. Update Notion's `QRT Source URL` field with the new URL. Add a note to Notion Notes: `"[QRT Fixed] Replaced broken link with <new_url> — original was <old_url>"`.
5. Re-run check 4 and 4b on the new URL before marking as passed.
6. If no suitable tweet is found on the creator's timeline after scrolling through ~20 posts: flag as `[QC FAIL: broken QRT, no replacement found]`, add the note to Notion Notes, and leave Status unchanged for manual handling.

**5. QRT / clip is topically aligned with the post**
- Do a quick gut-check: does the account name or keywords in the `quote_post_url` plausibly match the post's topic?
- Example fail: a dehydration post QRTing a crypto trader's tweet.
- You do NOT need to fetch the tweet — URL-level signal is sufficient for this check.

**6. No orphaned placeholder GIF (YouTube clips only)**
- If Source Type = YouTube and the scratchpad previously said `CLIP NEEDED`, confirm `media_ids` now contains the new clip ID and the placeholder GIF was replaced (not still present alongside it).

**7. Draft status is still "draft" (not published)**
- If `status` ≠ `"draft"`, log a warning and skip — do not overwrite a live post.

### QC outcome

| Result | Action |
|--------|--------|
| All checks pass | Proceed to Step 3 — update Notion to "Ready for Review" |
| Any check fails | Do NOT update status. Add a `[QC FAIL]` note to Notion Notes listing exactly which check(s) failed and why. Leave Status as `"Needs Media"`. Flag in the Step 4 report. |

---

## Step 3: Update Notion

After **successfully attaching media AND passing QC**:
- Set `Status` → `"Ready for Review"`

If **all media attachment attempts failed** OR **QC failed**:
- Add failure/QC note to `Notes` field
- Leave `Status` as `"Needs Media"` (or set it if currently null) for manual handling

---

## Step 4: Report

Output:
- How many ideas had "Needs Media" (by Status) vs found via Notes text
- How many clips extracted and uploaded
- How many GIF placeholders replaced with clips
- How many clip failures → fallback (QRT + images) used
- How many QRTs found for article sources
- **Broken QRT audit**: how many "Ready for Review" posts were scanned, how many had broken QRTs, how many were fixed vs left for manual handling
- **How many passed QC vs failed QC** — list each QC failure with the specific check(s) that failed
- How many failed entirely (media attachment failed, not just QC)
- Any needing manual attention

---

## Rules

- Process maximum 10 ideas per run
- Never modify the post text — only attach media, replace GIFs with clips, or set QRT/image URLs
- Clean up temp files in `~/ytclipper-fast/temp/` after successful uploads
- Notion is the single source of truth — no Typefully tags
- If a draft is 404 (deleted): add a failure note to Notion Notes and skip — do not recreate the draft
