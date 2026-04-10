---
name: char-counter
description: >
  Check character counts on post content against GeniusGTX pipeline targets.
  Triggered when: asked to "check character count", "is this too long",
  "does this fit", or when reviewing any post before scheduling.
  Uses tools/char_counter.py.
---

# Character Counter — Post Length Checker

Use this tool to verify post length against GeniusGTX format targets before
tagging any draft as ready-to-post.

## Quick Usage

```bash
cd /Users/toantruong/Desktop/AI\ Agents/2t1c-content-ops
python3 tools/char_counter.py "Your post text here"
```

Or pipe a file:
```bash
cat post.txt | python3 tools/char_counter.py
```

## Character Targets (Pipeline Reference)

| Format | Target Range | Notes |
|--------|-------------|-------|
| Hook (opener line) | 250–280 chars | Must stop scroll in 1-2 lines |
| Standalone tweet | 1–280 chars | Twitter hard limit |
| Long-form post | 1,000–2,000 chars | Body + hook + CTA combined |
| Tuki post | 500–1,000 chars | Short editorial reaction + CTA |

**Note:** The hook range in char_counter.py shows 250-300 — treat 280 as the hard
ceiling since that is Twitter's original tweet length (scroll-stopping test).

**Tuki posts** run shorter than long-form — they are reactions, not essays.
Target 500-1000 chars, not 1000-2000.

## When to Use This

Run the character counter:
1. **Before tagging `ready-for-review`** — confirm the post is in range
2. **When the hook feels too long** — check if it exceeds 280 chars
3. **When a long-form post feels bloated** — check if it's over 2000 chars
4. **When a Tuki post feels like it's dragging** — check if it's over 1000 chars

## macOS Quick Action (optional)

An Automator Quick Action is available for instant character counting from
anywhere on the Mac:
- Setup guide: `docs/char_counter_automator_setup.txt`
- Select any text → Right-click → Services → "Count Characters"
- A notification shows the count and target evaluation

This is useful when reviewing drafts in Typefully directly.
