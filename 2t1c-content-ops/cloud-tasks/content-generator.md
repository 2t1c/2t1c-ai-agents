# content-generator (Cloud Version) v3

**Description:** Pick 2-3 highest-urgency New ideas from Notion, write 1 draft per idea (Long-Form or Tuki QRT), create Typefully drafts, set status to Needs Media.

This is an automated run of a scheduled task. The user is not present to answer questions.

---

## STEP 0 — LOAD MCP CONNECTORS (run before anything else, no exceptions)

The Notion and Typefully connectors are deferred and must be loaded via ToolSearch before any other step. Do not ask for confirmation — execute immediately.

1. Call `ToolSearch` with query `"notion"` and max_results 10 — loads the Notion MCP tools
2. Call `ToolSearch` with query `"typefully"` and max_results 10 — loads the Typefully MCP tools
3. Call `notion-fetch` on `collection://330aef7b-3feb-401e-abba-28452441a64d` to confirm Notion is live
4. Call `typefully_get_me` to confirm Typefully is live

Do not pause. Do not ask if connectors are available. Only abort if ToolSearch returns zero results for both queries.

---

## STEP 0.5 — LOAD VOICE & RULES (mandatory)

The writing rules, hook system, CTA template, community registry, and swipe file all live in the public git repo. Fetch them via WebFetch before writing anything.

Run these in parallel:

```
WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/writing-style.md
WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/hook-writing.md
WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/cta-template.md
WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/community-registry.md
WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/swipe-file.md
```

These five files are the **complete voice + structure rulebook**. Apply them exactly when writing the hook, body, and CTA. Do not improvise rules not in these files.

---

## RUNTIME CONSTANTS

- **Notion Idea Pipeline data source:** `collection://330aef7b-3feb-401e-abba-28452441a64d`
- **Typefully social set ID** (GeniusGTX_2): `151393`
- **Use the Notion MCP** for Notion operations:
  - `notion-fetch` — read a single page or data source schema
  - `notion-update-page` — write to a page
  - `mcp__notion__API-query-data-source` — **REAL filter queries** (use this for "give me all pages where Status = X")
  - `notion-search` — semantic search ONLY (use only for fuzzy text discovery, NEVER for Status filtering — semantic search does not honor property filters and returns relevance-ranked results, not filtered results)
- **Use the Typefully MCP** for all Typefully operations

---

## ⚠️ HARD LIMITS (non-negotiable)

- **Maximum 3 Typefully drafts per run.** After creating 3 drafts, STOP.
- **ONE draft per idea.** Never create multiple angles, variants, numbered series, or format variations.
- **Each idea = 1 post.** Either Long-Form Post OR Tuki QRT. Not both. Not 8 angles. ONE.
- **SINGLE-POST FORMAT.** Every draft is one continuous long-form post with the 5-part CTA inline. No follow-up reply tweet.
- If you find yourself about to create a 4th draft, STOP and proceed to Phase 9 (Report).

---

## PHASE 0 — PIPELINE AUDIT

Before anything else, get a full view of the pipeline.

**⚠️ CRITICAL: Use `mcp__notion__API-query-data-source`, NOT `notion-search`.**

`notion-search` is **semantic search** — it ranks pages by text relevance and ignores structured property filters. Querying it with "Status = New" returns relevance-similar pages, not pages where the Status property actually equals "New". This is the most common failure mode of this task.

The correct tool is `mcp__notion__API-query-data-source` — it executes real database filter queries against the Notion API.

### Step 1 — Fetch the schema

Use `notion-fetch` on `collection://330aef7b-3feb-401e-abba-28452441a64d` to confirm the exact name of the Status property and its select option values.

### Step 2 — Query each status bucket via API-query-data-source (run in parallel)

Data source ID: `330aef7b-3feb-401e-abba-28452441a64d` (strip the `collection://` prefix).

For EACH of the 8 status values, call `mcp__notion__API-query-data-source` with this exact filter shape:

```json
{
  "data_source_id": "330aef7b-3feb-401e-abba-28452441a64d",
  "filter": {
    "property": "Status",
    "select": {
      "equals": "New"
    }
  },
  "page_size": 100
}
```

Run all 8 queries in parallel, one per status value:
- "New", "Writing", "Needs Media", "Ready for Review", "Approved", "Scheduled", "Published", "Killed"

If the Status property type is not `select` (could be `status` in Notion's newer schema), use `"status": { "equals": "New" }` instead. The schema fetched in Step 1 will tell you which.

Each query returns ONLY pages where the Status property genuinely equals the queried value. No semantic noise. No guessing.

### Step 2 fallback (only if API-query-data-source is unavailable)

If the `mcp__notion__API-query-data-source` tool failed to load or is otherwise unavailable:
1. Call `mcp__notion__API-post-search` with `query: ""` (empty) and `filter: { "property": "object", "value": "page" }` to get all pages, then client-side filter by `properties.Status.select.name`. Slow but correct.
2. **Do NOT fall back to `notion-search` with property filters** — it will silently return wrong results and the task will burn its 3-draft budget on stale or duplicate ideas.

### Output — Pipeline snapshot

```
Pipeline snapshot:
- New: [count]
- Writing: [count]
- Needs Media: [count]
- Ready for Review: [count]
- Approved: [count]
- Scheduled: [count]
- Published: [count]
- Killed: [count]
Total: [count]
```

This snapshot goes in the final report.

---

## PHASE 1 — PICK IDEAS

Use the results from the Status = "New" query already fetched in Phase 0. Do NOT run a new search.

If "New" returned 0 results, conclude the pipeline is empty and stop.

**Priority order:**

- 🔴 Breaking (highest — process first, time-sensitive)
- 🟡 Trending
- 🟢 Evergreen
- ⚪ Backlog (lowest)

Pick **2-3 ideas. NEVER more than 3.** Set each to Status → "Writing" immediately using `notion-update-page`.

### Recover stalled ideas

Use the results from the Status = "Writing" query already fetched in Phase 0. For each, check if it has a Typefully Draft ID. If empty, treat it as a failed prior run — include it in this run's batch.

Recovered ideas do NOT count against the 2-3 pick limit, BUT the total draft count (picked + recovered) must still not exceed 3. If recovering would push past 3, pick fewer new ideas.

If fewer than 5 "New" ideas remain after picking, flag this in the report as "Refill needed."

---

## PHASE 2 — RESEARCH

Run for each picked idea.

**Before writing, gather:**

- At least **3 specific data points** (numbers, dates, dollar amounts, percentages)
- **1-2 direct quotes** from the source in quotation marks, attributed by name (e.g., *Ray Dalio told Lex Fridman: "..."*)
- **1 unexpected connection** one layer below the surface — the detail nobody else is covering

### How to research

- Check the Source URL first for primary facts — use `WebFetch` on the URL
- Search for additional context, counter-arguments, and specific numbers using `WebSearch`
- If the source is a video/podcast: find the transcript and pull the most powerful line verbatim
- If the source is a tweet: read the full thread and any linked articles
- If the source is an article: find the original data or study being cited

### YouTube source strategy

When Source Type = YouTube, do not rely solely on the video page. Run a `WebSearch` on the video topic to surface:

- Specific data points, percentages, dollar amounts cited in the video
- Named studies or papers referenced by the expert
- The single most powerful direct quote from the expert — pull verbatim from transcript or web coverage

Use the channel name or expert name (not the video title) in the attribution line.

After gathering facts, search Twitter for a trending tweet on the same topic (see Phase 3). If found, write as Tuki QRT. If not, write as standalone Long-Form Post.

### Hard rule

**Never write with vague facts.** If you can't find at least 3 specific data points, skip this idea, set it back to "New" using `notion-update-page`, and pick the next one.

---

## PHASE 3 — QRT-FIRST MEDIA STRATEGY

Run for each picked idea.

Check the idea's `QRT Source URL` field first — if populated, that's the QRT target.

If `QRT Source URL` is empty:

- **Source Type = Twitter:** The Source URL IS the QRT target. Save it to QRT Source URL.
- **Source Type = YouTube or Article:** Search Twitter for a trending tweet on the same topic. Use `WebSearch`: `site:x.com [topic keywords]`. Look for tweets from the last 24-48 hours with high engagement.
  - If found: save to QRT Source URL.
  - If not: post will be standalone.

### QRT Tracing Rule

If the source tweet is itself a QRT, trace back to the ORIGINAL tweet being quoted. QRT the original author's tweet, not the QRTer's.

### URL Verification (non-negotiable, 2 checks)

Before saving any tweet URL to QRT Source URL:

**Check 1 — Format:** A real tweet URL has a numeric ID that does not end in multiple zeros (e.g., `...000000`). If a URL looks like a placeholder, reject immediately.

**Check 2 — Active existence:** Run a `WebSearch` for the exact tweet URL string (e.g., `"x.com/handle/status/1234567890"`). Confirm the tweet exists and content matches the idea. Handle being correct is NOT sufficient — the numeric tweet ID must be independently confirmed via search results.

If either check fails: do NOT save the URL. Leave QRT Source URL empty, mark the post standalone. Note in report: *"QRT URL unverified — posted standalone."*

### Format decision (ONE format per idea)

- QRT found → write **Tuki QRT** style (see writing-style.md)
- No QRT (standalone) → write **Long-Form Post** style (see writing-style.md)

---

## PHASE 4 — WRITE THE HOOK

Apply [hook-writing.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/hook-writing.md) (already fetched in Step 0.5).

**Required output:** a hook unit (250-300 chars for long-form, under 280 for QRT) that passes the SETUP → STAKES → PIVOT → PROMISE spine. Line 1 must be under 20 words.

**Key rules from hook-writing.md:**

- Run angle filters (Identity Attack / Time Collapse / Direct Address) — must pass at least one
- Run Visualization Test — REQUIRED before writing
- Hit at least one primal trigger (betrayal / survival / love / vulnerability / sacrifice / injustice at scale)
- Use opener types as compositional vocabulary (often combine 2-4 in one unit)
- Numbers exact and comparative
- Speed reveals use "just"
- Use [swipe-file.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/swipe-file.md) for inspiration on wording, NOT verbatim copying

**Format-adapted closer:**
- Tuki QRT → explicit closer ("Here's how:", "A thread")
- Long-form → implicit closer (last line opens a mystery the body resolves)

---

## PHASE 5 — WRITE THE BODY

Apply [writing-style.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/writing-style.md) (already fetched in Step 0.5).

**Body structure:**

```
Hook (already written in Phase 4)
Wall (line 2: why this couldn't have happened before)
Build (the story — prose, optionally → facts)
Suppression / Incentive Layer (1 sentence: structural beneficiary)
I-Factor (OPTIONAL, 1-2 sentences)
Contrast Close → Aphoristic Punch
```

**Key rules from writing-style.md:**

- ONE big idea per post — no listicles, no tours
- Body length: 1100-1300 chars
- Sentence cap: 18 words hard, natural pace within
- Sentence variety: 4+ distinct shapes per post
- Reading level: 6th grade (Flesch-Kincaid 6.0-7.5)
- Max 2 aphorisms per post
- 1-2 attributed direct quotes (1 from primary source minimum)
- No em dashes
- Filler test: cut if no tonal loss
- Banned AI words list (see writing-style.md)

---

## PHASE 6 — CTA CLOSER

Apply [cta-template.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/cta-template.md) (already fetched in Step 0.5).

The 5-part CTA goes inline at the end of the same long-form post (no reply tweet):

1. **Engagement Question** — write fresh, low-friction, post-specific
2. **Bridge with reciprocity gift** — extract a transferable rule, hand it as a usable lens
3. **Product CTA** — exact wording, direct gumroad link
4. **Brand CTA** — exact wording
5. **Attribution** — `— [Source], [Platform] | Data: [institutions]`

Total post (body + CTA inline) target: **1300-1450 chars.**

---

## PHASE 6.5 — COMMUNITY ROUTING

Apply [community-registry.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/community-registry.md) (already fetched in Step 0.5).

Run AFTER body + CTA are written, BEFORE creating the Typefully draft.

- Pick at most ONE community. Default is no community (timeline only).
- Only route when the topic clearly matches. Never force a fit.
- Apply only to the main post.

Record decision in report: `Community: [slug] (id: [community_id])` OR `Community: none (reason: [no match / ineligible])`.

---

## PHASE 7 — CREATE TYPEFULLY DRAFTS

Use the Typefully MCP. Social set ID: **151393**.

⚠️ **CHECKPOINT:** Count drafts you're about to create. If > 3, STOP and reduce to 3. Drop the lowest-priority ideas.

Create ONE draft per picked idea. Every draft is a SINGLE post (no thread).

For each draft:

- **Post text:** First words of output ARE first words of the post. No preamble.
- **Draft title:** Use the idea's Notion title (the "Idea" field) verbatim. REQUIRED.
- **Quote post URL:** The QRT Source URL (if found).
- **Share:** true
- **No leading whitespace** (CRITICAL): The text field must start with the first visible character — never a newline or space.
- **Scratchpad** (REQUIRED): Set `scratchpad_text` to exactly two lines:
  ```
  Notion: [full Notion page URL]
  Source: [Source URL from the idea]
  ```

⚠️ **SINGLE-POST FORMAT:** Do NOT create a second follow-up reply post. The Gumroad link is embedded in the main post CTA. Each draft is one post only.

⚠️ **SELF-CHECK:** Count drafts created. If > 3, you violated the hard limit. Report in Phase 9.

---

## PHASE 8 — UPDATE NOTION

For each processed idea, use `notion-update-page` to:

- Save Typefully Draft ID
- Save Typefully Shared URL
- If QRT found via search, save to QRT Source URL
- Set Status → **"Needs Media"**
- Update Notes — append: `Content generated [date]. Format: [Tuki QRT / Long-Form Post]. [QRT found — URL / standalone]. Tagged needs-media.`

**NOTE:** Always set "Needs Media" — never "Ready for Review". The media-attacher task attaches clips/GIFs and advances to "Ready for Review". Even standalone posts may need a clip or image.

---

## PHASE 9 — REPORT

```
═══ PIPELINE SNAPSHOT ═══
New: [count]
Writing: [count]
Needs Media: [count]
Ready for Review: [count]
Approved/Scheduled/Published: [count]
Killed: [count]
Total: [count]

═══ RECOVERED FROM STALLED "WRITING" ═══
[title] — originally picked [date] — now processed
(or: None this run)

═══ DRAFTS PRODUCED THIS RUN ═══

Draft 1:
  Idea: [title]
  Urgency: [level]
  QRT: [found — URL / not found]
  Format: [Tuki QRT / Long-Form Post]
  Community: [slug or none]
  Draft: [Typefully share URL]

Draft 2:
  ...

Draft 3 (if applicable):
  ...

═══ PIPELINE HEALTH ═══
"New" ideas remaining: [count]
Refill needed: [yes/no]
Draft count this run: [number] (MUST be ≤ 3)
```

---

## RULES SUMMARY

- ⛔ **HARD CEILING:** Body 1100-1300 chars. Total post (with inline CTA) 1300-1450 chars. Over 1500 = unconditionally trim.
- ⛔ **MAXIMUM 3 DRAFTS PER RUN.** Hard ceiling.
- ⛔ **ONE DRAFT PER IDEA.** Never create multiple angles, variants, or format variations.
- ⛔ **ONE FORMAT PER IDEA.** Either Tuki QRT or Long-Form Post.
- ⛔ **SINGLE-POST FORMAT.** No follow-up thread reply.
- First words of output ARE the post. No meta-text.
- Must gather 3+ data points and 1-2 attributed quotes before writing.
- If research fails, skip idea, set back to "New", pick next.
- Never publish or schedule. Draft only.
- Notion is single source of truth for ideas.
- **Voice/structure rules are in `docs/writing-style.md`, `docs/hook-writing.md`, `docs/cta-template.md`, `docs/community-registry.md`. Re-read them on every run via WebFetch in Step 0.5.**

### Anti-repetition

- Never same format twice for the same idea
- Topic rotation: no 3+ consecutive same-topic posts
- Check last 5 drafts created — avoid repeating the same angle, source, or pivot pattern

---

*Version 3.0 — April 2026*
*Source of truth: this file in git. Cloud routine prompt is a thin wrapper that fetches this file via raw.githubusercontent.com.*
