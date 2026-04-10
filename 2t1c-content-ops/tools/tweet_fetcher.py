"""
Tweet fetcher for the GeniusGTX content pipeline.
Extracts tweet text and metadata from X/Twitter URLs using public APIs.
No authentication required.
"""

from __future__ import annotations

import re
import requests


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Extract (username, tweet_id) from a tweet URL."""
    patterns = [
        r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Could not parse tweet URL: {url}")


def fetch_tweet(url: str) -> dict:
    """
    Fetch tweet text and metadata from a public X/Twitter URL.

    Returns dict with keys: text, author, handle, tweet_id, url,
    likes, retweets, replies, views, created_at, quoted_tweet (if any).
    """
    username, tweet_id = parse_tweet_url(url)

    # Primary: FXTwitter API (richest data, includes quoted tweets)
    try:
        return _fetch_fxtwitter(username, tweet_id, url)
    except Exception:
        pass

    # Fallback: Twitter oEmbed API
    try:
        return _fetch_oembed(url, tweet_id)
    except Exception:
        pass

    raise RuntimeError(f"All tweet fetch methods failed for: {url}")


def _fetch_fxtwitter(username: str, tweet_id: str, original_url: str) -> dict:
    """Fetch via FXTwitter API — best data quality."""
    resp = requests.get(
        f"https://api.fxtwitter.com/{username}/status/{tweet_id}",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    tweet = data.get("tweet", {})

    result = {
        "text": tweet.get("text", ""),
        "author": tweet.get("author", {}).get("name", ""),
        "handle": f"@{tweet.get('author', {}).get('screen_name', username)}",
        "tweet_id": tweet_id,
        "url": original_url,
        "likes": tweet.get("likes", 0),
        "retweets": tweet.get("retweets", 0),
        "replies": tweet.get("replies", 0),
        "views": tweet.get("views", 0),
        "created_at": tweet.get("created_at", ""),
    }

    # Extract quoted tweet if present
    quote = tweet.get("quote")
    if quote:
        result["quoted_tweet"] = {
            "text": quote.get("text", ""),
            "author": quote.get("author", {}).get("name", ""),
            "handle": f"@{quote.get('author', {}).get('screen_name', '')}",
            "url": quote.get("url", ""),
        }

    return result


def _fetch_oembed(url: str, tweet_id: str) -> dict:
    """Fallback: Twitter oEmbed API — less data but very reliable."""
    resp = requests.get(
        "https://publish.twitter.com/oembed",
        params={"url": url, "omit_script": "true"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract text from HTML
    html = data.get("html", "")
    # Strip HTML tags to get plain text
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    # Remove the trailing "— Author (@handle) Date" citation
    text = re.split(r"\s*&mdash;|\s*—", text)[0].strip()

    return {
        "text": text,
        "author": data.get("author_name", ""),
        "handle": "",
        "tweet_id": tweet_id,
        "url": url,
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "views": 0,
        "created_at": "",
    }
