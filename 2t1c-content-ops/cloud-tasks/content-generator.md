# content-generator (Cloud Version)
# Cron: 0 6,18 * * * (6am and 6pm daily)
# Description: Pick 2-3 highest-urgency New ideas from Notion, write 1 draft per idea (Long-Form or Tuki QRT), create Typefully drafts, tag needs-media.

This is an automated run of a scheduled task. The user is not present to answer questions.

Use the Notion MCP connector (mcp__8c435ebc) for ALL Notion operations — notion-search, notion-fetch, notion-update-page.
Use the Typefully MCP for all Typefully operations.
Typefully social set ID for GeniusGTX (@GeniusGTX_2): 151393
Notion Idea Pipeline data source: collection://330aef7b-3feb-401e-abba-28452441a64d

⚠️ HARD LIMITS (non-negotiable, override everything else):
- Maximum 3 Typefully drafts per run. After creating 3 drafts, STOP. Do not create more under any circumstances.
- ONE draft per idea. Never create multiple angle variants, numbered series (#1, #2...), format variations (Straight, Contrarian, Commentary, Thread, Explainer, Stat Bomb...), or any other multiplication of a single idea.
- Each idea = 1 post. Either Long-Form Post OR Tuki QRT. Not both. Not 8 angles. ONE.
- If you find yourself about to create a 4th draft, STOP and proceed to Phase 9 (Report).

PHASE 0: PIPELINE AUDIT
Before anything else, get a full view of the pipeline.

DO NOT use semantic search to find ideas by status. Semantic search misses New ideas because they have sparse content and score low in relevance. Always use direct database queries filtered by Status.

Step 1 — Fetch the schema:
  Use notion-fetch on collection://330aef7b-3feb-401e-abba-28452441a64d to confirm property names.

Step 2 — Query each status bucket directly using notion-search on the Idea Pipeline with a filter on the Status property. Run all 8 queries in parallel:
  - Status = "New"
  - Status = "Writing"
  - Status = "Needs Media"
  - Status = "Ready for Review"
  - Status = "Approved"
  - Status = "Scheduled"
  - Status = "Published"
  - Status = "Killed"

  Each query returns the exact pages in that status — no guessing, no missing items.

Produce a status count from the query results:

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
This snapshot goes in the final report.

PHASE 1: PICK IDEAS TO PROCESS
Use the results from the Status = "New" query already fetched in Phase 0. Do NOT run a new search.

If the New query returned 0 results, conclude the pipeline is empty and stop.

Priority order:

🔴 Breaking (highest — process these first, time-sensitive)
🟡 Trending
🟢 Evergreen
⚪ Backlog (lowest)
Pick 2-3 ideas. NEVER more than 3. Set each to Status → "Writing" immediately using notion-update-page.

Recover stalled ideas: Use the results from the Status = "Writing" query already fetched in Phase 0. For each, check if it has a Typefully Draft ID. If the Typefully Draft ID is empty (no draft was ever created), treat it as a failed prior run — include it in this run's batch. Recovered ideas do NOT count against the 2-3 pick limit, BUT the total draft count (picked + recovered) must still not exceed 3. If recovering stalled ideas would push past 3 total, pick fewer new ideas.

If fewer than 5 "New" ideas remain after picking, flag this in the report so the pipeline needs restocking.

PHASE 2: RESEARCH
Run this phase for each picked idea.

Before writing, do real research. You must gather:

At least 3 specific data points (numbers, dates, dollar amounts, percentages)
At least 1 direct quote from the source in quotation marks, attributed by name (e.g. "Ray Dalio told Lex Fridman:")
1 unexpected connection one layer below the surface — the detail nobody else is covering
How to research:

Check the Source URL first for primary facts — use web_fetch on the URL
Search for additional context, counter-arguments, and specific numbers using web_search
If the source is a video/podcast: find the transcript and pull the most powerful line verbatim
If the source is a tweet: read the full thread and any linked articles
If the source is an article: find the original data or study being cited
Attribution rule: When using a quote, always name the person. Never use an unattributed quote.

Never write with vague facts. If you can't find at least 3 specific data points, skip this idea, set it back to "New" using notion-update-page, and pick the next one.

PHASE 3: QRT-FIRST MEDIA STRATEGY
Run this phase for each picked idea.

Check the idea's QRT Source URL field first — if it's already populated, that's the QRT target. Done.

If QRT Source URL is empty:

Source Type = Twitter: The Source URL IS the QRT target. Save it to QRT Source URL.
Source Type = YouTube or Articles: Search Twitter for a trending tweet on the same topic. Use web_search for: site:x.com [topic keywords]. Look for tweets from the last 24-48 hours with high engagement. If found: save that tweet URL to QRT Source URL. If not found: the post will be standalone.
QRT Tracing Rule: If the source tweet is itself a QRT, trace back to the ORIGINAL tweet being quoted. QRT the original author's tweet, not the QRTer's.

URL VERIFICATION RULE (non-negotiable): Before saving any tweet URL to QRT Source URL, you must pass TWO checks:

Check 1 — Format check: A real tweet URL has a numeric ID that does not end in multiple zeros (e.g. ...000000). If a URL looks like a placeholder, reject it immediately.

Check 2 — Active existence check (even if Check 1 passes): Run a web_search for the exact tweet URL string (e.g. search: "x.com/handle/status/1234567890"). Confirm the tweet exists and the content matches the idea. The handle being correct is NOT sufficient — the numeric tweet ID must also be independently confirmed via search results.

If either check fails: Do NOT save the URL. Leave QRT Source URL empty and mark the post as standalone. Note in the report: "QRT URL unverified — posted standalone."

This prevents the known failure mode where the source account handle is correct but the tweet ID is wrong, resulting in a broken or misattributed QRT link.

Format decision (ONE format per idea, not multiple):

QRT found → Write in Tuki QRT style
No QRT (standalone) → Write in Long-Form Post style

PHASE 4: WRITE THE HOOK
Run this phase for each picked idea.

Read the Hook Writing Guide from Notion before writing — use notion-fetch on: https://www.notion.so/33004fca179481cda1dec88ca30837cc

The hook must stop the scroll within 280 characters.

Angle Finding (BEFORE writing the hook)
Run the three filters:

Unexpected Association — Connection between two recognizable things the reader wouldn't put together?
Visualization Test — Can you describe the core moment in one sentence and picture it clearly?
Primal Trigger Test — Does it activate: betrayal, survival, love under pressure, vulnerability behind power, sacrifice, or injustice at scale?
If the angle fails any filter, run the Expansion Move: find the authority → find the unexpected action → find the secondary ring → visualize the scene.

Never start writing the hook until the angle passes the Visualization Test.

Hook Construction
For QRT posts:

Type F (Recency Signal): time word + name + action. Default opener for QRT posts.
Type E (Quote Drop): Only use if the quote is genuinely strong — counterintuitive, transgressive, or impossible to paraphrase better. If the quote is merely descriptive or summarizing, use Type F instead. Never lead with a quote just because one exists.
For Long-Form posts (standalone):

Type A (Superlative Claim): Absolute declaration, never hedged. Default opener.
Type B (Year Anchor): Specific year + vivid detail + unexpected comparison
Type K (Personal Obsession): Writer's fixation as credibility signal
Type E (Quote Drop): Only if the quote would stop the scroll on its own — shocking, transgressive, or from an unlikely source saying the unexpected thing. Do not open with a quote just to open with a quote.
Hook Rules (non-negotiable)
One sentence per line
Exactly one pivot phrase
Approved pivot verbs: rewrote, exposed, transformed, revealed, collapsed, disrupted, bankrupt, seized, terrified, refused, buried, unleashed
NEVER use: decided to, started to, tried to, worked on, began
Numbers exact and comparative: "$7.4 BILLION" not "billions"
Speed reveals use "just": "collapsed in just 28 days"
Superlatives absolute: "the greatest" not "one of the greatest"
Hook: 250-300 characters total. Scroll-stop in first 150.

TRUTH-STRUCTURE TRANSITION (non-negotiable)
The hook grabs attention. Line 2 begins building truth — not amplifying the hook.

After the hook, never spend lines restating or piling hype onto what was just said.
Line 2 answers one question: "Why was this hard, impossible, or unseen until now?"
That is the origin point. Lead with it immediately after the hook.

Hook = what happened (signal, pattern interrupt, scroll-stop)
Line 2 = why it couldn't have happened before (the wall)

The wall does not need to be long. It needs to be the right obstacle — the one that makes every fact that follows feel earned rather than asserted.

PHASE 5: WRITE THE BODY
Run this phase for each picked idea.

Read the Writing Style Guide from Notion before writing — use notion-fetch on: https://www.notion.so/33004fca179481f9b85cde9132b145b6

TUKI QRT STYLE (when QRT found)
Opener: Flexible — no siren emoji (never use 🚨). Use time word + name + action (Type F) or lead directly with a direct quote in quotation marks (Type E). The opener IS the hook from Phase 4.
Proper capitalization and grammar. Proper nouns, sentence starts, and acronyms capitalized.
Use normal single periods. Never use double periods (..) — one period per sentence ending.

Structure (flexible in length, fixed in sequence):
1. Hook — the scroll-stop opener (Phase 4 output)
2. Wall — why this situation was hard, impossible, or previously unseen. Establishes the obstacle before any facts land. Length varies by story — use as many lines as needed to make the obstacle feel real, but no more.
3. Breach (optional) — the specific thing that cleared the wall. One line. Only include if the mechanism is non-obvious. Skip if the wall already implies it.
4. Facts — 3-6 lines starting with "→". Blank line between each → fact. Ordered causally: each line must require the next. Never list facts in arbitrary order. One mechanism explanation is allowed across all facts — identify the single most load-bearing causal link and explain it. All other facts stay lean.
5. Close — State the transferable principle the post just proved. The "I think..." pivot completes the sentence: "what this proves about how the world works is..." — not just an emotional reaction. Must be ORIGINAL. Length varies — use what the story earns.

Voice: casual, urgent, editorial. Diagnose the mechanism, never moralize.

LONG-FORM POST STYLE (standalone, no QRT)
Length: ~200 words (approximately 1100-1300 characters). Aim tight. Over 230 words = trim.
Structure: Hook → Wall → Build → Turn → Landing → CTA
Approach driven by Content Angle

Wall replaces generic Setup: The first section after the hook establishes why the situation existed or why the outcome was previously impossible. This is the origin point — the structural condition the rest of the post resolves. Without it, the Build is just a list of claims.

WRITING RULES (ALL posts)
Voice:

Systems thinker perspective. Diagnose mechanisms, never moralize.
Incentive-first: identify who benefits before accepting any narrative.
Calibrated urgency. Never doom. Never hype.
The reader is smart, slightly frustrated, beginning to see the rules weren't written for them.
Exit feeling: the world is more legible, reader has one actionable thing.

Truth Over Trust:

The goal is never to convince — it is to show the reader what has to be true.

- Never start with the claim and back it up. Start with the obstacle, then build causally to the claim. The claim is the conclusion the reader reaches, not the premise they are asked to accept.
- Replace assertion language with IF/THEN structure. Instead of "this is massive" — write "if this measurement has been wrong for 20 years, then every policy built on it carries the same error." Let the logic declare the significance.
- Sequence facts causally. Each → fact must require the next. Test: can you swap any two fact lines without losing meaning? If yes, reorder until the answer is no.
- One mechanism per post. Find the single most load-bearing causal link — the one where if the reader doesn't understand it, the facts float without weight. Explain that one clearly. Everything else stays lean.
- The close names a principle, not just an emotion. The "I think..." pivot should complete: "what this proves about how the world works is..." A reader who finished the post should feel they reached that conclusion themselves.
- No assertion lines. Cut any line that says "this changes everything", "nobody is talking about this", or "this is huge." Replace each one with the structural reason it matters.

Direct Quotes (prioritize over paraphrase):

Pull direct quotes in quotation marks. Always attributed by name.
One quote per section. Two back-to-back = transcript summary.
After the quote, don't explain it. Trust the reader.

Formatting:

Blank line above and below every paragraph.
Max 2 sentences per paragraph. Hard limit.
Sentences: Short. One idea per sentence. If a sentence exceeds 18 words, split it. The reader is on mobile, scrolling fast.
No em dashes. Split into new sentences.
One idea per paragraph. Vary rhythm deliberately.

Length:

Total: ~200 words (approximately 1100-1300 characters). Under 160 words = thin. Over 230 words = trim.

Banned:

AI words: delve, tapestry, nuanced, pivotal, groundbreaking, transformative, foster, leverage, utilize, paradigm, holistic, synergy, robust, comprehensive, multifaceted, underscores, highlights.
Openers: "In today's world", "It's no secret", "Throughout history"
Transitions: Furthermore, Moreover, Additionally, In conclusion
Hedging: "might potentially", "could possibly", "seems to suggest"
Twitter patterns: "Let that sink in", "Nobody is talking about it", "Here's the thing"

PHASE 6: CTA CLOSER
Every post ends with this exact three-part structure. Never deviate from Parts 2 and 3.

Part 1 — Bridge (write fresh for every post, 1-2 sentences):
Name the specific thinking pattern the post demonstrated and connect it directly to the toolkit. Not "mental models help you see things early" — but which mental model, applied how, produced the insight in this specific post. Reference the exact mechanism, question, or causal structure the post revealed. The reader should feel: "yes, that's exactly the kind of thinking I want more of." A generic bridge that could apply to any post is a failure — rewrite it until it could only belong to this post.

Part 2 — Product CTA (exact wording, never change a single word):
I made a free toolkit breaking down 100+ mental models used by history's greatest thinkers — the same frameworks that help you see patterns like this before everyone else.

5,000+ downloads. 113 five-star reviews.

Comment "MODELS" and I'll send it to you.

Part 3 — Brand CTA (exact wording, never change a single word):
If you're new here, @GeniusGTX is a gallery for the greatest minds in economics, psychology, and history. Follow along for more similar content.

CTA Rules:
- The keyword is always MODELS (never lowercase, never a different word)
- The bridge MUST connect the specific post topic to the toolkit — no generic bridges
- Never say "link in bio" — always use the comment keyword mechanic
- For Tuki QRT posts: the bridge follows lowercase style, Parts 2 and 3 stay in their exact wording
- Never add "That's a wrap." — removed from the template

PHASE 7: CREATE TYPEFULLY DRAFTS
Use the Typefully MCP. Social set ID: 151393.

⚠️ CHECKPOINT: Count how many drafts you are about to create. If the number exceeds 3, STOP and reduce to 3. Go back and drop the lowest-priority ideas.

Create ONE draft per picked idea. Every draft is a two-post thread.

For each draft:

Post text: First words of output ARE first words of the post. No preamble.
Draft title: Use the idea's Notion title (the "Idea" field) verbatim. REQUIRED — always set this.
Quote post URL: The QRT Source URL (if found) — applies to post 1 only.
Share: true
No leading whitespace (CRITICAL): The text field must start with the first visible character of the post — never a newline or space.
Scratchpad (REQUIRED): Always set scratchpad_text to exactly two lines:
  Notion: [full Notion page URL]
  Source: [Source URL from the idea]

FOLLOW-UP REPLY POST (post 2 — fixed, never change a single word):
Every draft must include a second post in the thread with this exact text:

I made the ultimate toolkit with 100+ timeless problem-solving and clear-thinking mental models used by history's greatest thinkers.

5,000+ downloads. 113 five-star reviews.

Click below for a free copy to unlock your genius thinking:

https://besuperhuman.gumroad.com/l/mentalmodels

This second post has no quote_post_url. It is always post 2 in the posts array. Never omit it.

⚠️ SELF-CHECK after creating drafts: Count the drafts you just created. If you created more than 3, you violated the hard limit. Report this in Phase 9.

PHASE 8: UPDATE NOTION
For each processed idea, use notion-update-page to:

Save Typefully Draft ID to the idea
Save Typefully Shared URL to the idea
If QRT found via search, save to QRT Source URL
Set Status → "Needs Media"
Update Notes — append: Content generated [date]. Format: [Tuki QRT / Long-Form Post]. [QRT found — URL / standalone]. Tagged needs-media.

NOTE: Always set "Needs Media" after content generation — never "Ready for Review". The media-attacher task is responsible for attaching clips/GIFs and advancing to "Ready for Review". Even standalone posts (no QRT) may need a clip or image added from the video/article source.

PHASE 9: REPORT

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
  Draft: [Typefully share URL]

Draft 2:
  ...

Draft 3 (if applicable):
  ...

═══ PIPELINE HEALTH ═══
"New" ideas remaining: [count]
Refill needed: [yes/no]
Draft count this run: [number] (MUST be ≤ 3)

RULES
⛔ MAXIMUM 3 DRAFTS PER RUN. This is a hard ceiling. No exceptions.
⛔ ONE DRAFT PER IDEA. Never create multiple angles, variants, numbered series, or format variations of the same idea. One idea = one post = one draft.
⛔ ONE FORMAT PER IDEA. Either Tuki QRT or Long-Form Post. Not both. Not 8 angles. ONE.
Process 2-3 ideas per run (never more than 3)
First words of output ARE the post. No meta-text.
Must gather 3+ data points and 1+ attributed quote before writing.
If research fails, skip idea, set back to "New", pick next.
Never publish or schedule. Draft only.
Notion is single source of truth.

ANTI-REPETITION RULES
Never same format twice for same idea
Topic rotation: no 3+ consecutive same-topic posts
Check last 5 drafts created — avoid repeating the same angle or source
