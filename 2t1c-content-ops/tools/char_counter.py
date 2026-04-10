#!/usr/bin/env python3
"""
GeniusThinking Character Counter
---------------------------------
Counts characters in a post and tells you exactly where it
sits against the pipeline targets.

Usage (three ways):
  1. python char_counter.py                  → paste text, hit Enter twice
  2. python char_counter.py "your text here" → inline text argument
  3. cat post.txt | python char_counter.py   → pipe a file

Targets:
  Tuki post         : 1000 – 2000 chars
  Hook (all formats): 250 – 300 chars
  Long-form post    : 1000 – 2000 chars
  Standalone tweet  : 1 – 280 chars
"""

import sys

# ── targets ─────────────────────────────────────────────────────────────────
TARGETS = {
    "Hook (thread / long-form)": (250, 300),
    "Tuki post":                 (1000, 2000),
    "Long-form post":            (1000, 2000),
    "Standalone tweet":          (1, 280),
}

# ── helpers ──────────────────────────────────────────────────────────────────
def bar(count, lo, hi, width=40):
    """Render a simple ASCII progress bar."""
    filled = min(width, int((count / hi) * width))
    over   = count > hi
    under  = count < lo
    if over:
        b = "█" * width + " OVER"
    elif under:
        b = "░" * filled + "─" * (width - filled) + " UNDER"
    else:
        b = "█" * filled + "░" * (width - filled) + " OK"
    return b

def evaluate(count, lo, hi):
    if count < lo:
        diff = lo - count
        return f"UNDER by {diff} chars  (need {diff} more)"
    elif count > hi:
        diff = count - hi
        return f"OVER by {diff} chars  (cut {diff})"
    else:
        return f"IN RANGE ✓"

def analyse(text):
    count = len(text)
    words = len(text.split())

    print()
    print("─" * 52)
    print(f"  CHARACTERS : {count}")
    print(f"  WORDS      : {words}")
    print("─" * 52)

    print()
    for name, (lo, hi) in TARGETS.items():
        status = evaluate(count, lo, hi)
        b      = bar(count, lo, hi)
        print(f"  {name}")
        print(f"  [{b}]")
        print(f"  {lo}–{hi} chars → {status}")
        print()

    print("─" * 52)
    print()

# ── entry point ───────────────────────────────────────────────────────────────
def main():
    # Inline argument
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])

    # Piped input
    elif not sys.stdin.isatty():
        text = sys.stdin.read()

    # Interactive paste
    else:
        print("Paste your post text below.")
        print("Press ENTER twice when done.")
        print()
        lines = []
        blank_count = 0
        while True:
            try:
                line = input()
                if line == "":
                    blank_count += 1
                    if blank_count >= 2:
                        break
                    lines.append(line)
                else:
                    blank_count = 0
                    lines.append(line)
            except EOFError:
                break
        text = "\n".join(lines).rstrip()

    if not text.strip():
        print("No text provided.")
        sys.exit(1)

    analyse(text)

if __name__ == "__main__":
    main()
