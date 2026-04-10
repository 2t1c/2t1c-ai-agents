"""
Media Rules — Centralized media priority logic for the GeniusGTX content pipeline.

Every long-form post must have at least one media element.

Priority 1 — QRT: If the idea came from Twitter/X, attach the source post as a QRT.
Priority 2 — GIF: If no QRT is available, attach a GIF from the local reaction folder.
Priority 3 — Both QRT + GIF: For breaking news or Tuki format, use both.

Text-only exceptions (no media required):
- Format 2: "Let Me Get This Straight" — text only by design
- Format 10: "Long-Form Text Only" — text only by design
- Format 11: "X Article" — uses a thumbnail instead
"""

from __future__ import annotations

# Formats that are text-only by design — no media required
TEXT_ONLY_FORMATS = {
    "Let Me Get This Straight",
    "Long-Form Text Only",
    "X Article",
}

# Formats/urgencies that require BOTH QRT + GIF
BOTH_QRT_AND_GIF = {
    "formats": {
        "Tuki QRT",
        "Summary QRT + GIF (Tuki Style)",
    },
    "urgencies": {
        "🔴 Breaking",
    },
}


def determine_media_needs(
    assigned_formats: list[str],
    urgency: str = "",
    source_url: str = "",
    qrt_source_url: str = "",
) -> dict:
    """
    Determine what media a post needs based on format, urgency, and source.

    Returns:
        {
            "needs_media": bool,
            "needs_qrt": bool,
            "needs_gif": bool,
            "qrt_url": str | None,
            "reason": str,
        }
    """
    # Check if text-only format
    for fmt in assigned_formats:
        if fmt in TEXT_ONLY_FORMATS:
            return {
                "needs_media": False,
                "needs_qrt": False,
                "needs_gif": False,
                "qrt_url": None,
                "reason": f"Text-only format: {fmt}",
            }

    # Determine QRT URL (prefer qrt_source_url, fall back to source_url if it's a tweet)
    qrt_url = qrt_source_url or ""
    if not qrt_url and source_url and ("x.com" in source_url or "twitter.com" in source_url):
        qrt_url = source_url

    has_qrt = bool(qrt_url)

    # Check if this format/urgency requires BOTH QRT + GIF
    needs_both = False
    for fmt in assigned_formats:
        if fmt in BOTH_QRT_AND_GIF["formats"]:
            needs_both = True
            break
    if urgency in BOTH_QRT_AND_GIF["urgencies"]:
        needs_both = True

    if needs_both:
        return {
            "needs_media": True,
            "needs_qrt": has_qrt,
            "needs_gif": True,
            "qrt_url": qrt_url or None,
            "reason": "Breaking/Tuki format — both QRT + GIF required",
        }

    # Priority 1: QRT if source is Twitter
    if has_qrt:
        return {
            "needs_media": True,
            "needs_qrt": True,
            "needs_gif": False,
            "qrt_url": qrt_url,
            "reason": "Twitter source — QRT as primary media",
        }

    # Priority 2: GIF if no QRT available
    return {
        "needs_media": True,
        "needs_qrt": False,
        "needs_gif": True,
        "qrt_url": None,
        "reason": "No QRT available — GIF required",
    }


def format_gif_brief(topic: str, mood: str = "", closer_tone: str = "") -> str:
    """
    Generate a structured GIF brief for manual or future automated selection.

    This is output when a GIF is needed but must be selected from the local folder.
    """
    return f"""GIF BRIEF
Topic: {topic}
Mood: {mood or "match the closer tone"}
Closer tone: {closer_tone or "editorial / dry irony"}
Local folder: skills/writing-system/Reaction GIF for twitter content/
Action: Select a reaction GIF that matches the mood. Any .mp4 or .jpg from the folder works."""
