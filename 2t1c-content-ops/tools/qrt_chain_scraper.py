"""
QRT Chain Scraper — Finds the best recent tweet from @GeniusGTX to QRT.

This tool is designed to be called during Claude Code cowork sessions.
It uses Chrome MCP (via Claude in Chrome extension) to scrape the profile
and match tweets to a given post topic.

For the automated pipeline, the matching logic can run standalone
once tweet data is provided (from any source).

Usage:
    # During cowork session (Chrome MCP provides the raw data):
    from tools.qrt_chain_scraper import find_best_qrt_target

    tweets = [...]  # scraped from Chrome MCP
    match = find_best_qrt_target(
        tweets=tweets,
        post_topic="psychology of decision-making under uncertainty",
        post_tags=["Psychology", "Science"],
    )

    # Returns:
    # {
    #     "url": "https://x.com/GeniusGTX/status/...",
    #     "text": "...",
    #     "relevance_score": 0.85,
    #     "reason": "Topic match: psychology + human behavior",
    #     "bridge_line": "Speaking of how our minds trick us →",
    #     "performance": "high"  # or "low"
    # }
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta


# --- Topic keyword maps for matching ---

TOPIC_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "machine learning", "gpt", "openai", "claude", "llm", "neural", "automation", "robot", "deepfake", "algorithm"],
    "Finance": ["finance", "stock", "market", "billion", "trillion", "revenue", "valuation", "investment", "economy", "gdp", "inflation", "fed", "bank", "crypto", "bitcoin"],
    "Geopolitics": ["war", "military", "sanctions", "nato", "china", "russia", "iran", "nuclear", "treaty", "diplomacy", "border", "conflict", "invasion"],
    "Business": ["business", "ceo", "company", "startup", "acquisition", "revenue", "profit", "corporation", "founder", "entrepreneur", "merger"],
    "Psychology": ["psychology", "brain", "mind", "cognitive", "behavior", "decision", "bias", "emotion", "mental", "habit", "perception", "consciousness", "thinking"],
    "Philosophy": ["philosophy", "meaning", "existence", "moral", "ethics", "truth", "reality", "wisdom", "stoic", "nietzsche", "plato", "socrates"],
    "Marketing": ["marketing", "brand", "audience", "growth", "viral", "engagement", "content", "social media", "advertising", "campaign"],
    "Tech": ["tech", "software", "hardware", "app", "internet", "data", "cloud", "cyber", "silicon valley", "computing", "quantum"],
    "Health": ["health", "medical", "disease", "drug", "pharma", "cancer", "vaccine", "longevity", "fitness", "nutrition", "sleep"],
    "Culture": ["culture", "society", "religion", "race", "gender", "identity", "tradition", "music", "art", "film", "media"],
    "Science": ["science", "research", "study", "experiment", "physics", "chemistry", "biology", "space", "nasa", "discovery"],
    "History": ["history", "ancient", "war", "empire", "century", "civilization", "revolution", "king", "dynasty", "colonial"],
}


def _compute_topic_overlap(tweet_text: str, post_topic: str, post_tags: list[str]) -> tuple[float, str]:
    """
    Score how relevant a tweet is to the post topic.
    Returns (score 0-1, reason string).
    """
    tweet_lower = tweet_text.lower()
    topic_lower = post_topic.lower()

    score = 0.0
    reasons = []

    # Direct keyword overlap between post topic and tweet text
    topic_words = set(topic_lower.split())
    tweet_words = set(tweet_lower.split())
    overlap = topic_words & tweet_words
    # Filter out very common words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "but", "not", "this", "that", "it", "with", "from", "by", "as", "be", "has", "had", "have", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "just", "about", "how", "why", "what", "when", "where", "who", "which"}
    meaningful_overlap = overlap - stop_words
    if meaningful_overlap:
        score += min(len(meaningful_overlap) * 0.15, 0.45)
        reasons.append(f"keyword overlap: {', '.join(list(meaningful_overlap)[:4])}")

    # Tag-based matching
    for tag in post_tags:
        keywords = TOPIC_KEYWORDS.get(tag, [])
        matches = [kw for kw in keywords if kw in tweet_lower]
        if matches:
            score += 0.2
            reasons.append(f"tag match: {tag}")
            break  # one tag match is enough

    # Bonus for thematic similarity patterns
    thematic_pairs = [
        (["brain", "mind", "think", "cognitive"], ["psychology", "decision", "behavior"]),
        (["money", "billion", "market", "economy"], ["finance", "business", "invest"]),
        (["war", "military", "conflict"], ["geopolitics", "power", "empire"]),
        (["history", "ancient", "century", "empire"], ["civilization", "culture", "legacy"]),
        (["ai", "robot", "algorithm", "automation"], ["tech", "future", "computing"]),
    ]
    for group_a, group_b in thematic_pairs:
        tweet_has_a = any(w in tweet_lower for w in group_a)
        topic_has_b = any(w in topic_lower for w in group_b)
        tweet_has_b = any(w in tweet_lower for w in group_b)
        topic_has_a = any(w in topic_lower for w in group_a)
        if (tweet_has_a and topic_has_b) or (tweet_has_b and topic_has_a):
            score += 0.15
            reasons.append("thematic connection")
            break

    score = min(score, 1.0)
    reason = "; ".join(reasons) if reasons else "no strong connection found"
    return score, reason


def _classify_performance(views: int, likes: int, reposts: int) -> str:
    """Classify a tweet as high, medium, or low performer."""
    if views >= 100_000 or likes >= 500:
        return "high"
    elif views >= 10_000 or likes >= 100:
        return "medium"
    else:
        return "low"


def _is_within_window(tweet_datetime: str, hours: int = 72) -> bool:
    """Check if a tweet is within the recency window."""
    if not tweet_datetime:
        return False
    try:
        tweet_dt = datetime.fromisoformat(tweet_datetime.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return tweet_dt >= cutoff
    except (ValueError, TypeError):
        return False


BRIDGE_LINE_PROMPT = """You are writing a 1-2 sentence bridge line for a post on X/Twitter.

This bridge line sits at the very end of a long-form post, right ABOVE a quote-retweet (QRT). Its job is to make the reader naturally flow from the post they just read into the quoted tweet below.

THE POST (what the reader just finished reading):
{post_summary}

THE QRT (the tweet that will appear below):
{qrt_text}

RULES:
- 1-2 sentences max. Keep it short.
- Write in the same casual, editorial voice as the post.
- All lowercase except proper names/acronyms.
- The bridge should feel like a natural extension, not a sales pitch.
- Don't say "check this out" or "read this." Instead, create a thematic connection.
- End with → or ... to pull the eye downward.
- Think of it as: "after reading the main post, this line makes the QRT feel like the obvious next thing to read."

GOOD EXAMPLES:
- "speaking of how power really works behind closed doors →"
- "this is exactly what i was talking about.. the pattern keeps repeating →"
- "and if you think that's wild.. look at what just happened →"
- "the psychology behind this runs deeper than most people realize →"
- "this connects to something i've been thinking about all week.."

BAD EXAMPLES (don't do these):
- "Check out this related post!" (too promotional)
- "Here's another great thread on this topic →" (too meta)
- "RT if you agree" (engagement bait)

Write ONLY the bridge line. Nothing else."""


def build_bridge_line_prompt(post_summary: str, qrt_text: str) -> str:
    """
    Build the prompt for Claude to generate a bridge line.

    Args:
        post_summary: A 1-2 sentence summary of what the post is about
        qrt_text: The text of the tweet being QRT'd

    Returns:
        A formatted prompt string ready to send to Claude.
    """
    return BRIDGE_LINE_PROMPT.format(
        post_summary=post_summary,
        qrt_text=qrt_text,
    )


def _generate_bridge_line_fallback(tweet_text: str, post_topic: str, reason: str) -> str:
    """
    Fallback template-based bridge line when LLM is not available.
    For production, use build_bridge_line_prompt() with Claude instead.
    """
    templates = [
        "this connects to something i shared recently →",
        "speaking of this →",
        "the pattern runs deeper than you think →",
        "and if you want to see this play out in real time →",
        "more on this below..",
    ]
    idx = hash(tweet_text[:50]) % len(templates)
    return templates[idx]


def find_best_qrt_target(
    tweets: list[dict],
    post_topic: str,
    post_tags: list[str] | None = None,
    recency_hours: int = 72,
    include_reposts: bool = True,
    include_pinned: bool = False,
) -> dict | None:
    """
    Find the best tweet to QRT from a list of scraped profile tweets.

    Args:
        tweets: List of tweet dicts with keys:
            - t (str): tweet text
            - d (str): ISO datetime
            - u (str): tweet URL
            - c (str): context ("Pinned", "You reposted", or "")
            - v (int): view count
            - l (int): like count
            - rp (int): repost count
        post_topic: What the new post is about
        post_tags: Topic tags from the post (e.g., ["Psychology", "Science"])
        recency_hours: How far back to look (default 72 hours)
        include_reposts: Whether to consider reposted tweets
        include_pinned: Whether to consider pinned tweets

    Returns:
        Dict with url, text, relevance_score, reason, bridge_line, performance
        or None if no suitable match found.
    """
    post_tags = post_tags or []
    candidates = []

    for tweet in tweets:
        text = tweet.get("t", "")
        dt = tweet.get("d", "")
        url = tweet.get("u", "")
        context = tweet.get("c", "")
        views = tweet.get("v", 0)
        likes = tweet.get("l", 0)
        reposts = tweet.get("rp", 0)

        # Filter by context
        if not include_pinned and "Pinned" in context:
            continue
        if not include_reposts and "reposted" in context.lower():
            continue

        # Filter by recency
        if not _is_within_window(dt, recency_hours):
            continue

        # Skip if no text or URL
        if not text or not url:
            continue

        # Score relevance
        relevance, reason = _compute_topic_overlap(text, post_topic, post_tags)
        performance = _classify_performance(views, likes, reposts)

        # Bonus for performance extremes (high performer = boost, low = second life)
        perf_bonus = 0.1 if performance in ("high", "low") else 0.0

        candidates.append({
            "url": url,
            "text": text,
            "datetime": dt,
            "context": context,
            "relevance_score": round(relevance + perf_bonus, 2),
            "relevance_reason": reason,
            "bridge_line": _generate_bridge_line_fallback(text, post_topic, reason),
            "performance": performance,
            "views": views,
            "likes": likes,
            "reposts": reposts,
        })

    if not candidates:
        return None

    # Sort by relevance score (descending), then by views (descending)
    candidates.sort(key=lambda c: (c["relevance_score"], c["views"]), reverse=True)
    return candidates[0]


def find_all_qrt_candidates(
    tweets: list[dict],
    post_topic: str,
    post_tags: list[str] | None = None,
    recency_hours: int = 72,
) -> list[dict]:
    """
    Return all viable QRT candidates ranked by relevance.
    Useful for manual review or when the top match isn't great.
    """
    post_tags = post_tags or []
    candidates = []

    for tweet in tweets:
        text = tweet.get("t", "")
        dt = tweet.get("d", "")
        url = tweet.get("u", "")
        context = tweet.get("c", "")
        views = tweet.get("v", 0)
        likes = tweet.get("l", 0)
        reposts = tweet.get("rp", 0)

        if "Pinned" in context:
            continue
        if not text or not url:
            continue
        if not _is_within_window(dt, recency_hours):
            continue

        relevance, reason = _compute_topic_overlap(text, post_topic, post_tags)
        performance = _classify_performance(views, likes, reposts)

        candidates.append({
            "url": url,
            "text": text[:150],
            "relevance_score": round(relevance, 2),
            "reason": reason,
            "performance": performance,
            "views": views,
        })

    candidates.sort(key=lambda c: (c["relevance_score"], c["views"]), reverse=True)
    return candidates


# --- Chrome MCP Integration ---
# The JavaScript snippet below should be executed via Claude in Chrome MCP
# to scrape the profile. The output feeds directly into find_best_qrt_target().

SCRAPE_PROFILE_JS = """
const articles = document.querySelectorAll('article[data-testid="tweet"]');
const r = [];
articles.forEach(a => {
  const t = a.querySelector('[data-testid="tweetText"]');
  const tm = a.querySelector('time');
  const sc = a.querySelector('[data-testid="socialContext"]');
  const lnk = tm ? tm.closest('a') : null;
  const grp = a.querySelector('[role="group"]');
  const gl = grp ? grp.getAttribute('aria-label') : '';
  const vm = gl.match(/(\\d+)\\s*views/);
  const lm = gl.match(/(\\d+)\\s*likes/);
  const rpm = gl.match(/(\\d+)\\s*reposts/);
  r.push({
    t: t ? t.innerText.substring(0, 300) : '',
    d: tm ? tm.getAttribute('datetime') : '',
    u: lnk ? lnk.href : '',
    c: sc ? sc.innerText : '',
    v: vm ? parseInt(vm[1]) : 0,
    l: lm ? parseInt(lm[1]) : 0,
    rp: rpm ? parseInt(rpm[1]) : 0
  });
});
JSON.stringify(r)
"""


if __name__ == "__main__":
    # Demo with sample data
    sample_tweets = [
        {
            "t": "To understand why modern society feels so broken, you need to look at the underlying laws that drive human behavior",
            "d": "2025-12-31T13:56:05.000Z",
            "u": "https://x.com/GeniusGTX/status/2006363733501907026",
            "c": "You reposted",
            "v": 68059, "l": 792, "rp": 217
        },
        {
            "t": "BREAKING: A jury just ruled that Instagram and YouTube deliberately addicted your kids.",
            "d": "2026-03-28T15:00:23.000Z",
            "u": "https://x.com/SurmountInvest/status/2037907661388390419",
            "c": "You reposted",
            "v": 2531, "l": 21, "rp": 14
        },
    ]

    result = find_best_qrt_target(
        tweets=sample_tweets,
        post_topic="How social media algorithms exploit human psychology",
        post_tags=["Psychology", "Tech"],
        recency_hours=720,  # wider window for demo
    )

    if result:
        print(f"Best QRT match:")
        print(f"  URL: {result['url']}")
        print(f"  Text: {result['text'][:100]}...")
        print(f"  Score: {result['relevance_score']}")
        print(f"  Reason: {result['relevance_reason']}")
        print(f"  Bridge: {result['bridge_line']}")
        print(f"  Performance: {result['performance']}")
    else:
        print("No matching tweets found within the recency window.")
