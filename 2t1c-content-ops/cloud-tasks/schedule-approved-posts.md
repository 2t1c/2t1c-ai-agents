# schedule-approved-posts (Cloud Version) v3

**Description:** Schedule approved posts to Typefully queue, sync published status, clean up killed drafts.

This is an automated run of a scheduled task. The user is not present to answer questions.

---

## RUNTIME CONSTANTS

- **Notion Idea Pipeline data source ID:** `330aef7b-3feb-401e-abba-28452441a64d`
- **Typefully social set ID** (GeniusGTX_2): `151393`
- **Posting schedule:** 4 slots/day in US Eastern Time — 8:30 AM, 12:00 PM, 4:30 PM, 8:00 PM EDT (UTC-4)

### MCP tools to use

- **Notion:**
  - `notion-fetch` — read a single page or data source schema
  - `notion-update-page` — write to a page
  - `notion-search` — enumerate pages in a data source (semantic; **does NOT honor property filters**)
  - **There is no property-filter query tool.** The cloud-routine Notion MCP does not include `API-query-data-source`. Use the enumerate-then-fetch pattern (see Step 1 below).
- **Typefully:**
  - `typefully_list_drafts`, `typefully_get_draft`, `typefully_edit_draft`, `typefully_delete_draft`
  - `typefully_get_queue`, `typefully_get_social_set_details`
- **WebFetch** for QRT URL liveness check

---

## STEP 0 — LOAD MCP CONNECTORS (run before anything else, no exceptions)

The Notion and Typefully connectors are deferred and must be loaded via ToolSearch before any other step. Do not ask for confirmation — execute immediately. Do not pause. Do not report missing tools — just load them.

### Step 0.1 — Bulk load in parallel

```
ToolSearch({ query: "notion", max_results: 20 })
ToolSearch({ query: "typefully", max_results: 20 })
```

### Step 0.2 — Verify both connectors are live (in parallel)

```
notion-fetch on collection://330aef7b-3feb-401e-abba-28452441a64d
typefully_get_me
```

### Step 0.3 — Retry once if verification fails

If either verification call fails with `"tool not found"` or `InputValidationError`, retry the relevant ToolSearch ONCE with a precise selector:

```
ToolSearch({ query: "select:notion-fetch,notion-search,notion-update-page", max_results: 5 })
ToolSearch({ query: "select:typefully_get_me,typefully_get_queue,typefully_get_draft,typefully_edit_draft,typefully_delete_draft,typefully_get_social_set_details,typefully_get_queue_schedule", max_results: 10 })
```

Then re-verify. If still failing after retry, abort the run and report which connector failed.

Only after both connectors are verified live, proceed to Part 1.

---

## PART 1 — SCHEDULE APPROVED POSTS

### Step 1: Find Approved posts (enumerate-then-fetch pattern)

The cloud-routine Notion MCP has no property-filter query tool. To find pages with Status="Approved":

**1a.** Call `notion-search` with `query: ""`, `data_source_url: collection://330aef7b-3feb-401e-abba-28452441a64d`, `page_size: 25`. Paginate via `start_cursor` until exhausted. Collect all page IDs.

**1b.** In parallel batches of 10, call `notion-fetch` on each page ID. Read the Status property.

**1c.** Filter client-side to keep only pages where `Status == "Approved"`. Sort by Created time (newest first).

For each kept page, collect: Idea title, Created time, Typefully Draft ID, Urgency, Topic Tags, Notes.

**Performance note:** This costs ~5-12 search calls + ~100-300 fetches. Roughly 30-90 seconds for the whole pipeline scan. The same enumerate-then-fetch is reused for Steps 5 and 6 below — **fetch all pages ONCE, then filter the same parsed list for "Scheduled" and "Killed" instead of re-enumerating.**

### Step 2: Check Typefully queue for open slots

Look at the next 2 days of slots (8 slots/day max across both days). Call `typefully_get_queue` and `typefully_get_social_set_details` for social set 151393 to identify which slots are taken.

### Step 2.5: Sort approved posts into priority lanes BEFORE running QC

Process in this order:

**LANE 1 — EXPRESS** (process first, schedule into earliest available slot today):
- 🔴 Breaking, created < 24h ago → `publish_at: "now"` immediately (don't wait for a slot)
- 🟡 Trending, created < 48h ago → next available slot TODAY, even if it means bumping an evergreen

**LANE 2 — STANDARD:**
- 🟡 Trending, created 48h–72h ago → schedule normally into next available slot
- 🟢 Evergreen → next available slot in order

**LANE 3 — DEPRIORITIZED** (schedule last, after Lanes 1 and 2 are placed):
- 🟡 Trending, older than 72h → treat as evergreen, no urgency
- 🔴 Breaking, older than 24h → kill immediately (handled in Step 4)

Within each lane, sort by Created time descending (newest first).

### Step 3: Mini QC gate — for each approved post, fetch the Typefully draft and run these checks BEFORE scheduling

A post must pass ALL checks to be scheduled. **These checks reflect the v3 single-post format with inline 5-part CTA (no follow-up reply, no comment keyword).**

**QC Check 1 — Single-post format:**
- The draft's `posts` array must have **exactly 1 post**.
- 2+ posts = FAIL (this is the legacy thread format; the post needs to be reformatted).

**QC Check 2 — Gumroad link inline in post 1:**
- Post 1 text must contain `besuperhuman.gumroad.com/l/mentalmodels`.
- Missing = FAIL.

**QC Check 3 — Brand CTA present:**
- Post 1 text must contain the verbatim string: `@GeniusGTX is a gallery for the greatest minds in economics, psychology, and history`.
- Missing = FAIL.

**QC Check 4 — Attribution line present:**
- Post 1 text must contain a line beginning with `— ` followed by a source name (e.g. `— Sherwin B. Nuland`).
- Missing = FAIL.

**QC Check 5 — Post length sanity:**
- 1100–1800 characters total = PASS.
- Under 1100 = FAIL (too thin, likely incomplete).
- Over 1800 = WARN (flag in report but still schedule).

**QC Check 6 — No placeholder text:**
- Post text must NOT contain: `TODO`, `CLIP NEEDED`, `[INSERT`, `PLACEHOLDER`, `[YOUR`, `Comment MODELS`, `comment MODELS`, or trailing `...` followed by EOL.
- Any match = FAIL. (`Comment MODELS` is the deprecated v2 CTA and indicates the draft used the old template.)

**QC Check 7 — Media attached:**
- At least one of: `quote_post_url` is set, OR `media_ids` is non-empty.
- Both empty = FAIL. Do not schedule a post with no visual.

**QC Check 8 — QRT still live (only if `quote_post_url` is set):**
- Use `WebFetch` to fetch the tweet URL.
- If 404, error page, or no tweet content visible = FAIL.
- If the tweet loads with visible content = PASS.
- Skip this check if no `quote_post_url`.

**QC Outcome:**
- ALL checks pass (warnings OK) → proceed to scheduling.
- ANY check FAILs → do NOT schedule. Leave Status as "Approved". Use `notion-update-page` to append to Notes: `[Scheduler QC FAIL {date}]: {which checks failed and why}`. Report the failure.

### Step 4: Schedule posts in priority lane order (Lane 1 first, then Lane 2, then Lane 3). Max 8 per run total.

For **LANE 1 — EXPRESS:**
- 🔴 Breaking < 24h → `publish_at: "now"` immediately. Update Notion Status → "Published".
- 🔴 Breaking > 24h → KILL. Update Notion Status → "Killed", call `typefully_delete_draft`. Report as "stale breaking — killed."
- 🟡 Trending < 48h → find next open slot TODAY. If all today's slots are taken, use the first slot tomorrow. Never push fresh trending past 48h total age.

For **LANE 2 — STANDARD:**
- Fill remaining slots in chronological order. No back-to-back same topic tag.
- 🟢 Evergreen → no staleness concern, schedule normally.

For **LANE 3 — DEPRIORITIZED:**
- Schedule only if slots remain after Lanes 1 and 2.

For all scheduled posts:
- Schedule on Typefully using `publish_at` (ISO 8601 datetime with timezone)
- Use `notion-update-page` to set Status → "Scheduled" and Publish Date → the scheduled datetime

---

## PART 2 — SYNC PUBLISHED STATUS

### Step 5: Find Scheduled posts

Filter the parsed pages from Step 1 (already enumerated and fetched) for `Status == "Scheduled"`. Do not re-enumerate.

For each result, call `typefully_get_draft` using the Typefully Draft ID.

- If Typefully `status == "published"` → update Notion Status to "Published".
- If still `scheduled` → no change.

---

## PART 3 — CLEAN UP KILLED DRAFTS

### Step 6: Find Killed posts with remaining Typefully drafts

Filter the parsed pages from Step 1 for `Status == "Killed"` AND `Typefully Draft ID is not empty`.

For each result:
- Call `typefully_delete_draft` to remove from Typefully
- Use `notion-update-page` to clear Typefully Draft ID and Typefully Shared URL

---

## REPORT

```
═══ SCHEDULED THIS RUN ═══
Lane 1 (Express):
  - [title] — 🔴/🟡 — published immediately / scheduled at [time]
Lane 2 (Standard):
  - [title] — 🟡/🟢 — scheduled at [time]
Lane 3 (Deprioritized):
  - [title] — 🟢 — scheduled at [time] (or: no slots remaining)

═══ STALE KILLED ═══
- [title] — 🔴 Breaking older than 24h — killed

═══ QC FAILURES (held in "Approved") ═══
- [title] — failed check #N: [reason]

═══ SYNC RESULTS ═══
Scheduled → Published transitions: [count]

═══ KILLED DRAFTS CLEANED UP ═══
[count] drafts deleted, Notion fields cleared

═══ QUEUE STATE ═══
Open slots in next 2 days: [count]
Today's slots filled: [n/4]
Tomorrow's slots filled: [n/4]
```

---

## RULES

- ⛔ **Maximum 8 posts scheduled per run** (2 days worth)
- ⛔ **Never schedule more than 4 posts in a single day**
- 🔴 Breaking < 24 hours old → `publish_at: "now"` immediately
- 🔴 Breaking > 24 hours old → kill it. Stale news damages credibility.
- 🟡 Trending > 72 hours old → lower priority, schedule after fresher content
- 🟢 Evergreen → no staleness, schedule normally
- Never modify post content (this task only schedules existing drafts)
- If no approved posts pass QC, just run Parts 2 and 3 then stop
- Notion is the single source of truth — no Typefully tags

---

*Version 3.0 — April 2026*
*Source of truth: this file in git. Cloud routine prompt is a thin wrapper that fetches this file via raw.githubusercontent.com.*
