"""
Format Definitions — Simplified content types for GeniusGTX.

Three active formats:
  1. Tuki QRT — Character voice, QRTs a source tweet
  2. Long-Form Post — The main format. Single post, 15-40 lines. Angle drives the style.
  3. Thread — Multi-tweet (HIDDEN — not active yet)

The angle (stat-heavy, contrarian, explanatory, commentary) is determined by the idea's
Content Angle field, not by a format label. Maya reads the angle and writes accordingly.

If the source is a tweet, the output always QRTs it (regardless of format).
"""

from __future__ import annotations


FORMAT_REGISTRY: dict[str, dict] = {

    # =========================================================================
    # TUKI QRT — Character voice. Stays separate because it's a distinct style.
    # =========================================================================

    "Tuki QRT": {
        "pipeline_type": "qrt",
        "media_type": "both",  # QRT + GIF
        "hook_style": "built_in",
        "is_thread": False,
        "addendum": """
IMPORTANT: You are writing in TUKI STYLE format. Override normal formatting rules with these:

FORMAT: Summary QRT + GIF (Tuki Style)
- Opener: 🚨 Do you understand what [just happened]..
- ALL lowercase except proper names and acronyms
- Use ".." instead of periods. Always.
- Setup: 1-2 sentences, no bullets, with an editorial twist
- Fact dump: 3-6 lines starting with ">" — each with editorial spin (irony, scale, hypocrisy, absurdity)
- Editorial bridge: 1-2 sentences connecting the dots
- Closer: sharp, quotable, philosophical one-liner with personal "i think..." pivot
- Voice: casual, urgent, editorial
- This is ALWAYS a QRT — the source URL will be attached as the quote tweet

The post should feel like a fast-breaking editorial reaction, not a long-form essay.

ALWAYS end with the signature finisher after the closer:

That's a wrap.

[1-2 sentences describing what @GeniusGTX is — a gallery for the greatest minds in economics, psychology, and history. Match the tone of the piece.]

We are ONE genius away.
""",
    },

    # =========================================================================
    # LONG-FORM POST — The main format. Angle drives the writing direction.
    # =========================================================================

    "Long-Form Post": {
        "pipeline_type": "text",
        "media_type": "gif",
        "hook_style": "maya",
        "is_thread": False,
        "addendum": """
FORMAT: Long-Form Post
LENGTH: 15-40 lines. Single post, not a thread.
STRUCTURE: Hook → Body → Editorial bridge → CTA closer.

WRITING DIRECTION:
Let the idea's angle and source material guide the structure:
- If the angle is data-heavy: lead with the most striking number, build with context, connect to mechanism.
- If the angle is contrarian: state the mainstream view fairly, then dismantle it with evidence.
- If the angle is explanatory: break down what's actually happening, use analogies, make the abstract concrete.
- If the angle is commentary/reaction: give your read on the event, connect to a bigger pattern.
- If the angle draws from multiple sources: weave them together, the value is the connection.

If the source is a YouTube video, pull the strongest quote and weave it into the text. Do not transcribe the video. Do not say "watch this" or reference "the video below."

CONTENT RULES:
- Each paragraph delivers ONE specific claim, number, or insight.
- Max 2 sentences per paragraph. One idea per paragraph.
- No em dashes. Split into new sentences.
- Include specific names, dates, and data points. No vague claims.
- No generic Twitter engagement patterns. NEVER write "Let that sink in", "And nobody is talking about it", "Here's the thing", "Think about that for a second."
- Each stat or claim must connect to a mechanism or incentive — not just shock value.

CTA CLOSER (EXACT — never deviate):
End with "That's a wrap." (own line) → 1-2 sentences describing @GeniusGTX (own paragraph) → "We are ONE genius away." (always the last line). NEVER use "Follow @GeniusGTX for more." — that is banned.

Follow the writing guidelines for voice, rhythm, and structure.
""",
    },

    # =========================================================================
    # THREAD — Multi-tweet format. HIDDEN — not active in pipeline yet.
    # =========================================================================

    # "Thread": {
    #     "pipeline_type": "text",
    #     "media_type": "gif",
    #     "hook_style": "maya",
    #     "is_thread": True,
    #     "addendum": """
    # FORMAT: Thread
    # LENGTH: 4-10 tweets. Each tweet 1-5 lines. Separate tweets with "---".
    # STRUCTURE: Hook tweet → Body tweets (setup → build → turn) → Closer tweet with CTA.
    # CONTENT: Each tweet is one complete thought. Do not use "1/" or "Thread:" or any numbering.
    # CTA: Final tweet ends with "That's a wrap." → @GeniusGTX description → "We are ONE genius away."
    #
    # Follow the writing guidelines for voice, rhythm, and structure.
    # """,
    # },
}


# --- Format mapping ---
# Old format names map to the new simplified formats.
# This ensures existing ideas with old format names still work.

FORMAT_ALIASES = {
    # QRT formats → Tuki QRT (character voice stays)
    "Bark QRT": "Tuki QRT",
    # All long-form single posts → Long-Form Post
    "Commentary Post": "Long-Form Post",
    "Stat Bomb": "Long-Form Post",
    "Explainer": "Long-Form Post",
    "Contrarian Take": "Long-Form Post",
    "Multi-Source Explainer": "Long-Form Post",
    "Video Clip Post": "Long-Form Post",
    "Clip Commentary": "Long-Form Post",
    # Threads → Long-Form Post (thread disabled for now)
    "Thread": "Long-Form Post",
    "Clip Thread": "Long-Form Post",
}


# --- Lookup helpers ---

def get_format(name: str) -> dict | None:
    """Get a format definition by name. Resolves aliases to simplified formats."""
    # Check direct match first
    for key, fmt in FORMAT_REGISTRY.items():
        if key.lower() == name.lower():
            return {**fmt, "name": key}
    # Check aliases
    resolved = FORMAT_ALIASES.get(name)
    if resolved:
        for key, fmt in FORMAT_REGISTRY.items():
            if key.lower() == resolved.lower():
                return {**fmt, "name": key, "original_format": name}
    return None


def get_formats_by_pipeline(pipeline_type: str) -> list[dict]:
    """Get all formats for a given pipeline type (qrt, text, clip)."""
    return [
        {**fmt, "name": key}
        for key, fmt in FORMAT_REGISTRY.items()
        if fmt["pipeline_type"] == pipeline_type
    ]


def list_all_formats() -> list[str]:
    """List all registered format names (active only)."""
    return list(FORMAT_REGISTRY.keys())


def get_media_type(format_name: str) -> str:
    """Get the media type for a format. Returns 'gif' as default."""
    fmt = get_format(format_name)
    return fmt["media_type"] if fmt else "gif"
