# 📋 Content Generation Playbook

> Source of truth: Notion page `33104fca-1794-818c-b9a8-fce540da0a66`
> Last synced: 2026-03-28

The single source of truth for how content is generated from a qualifying idea. Every agent — scheduled tasks, Claude Code, Paperclips, or manual — reads this page before producing any content.

This playbook governs the creative workflow AFTER an idea qualifies. It does not cover scanning, filtering, or thresholds. Those live in each scanner's own instructions.

Before writing anything, also read:
- 🪝 Hook Writing Guide — angle finding, opener types, emotional triggers, language bank
- ✍️ Writing Style Guide — body voice, rhythm, formatting, humanist landing

---

## Step 1 — Jordan Writes the Hook

### Exception: Tuki Style (Format 4: Summary QRT + GIF)

Jordan does NOT write a hook for Tuki Style. Maya handles the full post. The Tuki opener is always:

🚨 Do you understand what [just happened]..

Always lowercase. Always double periods (..). Skip Jordan entirely for this format.

### All Other Formats — Jordan's 5-Step Hook Process

**Step 1 — Angle Brief**
Identify the angle using the Angle Finding system from the 🪝 Hook Writing Guide.
Output: Topic, Angle, Angle Strength Level (1-4), which Primal Triggers it hits, Visualization Test result.

**Step 2 — Structure Brief**
Select the Opener Type (A through M), Escalation Type (A through D), and Closer Type (A through G) from the Hook Anatomy system.

**Step 3 — Assemble the Hook**
Write the hook inside the selected frame. Must land within 280 characters for the scroll-stop moment. One sentence per line. No em dashes.

**Step 4 — 4-Layer Baseline Rubric**
Evaluate against: Visualization Test, Primal Trigger, 280-char scroll-stop, closer opens door without summarizing.

**Step 5 — Autoresearch Loop**
Generate 3 hook candidates. Identify the weakest. Mutate it. Present the top 3 for selection.

---

## Step 2 — Maya Writes the Body

Maya takes the approved hook and writes the post body following the ✍️ Writing Style Guide:

- Voice: the reader finishes feeling smarter, not lectured to
- Rhythm: natural speaking pace, varied sentence length, no stacked one-liners
- Structure: setup → build → turn → landing
- Landing: humanist conclusion, never cynical, never a summary
- Follow CTA: "That's a wrap." → account description → "We are ONE genius away."

### Length & Spacing Rules

The body must be **concise**. Default target is roughly half of what feels "complete." Cut every paragraph that restates a point already made.

Every major beat gets its own spaced paragraph with a blank line above and below. One idea per paragraph.

If the final post (hook + body + CTA) exceeds roughly 25 paragraphs, it is too long. Cut from the middle.

---

## Step 3 — Media Prioritization

Every post must have at least one media element before being sent to Typefully.

### Priority 1 — QRT (Quote Retweet)
For Twitter-sourced ideas, QRT the original source.
- Use qrt_source_url if it exists (the original news post being quoted) — this is the default
- Fall back to source_url if no qrt_source_url exists
- Mandatory for any Twitter-sourced idea

### Priority 2 — GIF
If no QRT is available (non-Twitter source or original idea), attach a GIF using the GIF Brief process.

### Priority 3 — Both QRT + GIF
Use both for:
- Urgency = 🔴 Breaking
- Format = Summary QRT + GIF (Tuki Style) — always both

### Text-Only Exceptions
- Format 2 (Let Me Get This Straight) — text only
- Format 10 (Long-Form Text Only) — text only
- Format 11 (X Article) — uses thumbnail instead

### YouTube-Sourced Content
For video-based formats (Format 7, 8, 9): the video clip IS the primary media.
For text-based formats from YouTube ideas: check for a Twitter account posting the same story for QRT. If none, use GIF.

---

## Step 4 — GIF Brief Process

When a GIF is required, output this structured brief:

```
---
GIF REQUIRED
Folder: "Reaction GIF for Twitter content" (local device)
Mood: [one word — dread / shock / disbelief / dark realization / contempt / exhaustion]
Visual style: [describe the scene]
Avoid: funny / lighthearted / meme-style — always
Search terms: [2-3 keywords]
---
```

### Mood Guide by Topic
- Crime / fraud / insider trading → detective or investigation scenes
- War / geopolitics / conflict → apocalyptic or tension scenes
- Death / philosophical → contemplative movie scenes
- Security / surveillance / hack → trap or mechanism GIFs
- Institutional betrayal / systemic failure → person staring in disbelief, slow collapse

Rules: Always dark/cinematic. Never funny. Duration 0:01 to 0:13 seconds.

---

## Step 5 — Draft to Typefully

For 🔴 Breaking ideas, create a Typefully draft immediately using social set 151393.

Include in the draft:
- The approved hook (from Jordan's process)
- The post body (from Maya)
- The QRT URL as an attachment (if applicable)
- The GIF brief in the Notes field (human will add the GIF manually)

Tag the draft "needs-media" if a GIF brief was generated but not yet attached.

Update the Notion Idea Pipeline:
- Status → "Drafting"
- Typefully Draft ID → [the draft ID returned by Typefully]

### Typefully Tags
- **in-progress** — draft being worked on
- **ready-for-review** — content complete, awaiting human review
- **ready-to-post** — approved, can be scheduled or posted
- **needs-media** — GIF brief generated, human needs to attach the GIF

---

## Anti-Repetition Rules
- 3-hour minimum gap between same-idea posts
- Never use the same format twice for the same idea in a row
- Topic rotation: don't post 3+ ideas on the same topic consecutively

---

*Version 1.0 — March 2026*
