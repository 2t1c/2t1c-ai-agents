# content-generator (Cloud Version) v3

**Description:** Pick 2-3 highest-urgency New ideas from Notion, write 1 draft per idea (Long-Form or Tuki QRT), create Typefully drafts, set status to Needs Media.

This is an automated run of a scheduled task. The user is not present to answer questions.

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
ToolSearch({ query: "select:typefully_get_me,typefully_create_draft,typefully_list_social_sets,typefully_edit_draft,typefully_get_draft,typefully_create_media_upload", max_results: 10 })
```

Then re-verify. If still failing after retry, abort the run and report which connector failed.

Only after both connectors are verified live, proceed to Step 0.5.

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
  - `notion-fetch` — read a single page (returns full properties) or data source schema
  - `notion-update-page` — write to a page
  - `notion-search` — enumerate pages in a data source (semantic; **does NOT honor property filters**)
- **There is no property-filter query tool.** The cloud-routine Notion MCP does not include `API-query-data-source`. The only way to filter by Status is enumerate-then-verify (see Phase 0 below).
- **Use the Typefully MCP** for all Typefully operations

---

## ⚠️ HARD LIMITS (non-negotiable)

- **Maximum 3 Typefully drafts per run.** After creating 3 drafts, STOP.
- **ONE draft per idea.** Never create multiple angles, variants, numbered series, or format variations.
- **Each idea = 1 post.** Either Long-Form Post OR Tuki QRT. Not both. Not 8 angles. ONE.
- **SINGLE-POST FORMAT.** Every draft is one continuous long-form post with the 5-part CTA inline. No follow-up reply tweet.
- If you find yourself about to create a 4th draft, STOP and proceed to Phase 9 (Report).

---

## PHASE 0 — FIND NEW IDEAS (marker-based fast path)

**The marker convention.** New ideas in the Idea Pipeline have **`🆕 `** prepended to their title (added by the ideation agent at card creation). This makes them findable by `notion-search` query, bypassing the Notion MCP's lack of a property-filter query tool.

State machine (relevant to this task):

| Status | Title prefix | Set by | Removed by |
|---|---|---|---|
| New | `🆕 ` | Ideation agent | content-generator (Phase 1, when picking) |
| Writing | (none) | content-generator | (next transition) |
| Needs Media | `📺 ` | content-generator (Phase 8, when handing off) | media-attacher (when media done) |
| Ready for Review | (none) | media-attacher | — |

### Step 1 — Confirm Notion schema

Call `notion-fetch` on `collection://330aef7b-3feb-401e-abba-28452441a64d`. From the response, note:
- The exact title property name (typically `Idea`)
- The Status property type and its select option values

### Step 2 — Search for the 🆕 marker

Call `notion-search`:

```json
{
  "query": "🆕",
  "data_source_url": "collection://330aef7b-3feb-401e-abba-28452441a64d",
  "page_size": 25
}
```

Title-match results land at the top — these are reliable. Paginate via `start_cursor` only if the first response indicates more results.

### Step 3 — Verify each candidate

For each search result, call `notion-fetch` on the page ID. Confirm BOTH:

1. The title still starts with `🆕 ` (defense against false positives from semantic noise)
2. Status property genuinely equals `"New"` (defense against stale markers left on cards that already moved)

If either check fails, skip the candidate. **If a card has `🆕` in title but Status is not "New" → log it for cleanup but do not pick.**

For each verified "New" candidate, collect: Idea title (with marker), Urgency, Source URL, QRT Source URL, Source Type, Topic Tags, Notes, Created time.

### Step 4 — Snapshot

Just report what you found:

```
═══ NEW IDEAS FOUND VIA 🆕 MARKER ═══
Total: [count]
By urgency:
  🔴 Breaking: [count]
  🟡 Trending: [count]
  🟢 Evergreen: [count]
  ⚪ Backlog: [count]

Cleanup needed (🆕 marker on non-New card): [count]
[list any]
```

Full pipeline-wide status counts are not part of this task. The pipeline-qa task handles full audits.

### Stalled recovery (deferred)

This task does not auto-recover stalled "Writing" cards (cards in Writing status with no Typefully Draft ID — meaning a prior run failed mid-flight). The Notion MCP can't filter by Status efficiently, so a per-run enumeration would dominate runtime.

If you find a stuck card manually, fix it by:
- Resetting Status → "New"
- Re-adding `🆕 ` to the title prefix
- It will be picked up on the next content-generator run.

Pipeline-qa will surface stalled cards in its daily report.

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

Use the verified "New" candidates from Phase 0. Do NOT run a new search.

If 0 New candidates were found, conclude the pipeline is empty and stop.

**Priority order:**

- 🔴 Breaking (highest — process first, time-sensitive)
- 🟡 Trending
- 🟢 Evergreen
- ⚪ Backlog (lowest)

Pick **2-3 ideas. NEVER more than 3.**

### For each picked idea, immediately update Notion (state transition: New → Writing)

Call `notion-update-page` with both changes in one call:

1. **Strip `🆕 ` from the title.** Update the title property (typically `Idea`) to remove the marker prefix. If the title is `🆕 Marie Curie's notebooks behind lead shields`, the new title is `Marie Curie's notebooks behind lead shields`.
2. **Set Status → "Writing"** so the card moves on the kanban.

Do this BEFORE writing content so the card stops appearing in subsequent `🆕` searches (prevents double-pick by parallel runs).

### Refill warning

If fewer than 5 verified "New" candidates remained after Phase 0, flag in the final report as `Refill needed: New idea count is critically low.`

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

## PHASE 4 — WRITE THE HOOK (swipe-file-first, top-of-funnel)

Stop overthinking hooks. The job is simple: **find the single most interesting fact or angle in your research, and write it like a thread hook that would stop a stranger mid-scroll.**

### Step 4.1 — Pick the top-of-funnel angle (before writing anything)

From the facts you gathered in Phase 2, pick the ONE angle that resonates widest — the thing a non-expert scrolling past would stop for. Not the angle you find intellectually interesting. The angle that lands on a cold audience.

Litmus test: *"If my mom (who doesn't follow this topic) saw line 1, would she pause?"* If no, pick a different angle.

Strong top-of-funnel angles are usually one of:
- A specific number that's absurd in context ($155 GDP, 28 days, $4M/month burning)
- An unexpected juxtaposition (poorer than Chad / greatest trader ever / two gaming GPUs beat every elite lab)
- A named authority doing something no one expects (Marie Curie's notebooks still lethal, Sam Altman on anxiety)
- A time collapse (same fact, two eras, the gap IS the hook)
- A hidden consequence (nearly destroyed physics, buried for 30 years)

If your best fact isn't one of these, keep researching — you don't have a hook yet.

### Step 4.2 — Pull 2-3 swipe-file hooks that match your angle

**This step is mandatory.** Open [swipe-file.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/swipe-file.md) (fetched in Step 0.5) and find 2-3 hooks whose **shape** matches your idea — same content category, similar opener move, similar number/contrast rhythm.

In your working notes, quote the swipe hooks you're modeling on. Example:
```
Modeling on:
- "In 1978, China was poorer than Chad, Bangladesh, and Malawi." (Type B year anchor + contrast)
- "Tesla was burning $4M per month on a car no one wanted. 0 sold. 3 weeks from bankruptcy." (stacked micro-facts)
```

This forces the hook to sound like the voice, not like a generic summary.

### Step 4.3 — Write the hook AS A THREAD HOOK

Write it like you're trying to get the tap, even for long-form. Thread-hook cadence = short lines, one idea per line, specific numbers, one sharp turn.

Minimum bar:
- **Line 1:** under 20 words, contains a specific number or named entity, scroll-stops on its own
- **Total hook unit:** 250-300 chars (long-form), under 280 (QRT)
- **One clear turn** (the "but"/"then"/"here's why" pivot)
- **No generic openers.** Banned: "In the world of...", "Most people don't realize...", "It's fascinating that...", "Did you know...", anything that could apply to any topic.

### Step 4.4 — Withhold the mechanism (do not spoil the body)

The hook names the authority and the frame. The body delivers the mechanism. Hold back:

- The specific fix (e.g. "$50 vaccine", "one regulation", "a single phone call")
- The specific actor (e.g. "the cook", "the engineer", "the whistleblower")
- The specific pathogen / product / exact failure mode
- The exact body count or dollar figure tied to the reveal

These are body reveals. The hook should make the reader need them — not hand them over.

**Named institutional villains > generic mechanisms.** Use FDA, FBI, FED, CIA, SEC, WHO, Pentagon, DOJ, specific companies and named individuals. Never "a federal agency", "authorities", "regulators", "someone". Named authorities scroll-stop on their own.

**Verb upgrades.** Swap neutral verbs for the approved pivot list: *buried, exposed, collapsed, seized, bankrupt, terrified, unleashed, rewrote, disrupted, refused.* Never: *decided to, started to, tried to, worked on, began.*

### Step 4.5 — Self-check before moving on

Answer these in one line each. If any is weak, rewrite:

1. Would a cold scroller stop on line 1? (Why?)
2. Which swipe-file hook is this closest to in shape?
3. What's the specific number or named entity doing the work?
4. What's the one turn?
5. What's being withheld for the body? (Must be at least one concrete mechanism / actor / figure.)

### Closer (always explicit)

Every hook — Tuki QRT AND long-form — ends with an **explicit closer** that opens the door into the body. Match the swipe file exactly.

Examples from the swipe file:
- *"Here's how [NAME] did it:"*
- *"Here's the full story:"*
- *"Here's the part that'll haunt you:"*
- *"Here's what nobody tells you:"*
- *"Here's the forgotten story:"*
- *"A thread"* / *"🧵"*
- *"Let me save you 3 hours — here are the [N] most important things:"*
- *"Once you understand how X, you'll Y:"*

Pick the closer that best tees up the body's first reveal. Never skip it. Never use an implicit door.

### Reference (optional deep dive)
[hook-writing.md](https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/docs/hook-writing.md) has the full taxonomy (opener types A-N, escalation types, pivot verbs, triggers). Consult only when stuck — do NOT try to satisfy every filter. The swipe file is the primary reference; hook-writing.md is the glossary.

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

## PHASE 8 — UPDATE NOTION (state transition: Writing → Needs Media)

For each processed idea, use `notion-update-page` with all changes in one call:

1. **Prepend `📺 ` to the title.** This is the marker that tells the local media-attacher task to pick this card up. The title goes from `Marie Curie's notebooks behind lead shields` → `📺 Marie Curie's notebooks behind lead shields`.
2. **Set Status → "Needs Media"** so the card moves on the kanban.
3. Save **Typefully Draft ID**.
4. Save **Typefully Shared URL**.
5. If QRT found via search, save to **QRT Source URL**.
6. Append to **Notes**: `Content generated [date]. Format: [Tuki QRT / Long-Form Post]. [QRT found — URL / standalone]. 📺 marker added — handed off to media-attacher.`

**NOTE:** Always set "Needs Media" with `📺 ` marker — never "Ready for Review" directly. The media-attacher task picks up `📺` cards, attaches clips/GIFs, removes the `📺` marker, and advances to "Ready for Review". Even standalone posts may need a clip or image.

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
