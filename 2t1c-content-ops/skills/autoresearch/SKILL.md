---
name: autoresearch
description: >
  Autonomous optimization loop for the GeniusGTX content system.
  Triggered when: the agent is told to "optimize", "improve", "autoresearch",
  or "run experiments on" writing skills, hook templates, or format definitions.
  NOT for regular content writing — this is the meta-layer that makes
  the writing system better over time.
---

# Autoresearch — Content System Optimizer

Adapted from Karpathy's autoresearch pattern. You are an autonomous researcher
running experiments on the GeniusGTX content pipeline. Your goal: make every
part of the system produce better content, measured by real performance data.

## The Contract

Three zones, same as the original:

| Zone | Files | Rule |
|---|---|---|
| **SANDBOX** (you modify) | `skills/writing-system/SKILL.md`, `skills/writing-system/references/*`, `skills/hook-writing-system/SKILL.md`, `skills/hook-writing-system/references/*`, `pipeline/format_definitions.py` | Fair game. Experiment freely. |
| **EVAL** (read-only) | Typefully analytics, Notion Idea Pipeline, draft approval history | Ground truth. Never modify. |
| **INFRASTRUCTURE** (never touch) | `tools/*`, `pipeline/format_pipeline.py`, `pipeline/longform_pipeline.py`, `pipeline/tuki_pipeline.py`, `pipeline/media_*.py`, `pipeline/notion_sync.py`, Notion content/guidelines | Off limits. These are the plumbing. |

## Primary Optimization Target: Hooks

The hook is the most important element. Hook templates (`skills/hook-writing-system/`) are the
primary optimization target. All other areas (voice, format, examples) are secondary and rotate
after hooks have been tested in each cycle.

## Eval Metrics — Views & Analytics First

| Metric | Source | Weight | How to Measure |
|---|---|---|---|
| **avg_views** | Typefully analytics | 50% | Average views per published post |
| **avg_engagement** | Typefully analytics | 30% | Average (likes + retweets + replies) per post |
| **format_diversity** | Typefully drafts | 10% | Number of distinct formats used (max 11) |
| **toan_approval** | Toản's eye test | 10% | Binary: approved or rejected by Toản during feedback batch |

**Composite score:** `(normalized_views × 0.5) + (normalized_engagement × 0.3) + (format_diversity/11 × 0.1) + (toan_approval_rate × 0.1)`

Normalize views and engagement against the 30-day baseline average. A score > 1.0 means you're beating the baseline.

## Two Feedback Loops

### Loop 1: Analytics (72-hour delay)
- After publishing experiment posts, **wait 72 hours** for accurate data
- Pull Typefully analytics for the experiment posts
- Compare views and engagement against baseline
- This is the ground truth — slow but accurate

### Loop 2: Toản's Eye Test (fast, batched)
- Create experiment drafts tagged `autoresearch-test` in Typefully
- Toản reviews them during the week in batches
- Approved = signal to keep the change
- Rejected = signal to discard
- This is faster but subjective — use it to pre-filter before waiting 72h

## The Experiment Loop

**SETUP (run once at start):**

1. Read the current state of all SANDBOX files
2. Pull baseline metrics from Typefully analytics (last 30 days)
3. Record baseline in `autoresearch_results.tsv`
4. Create a git branch: `autoresearch/<date>`
5. Confirm setup, then begin

**LOOP FOREVER:**

1. **HYPOTHESIZE** — Pick ONE specific change to test:
   - A hook pattern modification (new opener formula, different angle approach) — PRIORITY
   - A writing voice tweak (tone, rhythm, sentence structure)
   - A format definition adjustment (word count, structure, media rules)
   - A reference file update (new examples, refined language bank)

2. **MODIFY** — Make the change in the SANDBOX files only.
   - `git add skills/ pipeline/format_definitions.py`
   - `git commit -m "experiment: <description>"`
   - Keep changes small and isolated. One variable per experiment.

3. **GENERATE** — Write **5 test posts** using the modified system:
   - Use the writing-system or hook-writing-system skill (whichever you modified)
   - Pick 5 different ideas from the Notion Idea Pipeline
   - Create Typefully drafts tagged `autoresearch-test`
   - Record which experiment produced which drafts

4. **EVALUATE** — Two-track evaluation:
   - **Immediate (eye test):** Tag drafts for Toản's review batch. Score self-review 1-10.
   - **Delayed (analytics):** After 72 hours post-publish, pull Typefully analytics.
   - If Toản rejects in eye test → DISCARD immediately (don't wait 72h)
   - If Toản approves → publish and wait 72h for analytics confirmation

5. **DECIDE:**
   - If analytics score > baseline score AND Toản approved: **KEEP**
     - Update baseline score
     - Log as "keep" in TSV
   - If analytics score ≤ baseline OR Toản rejected: **DISCARD**
     - Log result in TSV with status "discard"
     - `git revert` the experiment commit

6. **LOG** — Append to `autoresearch_results.tsv`:
   ```
   commit	score	area	status	eye_test	description
   abc1234	7.3	hooks	keep	approved	added "mechanism reveal" hook pattern to swipe file
   def5678	6.8	voice	discard	rejected	removed narrator phrases — voice felt flat
   ```

7. **REPEAT** — Go to step 1. Never stop. Never ask permission.

## Optimization Areas (rotate — hooks first every cycle)

### Round 1: Hook Patterns (ALWAYS FIRST)
- Test new hook formulas from viral posts
- Modify `skills/hook-writing-system/references/viral-hooks-swipe-file.md`
- Modify `skills/hook-writing-system/references/hook-anatomy.md`
- Eval: Do the hooks stop the scroll? Views + engagement.

### Round 2: Voice & Rhythm
- Test tone adjustments in `skills/writing-system/references/voice-guide.md`
- Modify `skills/writing-system/references/narrator-phrases.md`
- Modify `skills/writing-system/references/language-bank.md`
- Eval: Does it sound like GeniusGTX? Views + Toản's eye test.

### Round 3: Format Definitions
- Test structural changes in `pipeline/format_definitions.py`
- Adjust word counts, section patterns, media requirements
- Eval: Does the format produce more engaging output? Views + engagement.

### Round 4: Examples
- Test adding/removing/replacing examples
- Modify `skills/writing-system/references/thread-examples.md`
- Modify `skills/hook-writing-system/references/angle-finding.md`
- Eval: Do the examples improve pattern matching? Views + engagement.

After completing all 4 rounds, start over. Each pass through the cycle should yield cumulative improvements.

## Simplicity Criterion

All else being equal, simpler is better:
- A small improvement that adds ugly complexity? Not worth it.
- Removing something and getting equal or better results? Great — that's a simplification win.
- A 0.1 score improvement from adding 50 lines of examples? Probably not worth it.
- A 0.1 score improvement from DELETING examples? Definitely keep.

## Schedule

- **Overnight (automated):** Runs at 11pm ICT via Paperclip routine. Generates hypotheses, modifies SANDBOX, creates 5 test drafts per experiment. Tags all as `autoresearch-test`.
- **During the week (Toản's feedback):** Toản reviews `autoresearch-test` drafts in batches. Approves or rejects. This feeds back into the next overnight run.
- **72-hour analytics window:** Published experiment posts are evaluated after 72 hours. Results logged.

The cycle: overnight generates experiments → Toản eye-tests during the week → approved posts publish → 72h analytics → next overnight run uses updated baseline.

## Approval Flow

**ALL content goes through Toản.** No auto-publishing. Autoresearch creates drafts tagged `autoresearch-test`. Toản approves or kills them. Only approved drafts get published and enter the 72-hour analytics window.

## Results File

Create `autoresearch_results.tsv` in the repo root:

```
commit	score	area	status	eye_test	description
baseline	6.5	-	keep	-	initial baseline from current system
```

Tab-separated. Never use commas in descriptions.
