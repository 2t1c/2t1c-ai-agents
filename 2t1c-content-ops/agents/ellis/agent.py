"""
Ellis — Quality Control Manager for GeniusGTX

Evaluates every draft against the writing standards rubric before it reaches
Toan for review. Posts that fail get sent back to Maya with specific feedback.

Pipeline position:
    Format Pipeline → status "QC Review" → Ellis evaluates → PASS/FAIL
    PASS → status "Ready for Review" → Telegram bot sends to Toan
    FAIL → Maya revises with Ellis's feedback → Ellis re-evaluates (max 3 rounds)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


def load_skill() -> str:
    """Load Ellis's QC rubric."""
    if SKILL_PATH.exists():
        return SKILL_PATH.read_text(encoding="utf-8")
    return ""


def _build_system_prompt() -> str:
    """Build system prompt fresh each call so skill edits take effect without restart."""
    return f"""You are Ellis, the QC manager for the GeniusGTX content team.

Your ONLY job is to evaluate drafts against the quality rubric below. You are not a writer. You do not rewrite. You evaluate and give specific, actionable feedback.

You must return ONLY a valid JSON object. No prose before or after. No markdown code fences. Just the JSON.

{load_skill()}

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
"""


# Formats that REQUIRE media attached
MEDIA_REQUIRED_FORMATS = {
    "Tuki QRT", "Stat Bomb", "Explainer", "Contrarian Take",
    "Multi-Source Explainer", "Video Clip Post", "Clip Commentary",
    "Clip Thread",
}
MEDIA_OPTIONAL_FORMATS = {"Commentary Post", "Thread", "Bark QRT"}

PASS_THRESHOLD = 9  # out of 12


def evaluate(
    post_text: str,
    format_name: str = "",
    source_url: str = "",
    has_media: bool = True,
) -> dict:
    """
    Evaluate a draft against the GeniusGTX quality standards.

    Args:
        post_text: The full post text to evaluate.
        format_name: The content format (e.g. "Tuki QRT", "Stat Bomb").
        source_url: The source URL (tweet, video, article) if applicable.
        has_media: Whether the draft has media (GIF, clip, image) attached.

    Returns:
        Dict with keys: verdict, score, failures, feedback, notes,
        plus direct_fixes (list of {old, new} replacements Ellis can make herself).
    """
    context_parts = [f"FORMAT: {format_name}"] if format_name else []
    if source_url:
        context_parts.append(f"SOURCE: {source_url}")
    context_parts.append(f"DRAFT:\n{post_text}")

    user_message = "\n\n".join(context_parts) + """

Evaluate this draft against the 10-check QC rubric (checks 1-9, media is checked separately).
Return ONLY a JSON object:
{
  "score": <0-11>,
  "hook_strength": <0-2>,
  "structure": <0-1>,
  "rhythm": <0-2>,
  "voice": <0-1>,
  "banned_patterns": <0-1>,
  "iceberg_depth": <0-1>,
  "landing": <0-1>,
  "i_factor": <0-1>,
  "format_compliance": <0-1>,
  "failures": ["specific failure 1", ...],
  "feedback": "Concise actionable feedback for Maya if needed. Empty string if clean.",
  "notes": "One-line summary.",
  "direct_fixes": [
    {"old": "exact phrase to remove or replace", "new": "replacement (empty string to delete)"}
  ]
}

IMPORTANT about direct_fixes:
- ONLY include fixes that are mechanical: removing a filler phrase, removing a banned word,
  adding missing CTA lines, fixing em dashes → periods.
- The "old" value must be an EXACT substring match from the draft.
- If the fix requires rethinking or rewriting a section, put it in "feedback" instead.
- If no direct fixes are possible, return an empty array.
- Max 3 direct fixes. Beyond that, send to Maya."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Parse JSON — handle potential markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "verdict": "FAIL",
            "score": 0,
            "failures": ["Could not parse QC evaluation"],
            "feedback": "",
            "notes": f"Parse error. Raw: {raw[:200]}",
            "direct_fixes": [],
        }

    # Media check (done in code, not by LLM)
    media_score = 1
    if format_name in MEDIA_REQUIRED_FORMATS and not has_media:
        media_score = 0
        result.setdefault("failures", []).append(
            f"MEDIA: {format_name} requires media (GIF/clip) but none is attached."
        )
    result["media_check"] = media_score

    # Compute total score (LLM scores 0-11 for checks 1-9, + media = 0-12)
    llm_score = result.get("score", 0)
    result["score"] = min(llm_score + media_score, 12)

    # Verdict
    if result["score"] >= PASS_THRESHOLD:
        result["verdict"] = "PASS"
    else:
        result["verdict"] = "FAIL"

    # Ensure direct_fixes is present
    result.setdefault("direct_fixes", [])

    return result


def apply_direct_fixes(post_text: str, fixes: list[dict]) -> tuple[str, list[str]]:
    """
    Apply Ellis's direct fixes to the post text.

    Returns (fixed_text, list_of_changes_made).
    Only applies fixes where the "old" string is an exact match in the text.
    """
    changes = []
    fixed = post_text

    for fix in fixes[:3]:  # Max 3 fixes
        old = fix.get("old", "")
        new = fix.get("new", "")
        if not old:
            continue
        if old in fixed:
            fixed = fixed.replace(old, new, 1)
            action = f"Removed: '{old[:60]}'" if not new else f"Replaced: '{old[:40]}' → '{new[:40]}'"
            changes.append(action)

    return fixed, changes


def evaluate_and_format(
    post_text: str,
    format_name: str = "",
    source_url: str = "",
    has_media: bool = True,
) -> str:
    """
    Evaluate and return a human-readable summary.
    Used for CLI output and logging.
    """
    result = evaluate(post_text, format_name, source_url, has_media)

    lines = [
        f"{'PASS' if result['verdict'] == 'PASS' else 'FAIL'} ({result.get('score', '?')}/12)",
        "",
    ]

    checks = [
        ("Hook Strength", "hook_strength", "/2"),
        ("Structure", "structure", "/1"),
        ("Rhythm", "rhythm", "/2"),
        ("Voice", "voice", "/1"),
        ("Banned Patterns", "banned_patterns", "/1"),
        ("Iceberg Depth", "iceberg_depth", "/1"),
        ("Landing", "landing", "/1"),
        ("I Factor", "i_factor", "/1"),
        ("Format Compliance", "format_compliance", "/1"),
        ("Media Check", "media_check", "/1"),
    ]
    for label, key, suffix in checks:
        if key in result:
            lines.append(f"  {label}: {result[key]}{suffix}")

    if result.get("failures"):
        lines.append("")
        lines.append("Failures:")
        for f in result["failures"]:
            lines.append(f"  - {f}")

    if result.get("direct_fixes"):
        lines.append("")
        lines.append("Direct fixes (Ellis can apply):")
        for fix in result["direct_fixes"]:
            old = fix.get("old", "")[:50]
            new = fix.get("new", "")[:50]
            if new:
                lines.append(f"  '{old}' → '{new}'")
            else:
                lines.append(f"  Remove: '{old}'")

    if result.get("feedback"):
        lines.append("")
        lines.append(f"Feedback for Maya: {result['feedback']}")

    if result.get("notes"):
        lines.append(f"Notes: {result['notes']}")

    return "\n".join(lines)


# --- CLI ---

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ellis QC — evaluate a draft")
    parser.add_argument("--text", type=str, help="Post text to evaluate (or pipe via stdin)")
    parser.add_argument("--file", type=str, help="Read post text from a file")
    parser.add_argument("--format", type=str, default="", help="Content format name")
    parser.add_argument("--source", type=str, default="", help="Source URL")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        import sys
        text = sys.stdin.read()

    if not text.strip():
        print("No text provided.")
        return

    if args.json:
        result = evaluate(text, args.format, args.source)
        print(json.dumps(result, indent=2))
    else:
        print(evaluate_and_format(text, args.format, args.source))


if __name__ == "__main__":
    main()
