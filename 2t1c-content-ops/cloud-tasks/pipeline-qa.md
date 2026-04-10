# pipeline-qa (Cloud Version)
# Cron: 0 6 * * * (6am daily)
# Description: Pipeline QA — Ready for Review audit, schedule sync, stale detection, duplicate check

Typefully social set ID for GeniusGTX: 151393
Notion Idea Pipeline data source: collection://330aef7b-3feb-401e-abba-28452441a64d

Use the Notion MCP connector for all Notion operations (notion-search, notion-fetch, notion-update-page).
Use the Typefully MCP for all Typefully operations.

STEP 1: Fetch All "Ready for Review" Ideas
Query the Idea Pipeline (collection://330aef7b-3feb-401e-abba-28452441a64d) for all ideas with Status = "Ready for Review".

For each idea, fetch the full page and collect:

Idea title
Typefully Draft ID
Typefully Shared URL
QRT Source URL
Source URL
Source Type
Notes (check for any media references)

STEP 2: Check Each Idea for Media
For each "Ready for Review" idea, run these checks:

Check A — Does a Typefully draft exist?

If Typefully Draft ID is empty → FAIL (no draft was ever created)
Check B — If Typefully Draft ID exists, fetch the draft from Typefully and verify:

Does the draft have a quote post URL attached? (QRT)
Does the draft have any media attached? (images, GIFs, videos)
Check C — Cross-reference with Notion fields:

If QRT Source URL is populated in Notion but the Typefully draft has no quote post → MISMATCH
If QRT Source URL is empty AND no media attached to the draft → NO MEDIA AT ALL

STEP 3: Classify Each Idea
Based on the checks, classify each idea:

PASS — Draft exists AND has at least one of: quote post (QRT) attached, image, GIF, or video
FAIL — No Draft — Typefully Draft ID is empty. Move back to "Writing" (it never got a draft created)
FAIL — No Media — Draft exists but has no QRT and no media attached. Move back to "Needs Media"
MISMATCH — QRT Source URL exists in Notion but isn't attached in the Typefully draft. Flag for manual review but still move to "Needs Media"

STEP 4: Move Failing Ideas
For each idea that FAILed:

No Draft → Set Status to "Writing"
No Media / Mismatch → Set Status to "Needs Media"
Append to Notes: [QA Audit {date}]: Moved back from Ready for Review — {reason}.

STEP 4.5: Auto-Approve Passing Ideas
For each idea that PASSED all checks in Step 3, run this final gate before auto-approving:

Gate 1 — Typefully draft text is not empty and post 1 is at least 800 characters.
Gate 2 — Post 2 (follow-up reply) exists and contains "besuperhuman.gumroad.com/l/mentalmodels".
Gate 3 — Post 1 contains "MODELS" (the CTA keyword, uppercase).
Gate 4 — No placeholder text in post 1: must NOT contain TODO, CLIP NEEDED, [INSERT, PLACEHOLDER, [YOUR, or trailing ...
Gate 5 — QRT URL format check: if QRT Source URL is set, it must have a numeric tweet ID that does NOT end in multiple zeros. If it fails format check, do not auto-approve — flag as MISMATCH.
Gate 6 — Created within the last 14 days. If older than 14 days and still unscheduled, it is stale — do NOT auto-approve. Set Status back to "Killed" and note: [QA Auto-Kill {date}]: Idea older than 14 days, never approved — killed as stale.

If ALL 6 gates pass → Set Status to "Approved". Append to Notes: [QA Auto-Approved {date}]: Passed all quality gates. Ready to schedule.

If ANY gate fails → Do NOT auto-approve. Leave Status as "Ready for Review". Append to Notes: [QA Auto-Approve BLOCKED {date}]: {which gate failed and why}. These need manual review.

This means posts that fully pass flow automatically into the scheduling queue without any manual step. Posts with issues surface for your attention.

STEP 5: Schedule Sync Check
Query all ideas with Status = "Scheduled". For each:

1. Fetch the Typefully draft using the Typefully Draft ID.
2. Compare the Typefully draft's `scheduled_date` with Notion's `Publish Date` property.
3. Classify:
   - SYNCED — Both dates match (within 5 minutes tolerance)
   - NOT SCHEDULED ON TYPEFULLY — Notion says "Scheduled" but Typefully `scheduled_date` is null. This means the post will NOT go out. Flag as critical.
   - DATE MISMATCH — Both have dates but they differ. Flag with both timestamps.
   - NO NOTION DATE — Typefully has a scheduled_date but Notion's Publish Date is empty. Update Notion's Publish Date to match Typefully.

For critical issues (not scheduled on Typefully), append to Notes: [QA Audit {date}]: Scheduled in Notion but not scheduled on Typefully — needs manual scheduling.

STEP 6: Stale Item Detection
Query all ideas with Status = "Writing" or "Needs Media". For each:

1. Check the Notes field for the most recent dated entry.
2. If the last activity is 3+ days ago (relative to today), flag as STALE.
3. Do NOT move stale items — just report them.

STEP 7: Duplicate Source URL Detection
Across ALL ideas fetched in Steps 1, 5, and 6, check for duplicate Source URLs.

Flag any two or more ideas sharing the same Source URL. Report the idea titles and their statuses.

STEP 8: Status Sync (Notion vs Typefully)
For all ideas already fetched that have a Typefully Draft ID, cross-check:

- If Typefully draft status = "published" but Notion Status is NOT "Published" → Update Notion Status to "Published"
- If Typefully draft status = "scheduled" but Notion Status is NOT "Scheduled" → Flag for review (don't auto-move, just report)

STEP 9: Report

═══ PIPELINE QA AUDIT ═══
Date: {date}

── READY FOR REVIEW AUDIT ──
Total ideas audited: [count]

✅ PASSED media check: [count]

🚀 AUTO-APPROVED: [count]
[idea title] — all 6 gates passed

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
