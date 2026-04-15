# schedule-approved-posts (Cloud Version)
# Cron: 0 0,3,6,9,12,15,18,21 * * * (every 3 hours)
# Description: Schedule approved posts, sync published status, clean up killed drafts.

Typefully social set ID for GeniusGTX (@GeniusGTX_2): 151393
Notion Idea Pipeline data source: collection://330aef7b-3feb-401e-abba-28452441a64d

Use the Notion MCP connector for all Notion operations (notion-search, notion-fetch, notion-update-page).
Use the Typefully MCP for all Typefully operations.

STEP -1 — TAB STATUS BEGIN (run first, before anything else)
Run Bash immediately as your very first action:
  `bash ~/.claude/lib/tab-status.sh begin schedule-approved-posts`
This writes a busy flag to `~/.claude/state/tabs/schedule-approved-posts.json` so the daily tab-cleanup sweep knows this task is live and will not close tabs it might need. On successful completion call `done` (final step). If you abort early (e.g. preload failure), call `fail` instead.

STEP 0 — TOOL PRELOAD (MANDATORY, RUN FIRST)
This task is non-interactive. MCP tools are lazy-loaded via ToolSearch, and a first-try miss has no human to retry it. Before doing ANY other work, preload every tool this task needs in a single batch so later calls cannot fail with "tool not found".

Run these ToolSearch calls in parallel as your very first action:
  1. ToolSearch({ query: "notion", max_results: 20 })
  2. ToolSearch({ query: "typefully", max_results: 20 })
  3. ToolSearch({ query: "web_fetch web search", max_results: 5 })

Verify after preload that the following tool names appear in the loaded set before proceeding. If any are missing, run a targeted ToolSearch for that specific name (e.g. `select:<exact_tool_name>`) and retry once:
  - notion-search, notion-fetch, notion-update-page
  - typefully_list_drafts, typefully_get_draft, typefully_edit_draft, typefully_delete_draft, typefully_get_queue, typefully_get_social_set_details
  - WebFetch (or equivalent web_fetch)

If after two ToolSearch attempts a required tool is still unavailable, abort the run and report which tool failed to load. Do NOT attempt to call unloaded tools — that produces the "deferred tool" error.

PART 1 — SCHEDULE APPROVED POSTS

Step 1: Find Approved posts.
Use the Notion MCP connector to search the Idea Pipeline for all ideas with Status = "Approved".
For each, fetch the full page and collect: Idea title, Created time, Typefully Draft ID, Urgency, Topic Tags, Notes.

Step 2: Check Typefully for already-scheduled drafts to find open slots. The posting schedule is 4 slots per day (US Eastern Time):
- 8:30 AM EDT
- 12:00 PM EDT
- 4:30 PM EDT
- 8:00 PM EDT

Look at the next 2 days of slots. We are currently in EDT (UTC-4).

Step 2.5: Sort approved posts into priority lanes BEFORE running QC. Process in this order:

LANE 1 — EXPRESS (process first, schedule into earliest available slot today):
- 🔴 Breaking, created < 24h ago → publish_at: "now" immediately (don't wait for a slot)
- 🟡 Trending, created < 48h ago → next available slot TODAY, even if it means bumping an evergreen

LANE 2 — STANDARD:
- 🟡 Trending, created 48h–72h ago → schedule normally into next available slot
- 🟢 Evergreen → next available slot in order

LANE 3 — DEPRIORITIZED (schedule last, after all Lane 1 and 2 are placed):
- 🟡 Trending, older than 72h → treat as evergreen, no urgency
- 🔴 Breaking, older than 24h → kill immediately (handled in Step 4)

Within each lane, sort by Created time descending (newest first).

Step 3: Mini QC gate — for each approved post, fetch the Typefully draft and run these checks BEFORE scheduling. A post must pass ALL checks to be scheduled.

QC Check 1 — Media is attached:
  - At least one of: `quote_post_url` is set, OR `media_ids` is non-empty.
  - Both empty = FAIL. Do not schedule a post with no visual.

QC Check 2 — Thread structure (follow-up reply post):
  - The draft must have 2+ posts in the `posts` array.
  - Post 2 must contain the Gumroad link (`besuperhuman.gumroad.com/l/mentalmodels`).
  - Missing post 2 or missing Gumroad link = FAIL.

QC Check 3 — CTA keyword present:
  - The main post text (post 1) must contain the word "MODELS" (uppercase, the comment keyword).
  - Missing = FAIL.

QC Check 4 — Post length sanity:
  - Under 800 characters = FAIL (too thin, likely incomplete).
  - 800–3000 characters = PASS.
  - Over 3000 characters = WARN (flag in report but still schedule).
  - Measure post 1 text only.

QC Check 5 — No placeholder text:
  - Post text must NOT contain: `TODO`, `CLIP NEEDED`, `[INSERT`, `PLACEHOLDER`, `[YOUR`, or trailing `...`.
  - Any match = FAIL.

QC Check 6 — QRT still live (only if quote_post_url is set):
  - Use web_fetch to fetch the tweet URL.
  - If the response 404s, returns an error page, or shows no tweet content = FAIL.
  - If the tweet loads with visible content = PASS.
  - Skip this check if no quote_post_url is set.

QC Outcome:
  - ALL checks pass (warnings OK) → proceed to scheduling.
  - ANY check FAILs → do NOT schedule. Leave Status as "Approved". Append to Notion Notes: `[Scheduler QC FAIL {date}]: {which checks failed and why}`. Report the failure.

Step 4: Schedule posts in priority lane order (Lane 1 first, then Lane 2, then Lane 3). Max 8 per run total.

For LANE 1 — EXPRESS:
- 🔴 Breaking < 24h → publish_at: "now" immediately. Update Notion Status → "Published".
- 🔴 Breaking > 24h → KILL. Update Notion Status → "Killed", delete Typefully draft. Report as "stale breaking — killed."
- 🟡 Trending < 48h → find next open slot TODAY. If all today's slots are taken, use the first slot tomorrow. Never push fresh trending past 48h total age.

For LANE 2 — STANDARD:
- Fill remaining slots in chronological order. No back-to-back same topic tag.
- 🟢 Evergreen → no staleness concern, schedule normally.

For LANE 3 — DEPRIORITIZED:
- Schedule only if slots remain after Lane 1 and 2.

For all scheduled posts:
- Schedule on Typefully using publish_at (ISO 8601 datetime with timezone)
- Update Notion: Status → "Scheduled", Publish Date → the scheduled datetime

PART 2 — SYNC PUBLISHED STATUS

Step 5: Find Scheduled posts.
Use the Notion MCP connector to search for all ideas with Status = "Scheduled".
For each, fetch the Typefully draft using the Typefully Draft ID.

- If Typefully status = "published" → update Notion Status to "Published"
- If still "scheduled" → no change

PART 3 — CLEAN UP KILLED DRAFTS

Step 6: Find Killed posts with remaining Typefully drafts.
Use the Notion MCP connector to search for "Killed" status ideas in the Idea Pipeline.
For each that still has a Typefully Draft ID set:

- Delete the Typefully draft
- Clear the Typefully Draft ID and Typefully Shared URL fields on the Notion idea

REPORT:
- Breaking posts published immediately (if any)
- Stale breaking posts killed (if any)
- Approved posts scheduled (with times)
- Scheduled posts now published
- Killed drafts cleaned up
- Open slots remaining in next 2 days

RULES:
- Maximum 8 posts scheduled per run (2 days worth)
- Never schedule more than 4 posts in a single day
- 🔴 Breaking < 24 hours old → publish_at: "now" immediately
- 🔴 Breaking > 24 hours old → kill it. Stale news damages credibility.
- 🟡 Trending > 72 hours old → lower priority, schedule after fresher content
- 🟢 Evergreen → no staleness, schedule normally
- Never modify post content
- If no approved posts, just run Parts 2 and 3 then stop
- Notion is the single source of truth — no Typefully tags

FINAL STEP — TAB STATUS END (run last, after the report)
As your final action, run Bash:
  `bash ~/.claude/lib/tab-status.sh done schedule-approved-posts`
If you aborted earlier (preload failure or any unrecovered error), run `fail` instead:
  `bash ~/.claude/lib/tab-status.sh fail schedule-approved-posts`
Either call clears the busy flag so the next daily cleanup sweep can reclaim any tabs associated with this run.
