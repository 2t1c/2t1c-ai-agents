# pipeline-qa (Cloud Version) v3

**Description:** Pipeline QA — Ready for Review audit, schedule sync, stale detection, duplicate check.

This is an automated run of a scheduled task. The user is not present to answer questions.

---

## RUNTIME CONSTANTS

- **Notion Idea Pipeline data source ID:** `330aef7b-3feb-401e-abba-28452441a64d`
- **Typefully social set ID** (GeniusGTX_2): `151393`

### MCP tools to use

- **Notion:**
  - `notion-fetch` — read a single page or data source schema
  - `notion-update-page` — write to a page
  - `mcp__notion__API-query-data-source` — **REAL filter queries** for Status (use this everywhere)
  - **NEVER use `notion-search` for Status filtering** — it is semantic search and ignores property filters
- **Typefully:**
  - `typefully_list_drafts`, `typefully_get_draft`

---

## STEP 1: Fetch all "Ready for Review" ideas

Call `mcp__notion__API-query-data-source`:

```json
{
  "data_source_id": "330aef7b-3feb-401e-abba-28452441a64d",
  "filter": {
    "property": "Status",
    "select": { "equals": "Ready for Review" }
  },
  "page_size": 100
}
```

If the Status property is type `status` instead of `select`, swap the filter to `"status": { "equals": "Ready for Review" }`. Fetch the data source schema first via `notion-fetch` if unsure.

For each result, collect: Idea title, Typefully Draft ID, Typefully Shared URL, QRT Source URL, Source URL, Source Type, Notes, Created time.

---

## STEP 2: Check each idea for media

For each "Ready for Review" idea:

**Check A — Does a Typefully draft exist?**
- If Typefully Draft ID is empty → FAIL (no draft was ever created)

**Check B — If Typefully Draft ID exists, fetch the draft via `typefully_get_draft` and verify:**
- Does the draft have a `quote_post_url` attached? (QRT)
- Does the draft have any `media_ids` attached? (images, GIFs, videos)

**Check C — Cross-reference with Notion fields:**
- If QRT Source URL is populated in Notion but the Typefully draft has no `quote_post_url` → MISMATCH
- If QRT Source URL is empty AND no `media_ids` attached to the draft → NO MEDIA AT ALL

---

## STEP 3: Classify each idea

- **PASS** — Draft exists AND has at least one of: `quote_post_url`, `media_ids` (images/GIFs/videos)
- **FAIL — No Draft** — Typefully Draft ID is empty. Move back to "Writing" (it never got a draft created)
- **FAIL — No Media** — Draft exists but has no QRT and no media. Move back to "Needs Media"
- **MISMATCH** — QRT Source URL exists in Notion but isn't attached in the Typefully draft. Flag for manual review but still move to "Needs Media"

---

## STEP 4: Move failing ideas

For each idea that failed Step 3, use `notion-update-page`:

- **No Draft** → Set Status to "Writing"
- **No Media / Mismatch** → Set Status to "Needs Media"
- Append to Notes: `[QA Audit {date}]: Moved back from Ready for Review — {reason}.`

---

## STEP 4.5: Auto-approve passing ideas (v3 single-post format gates)

For each idea that PASSED all checks in Step 3, run this final gate before auto-approving. **These gates reflect the v3 single-post format with inline 5-part CTA. The old "Comment MODELS" + post-2 reply pattern is deprecated.**

Fetch the Typefully draft via `typefully_get_draft` and check:

**Gate 1 — Single-post format:**
- The draft's `posts` array must have **exactly 1 post**.
- 2+ posts = FAIL (legacy thread format; the post needs to be reformatted by content-generator).

**Gate 2 — Post 1 length sanity:**
- Post 1 text length: **1100–1800 characters**.
- Under 1100 = FAIL (too thin)
- Over 1800 = FAIL (over budget; needs trimming)

**Gate 3 — Gumroad link inline in post 1:**
- Post 1 text must contain `besuperhuman.gumroad.com/l/mentalmodels`.
- Missing = FAIL.

**Gate 4 — Brand CTA verbatim:**
- Post 1 text must contain the exact string: `@GeniusGTX is a gallery for the greatest minds in economics, psychology, and history`.
- Missing = FAIL.

**Gate 5 — Attribution line present:**
- Post 1 text must contain a line beginning with `— ` (em-dash space) followed by a source name. Pattern hint: matches `\n— [A-Z]` (newline, em-dash, space, capitalized name).
- Missing = FAIL.

**Gate 6 — No placeholder or deprecated text:**
- Post 1 must NOT contain any of: `TODO`, `CLIP NEEDED`, `[INSERT`, `PLACEHOLDER`, `[YOUR`, `Comment MODELS`, `comment MODELS`, `That's a wrap`, trailing `...` followed by EOL.
- Any match = FAIL. (The `Comment MODELS` and `That's a wrap` strings are explicit deprecation indicators — they mean the draft was generated against the old v2 template.)

**Gate 7 — QRT URL format (only if QRT Source URL is set in Notion):**
- The numeric tweet ID must NOT end in multiple zeros (`...000000` is a placeholder, not a real ID).
- Failed format = FAIL with reason "QRT URL placeholder format".

**Gate 8 — Idea freshness (created within the last 14 days):**
- If older than 14 days and still unscheduled → it is stale.
- Do NOT auto-approve. Set Status back to "Killed" using `notion-update-page` and append to Notes: `[QA Auto-Kill {date}]: Idea older than 14 days, never approved — killed as stale.`

**If ALL 8 gates pass:**
- Use `notion-update-page` to set Status → "Approved"
- Append to Notes: `[QA Auto-Approved {date}]: Passed all v3 quality gates. Ready to schedule.`

**If ANY gate fails (other than Gate 8 which auto-kills):**
- Do NOT auto-approve. Leave Status as "Ready for Review".
- Append to Notes: `[QA Auto-Approve BLOCKED {date}]: {which gate failed and why}. These need manual review.`

This means posts that fully pass v3 gates flow automatically into the scheduling queue without any manual step. Posts with issues surface for your attention.

---

## STEP 5: Schedule sync check

Query all ideas with Status = "Scheduled" using `mcp__notion__API-query-data-source`:

```json
{
  "data_source_id": "330aef7b-3feb-401e-abba-28452441a64d",
  "filter": {
    "property": "Status",
    "select": { "equals": "Scheduled" }
  },
  "page_size": 100
}
```

For each:
1. Fetch the Typefully draft via `typefully_get_draft` using the Typefully Draft ID
2. Compare Typefully's `scheduled_date` with Notion's `Publish Date` property
3. Classify:
   - **SYNCED** — Both dates match (within 5 minutes tolerance)
   - **NOT SCHEDULED ON TYPEFULLY** — Notion says "Scheduled" but Typefully `scheduled_date` is null. The post will NOT go out. Flag as critical.
   - **DATE MISMATCH** — Both have dates but they differ. Flag with both timestamps.
   - **NO NOTION DATE** — Typefully has a `scheduled_date` but Notion's Publish Date is empty. Update Notion's Publish Date to match Typefully.

For critical issues (not scheduled on Typefully), append to Notes: `[QA Audit {date}]: Scheduled in Notion but not scheduled on Typefully — needs manual scheduling.`

---

## STEP 6: Stale item detection

Query all ideas with Status = "Writing" or "Needs Media". Run two queries in parallel:

```json
{ "data_source_id": "330aef7b-3feb-401e-abba-28452441a64d", "filter": { "property": "Status", "select": { "equals": "Writing" } }, "page_size": 100 }
```

```json
{ "data_source_id": "330aef7b-3feb-401e-abba-28452441a64d", "filter": { "property": "Status", "select": { "equals": "Needs Media" } }, "page_size": 100 }
```

For each:
1. Check the Notes field for the most recent dated entry
2. If the last activity is 3+ days ago (relative to today) → flag as STALE
3. Do NOT move stale items — just report them

---

## STEP 7: Duplicate Source URL detection

Across ALL ideas fetched in Steps 1, 5, and 6, check for duplicate Source URLs.

Flag any two or more ideas sharing the same Source URL. Report the idea titles and their statuses.

---

## STEP 8: Status sync (Notion vs Typefully)

For all ideas already fetched that have a Typefully Draft ID, cross-check:

- If Typefully draft `status == "published"` but Notion Status is NOT "Published" → use `notion-update-page` to set Notion Status to "Published"
- If Typefully draft `status == "scheduled"` but Notion Status is NOT "Scheduled" → flag for review (don't auto-move, just report)

---

## STEP 9: Report

```
═══ PIPELINE QA AUDIT (v3) ═══
Date: {date}

── READY FOR REVIEW AUDIT ──
Total ideas audited: [count]

✅ PASSED media check: [count]

🚀 AUTO-APPROVED: [count]
[idea title] — all 8 v3 gates passed

⛔ AUTO-APPROVE BLOCKED (needs manual review): [count]
[idea title] — gate failed: [which gate and why]

🗑️ AUTO-KILLED (stale 14+ days): [count]
[idea title] — reason: older than 14 days, never approved

❌ MOVED TO "NEEDS MEDIA": [count]
[idea title] — reason: [no media / QRT not attached / mismatch]

❌ MOVED TO "WRITING": [count]
[idea title] — reason: no Typefully draft

── SCHEDULE SYNC ──
Scheduled ideas checked: [count]

✅ SYNCED: [count]
[list of synced idea titles with scheduled time]

🚨 NOT SCHEDULED ON TYPEFULLY: [count]
[idea title] — Notion says Scheduled for {date}, Typefully has no scheduled_date

⚠️ DATE MISMATCH: [count]
[idea title] — Notion: {date} / Typefully: {date}

── STALE ITEMS ──
⏳ STALE (3+ days no activity): [count]
[idea title] — Status: [status] — Last activity: {date} ({N} days ago)

── DUPLICATE SOURCE URLs ──
🔁 DUPLICATES FOUND: [count groups]
[Source URL] →
  - [idea title 1] (Status: ...)
  - [idea title 2] (Status: ...)

── STATUS SYNC ──
🔄 NOTION UPDATED TO "PUBLISHED": [count]
[idea title] — was "[old status]", Typefully confirmed published

⚠️ STATUS MISMATCH (review needed): [count]
[idea title] — Notion: [status] / Typefully: [status]

═══ SUMMARY ═══
"Ready for Review" before audit: [count]
Auto-approved → Approved: [count]
Blocked (manual review needed): [count]
Auto-killed (stale): [count]
Moved back to Needs Media: [count]
Moved back to Writing: [count]
"Ready for Review" after audit: [count]
Schedule issues found: [count]
Stale items flagged: [count]
Duplicates flagged: [count]
Status corrections made: [count]
```

---

## RULES

- Notion is the single source of truth — no Typefully tags. Never create, add, or modify tags on Typefully drafts.
- Never delete Typefully drafts. Only move Notion statuses. (Deletion is `schedule-approved-posts`'s job for killed items.)
- Use `mcp__notion__API-query-data-source` for ALL Status filtering. `notion-search` is semantic only and silently returns wrong results.

---

*Version 3.0 — April 2026*
*Source of truth: this file in git. Cloud routine prompt is a thin wrapper that fetches this file via raw.githubusercontent.com.*
