"""
Tuki Pipeline — Polls Notion for 'Triggered' ideas with 'Tuki QRT' format,
generates Tuki-style posts via Maya, and creates Typefully drafts.

Usage:
    python -m pipeline.tuki_pipeline --poll          # continuous polling
    python -m pipeline.tuki_pipeline --once --idea-id <notion-page-id>  # single idea
    python -m pipeline.tuki_pipeline --url <tweet-url>  # process a tweet URL directly
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to path so we can import tools and agents
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.notion_client import get_triggered_ideas, update_idea_status, save_typefully_draft_id, get_idea_by_id
from tools.typefully_client import create_draft, upload_media, pick_random_gif, add_tag_to_draft
from tools.tweet_fetcher import fetch_tweet
from pipeline.media_rules import determine_media_needs

# Maya agent for writing
from agents.maya.agent import write_thread


TUKI_SYSTEM_ADDENDUM = """
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
"""

POLL_INTERVAL_SECONDS = 300  # 5 minutes


def enrich_idea_with_tweet(idea: dict) -> dict:
    """
    If the idea has a source_url pointing to a tweet, fetch the tweet text
    and any quoted tweet to provide full context for Maya.

    QRT TRACING: If the source tweet is itself a QRT (e.g., a Tuki post or
    another QRTer), we trace back to the ORIGINAL post being quoted and use
    that as our QRT target. We never want to QRT the QRTer — we QRT the original.
    """
    source_url = idea.get("source_url", "")
    if not source_url or "x.com" not in source_url and "twitter.com" not in source_url:
        return idea

    try:
        tweet_data = fetch_tweet(source_url)
        context_parts = []
        context_parts.append(f"SOURCE TWEET by {tweet_data['handle']} ({tweet_data['author']}):")
        context_parts.append(f'"{tweet_data["text"]}"')

        if tweet_data.get("views"):
            context_parts.append(f"Engagement: {tweet_data['views']:,} views, {tweet_data['likes']:,} likes, {tweet_data['retweets']:,} RTs")

        idea = dict(idea)  # don't mutate original

        if tweet_data.get("quoted_tweet"):
            qt = tweet_data["quoted_tweet"]
            context_parts.append(f"\nORIGINAL QUOTED TWEET by {qt['handle']} ({qt['author']}):")
            context_parts.append(f'"{qt["text"]}"')

            # TRACE BACK: The source tweet is a QRT. Use the ORIGINAL post as our
            # QRT target so we quote the original author, not the QRTer.
            if qt.get("url"):
                idea["qrt_source_url"] = qt["url"]
                print(f"    QRT traced back to original: {qt['url']}")
                print(f"    (Skipping QRTer: {source_url})")

        idea["tweet_context"] = "\n".join(context_parts)
        print(f"    Fetched tweet: {tweet_data['text'][:80]}...")
    except Exception as e:
        print(f"    WARN: Could not fetch tweet ({e})")

    return idea


def build_tuki_prompt(idea: dict) -> str:
    """Build the prompt for Maya to write a Tuki-style post."""
    parts = [f"TOPIC: {idea['idea']}"]

    if idea.get("content_angle"):
        parts.append(f"ANGLE: {idea['content_angle']}")

    if idea.get("tweet_context"):
        parts.append(idea["tweet_context"])

    qrt_target = idea.get("qrt_source_url") or idea.get("source_url")
    if qrt_target:
        parts.append(f"QRT TARGET URL: {qrt_target}")

    if idea.get("source_account"):
        parts.append(f"SOURCE ACCOUNT: {idea['source_account']}")

    if idea.get("notes"):
        parts.append(f"NOTES: {idea['notes']}")

    parts.append(TUKI_SYSTEM_ADDENDUM)
    parts.append("Write the Tuki-style post now. One continuous post, not a thread.")

    return "\n\n".join(parts)


def process_idea(idea: dict) -> dict | None:
    """
    Process a single idea through the Tuki pipeline:
    1. Enrich with tweet context + trace QRT to original source
    2. Determine media needs (QRT, GIF, or both)
    3. Mark as Drafting in Notion
    4. Generate Tuki post via Maya
    5. Upload a reaction GIF
    6. Create Typefully draft with QRT URL + media
    7. Save draft ID back to Notion
    8. Mark as Ready for Review
    """
    idea_title = idea["idea"]
    idea_id = idea.get("id", "direct-url")
    source_url = idea.get("source_url")

    print(f"\n--- Processing: {idea_title}")
    print(f"    Source: {source_url or 'none'}")

    # Step 1: Enrich with tweet context (must happen before media needs
    # so QRT tracing can resolve the original post URL)
    idea = enrich_idea_with_tweet(idea)

    # Step 2: Determine media needs (now has qrt_source_url if traced)
    assigned_formats = idea.get("assigned_formats", ["Tuki QRT"])
    media_needs = determine_media_needs(
        assigned_formats=assigned_formats,
        urgency=idea.get("urgency", ""),
        source_url=source_url or "",
        qrt_source_url=idea.get("qrt_source_url", ""),
    )
    print(f"    Media: {media_needs['reason']}")

    # Step 3: Mark as Drafting (skip if no Notion ID)
    if idea_id != "direct-url":
        update_idea_status(idea_id, "Drafting")
        print("    Status → Drafting")

    # Step 4: Generate Tuki post
    prompt = build_tuki_prompt(idea)
    print("    Generating Tuki post via Maya...")
    post_text = write_thread(hook="", raw_facts="", topic=prompt)

    if not post_text or len(post_text.strip()) < 50:
        print(f"    ERROR: Maya returned insufficient content ({len(post_text)} chars). Skipping.")
        if idea_id != "direct-url":
            update_idea_status(idea_id, "Triggered")  # revert
        return None

    print(f"    Generated {len(post_text)} chars")

    # Step 5: Upload GIF if needed
    media_ids = []
    if media_needs["needs_gif"]:
        gif_path = pick_random_gif()
        if gif_path:
            print(f"    Uploading GIF: {gif_path.name[:50]}...")
            try:
                media_id = upload_media(gif_path)
                media_ids.append(media_id)
                print(f"    GIF uploaded: {media_id}")
            except Exception as e:
                print(f"    WARN: GIF upload failed ({e}), continuing without media")

    # Step 6: Create Typefully draft (with QRT if needed)
    # Prefer traced original post URL > media_needs resolved URL > source_url
    qrt_url = (idea.get("qrt_source_url") or media_needs.get("qrt_url") or source_url) if media_needs["needs_qrt"] else None
    print("    Creating Typefully draft...")
    draft = create_draft(
        post_text=post_text,
        qrt_url=qrt_url,
        media_ids=media_ids or None,
    )
    draft_id = str(draft.get("id", ""))
    print(f"    Draft created: {draft_id}")

    # Tag draft based on media status
    needs_media = media_needs["needs_gif"] and not media_ids
    if draft_id:
        try:
            if needs_media:
                add_tag_to_draft(draft_id, "needs-media")
                print("    Tagged: needs-media (GIF will be attached by media_attacher)")
            else:
                add_tag_to_draft(draft_id, "ready-for-review")
                print("    Tagged: ready-for-review")
        except Exception as e:
            print(f"    WARN: Could not tag draft ({e})")

    # Step 7: Save draft ID to Notion
    if draft_id and idea_id != "direct-url":
        save_typefully_draft_id(idea_id, draft_id)
        print("    Saved draft ID to Notion")

    # Step 8: Mark as Ready for Review
    if idea_id != "direct-url":
        update_idea_status(idea_id, "Ready for Review")
        print("    Status → Ready for Review")

    return {
        "idea_id": idea_id,
        "idea": idea_title,
        "draft_id": draft_id,
        "post_length": len(post_text),
        "post_text": post_text,
        "needs_media": needs_media,
    }


def run_from_url(tweet_url: str):
    """Process a tweet URL directly — no Notion involved."""
    print(f"Fetching tweet: {tweet_url}")
    try:
        tweet_data = fetch_tweet(tweet_url)
    except Exception as e:
        print(f"ERROR: Could not fetch tweet: {e}")
        return

    idea = {
        "id": "direct-url",
        "idea": tweet_data["text"][:200],
        "source_url": tweet_url,
        "source_account": tweet_data.get("handle", ""),
        "content_angle": "",
        "notes": "",
        "tweet_context": "",  # will be enriched in process_idea
    }

    result = process_idea(idea)
    if result:
        print(f"\n=== Done: draft {result['draft_id']} ({result['post_length']} chars) ===")


def run_once(idea_id: str | None = None):
    """Process a single idea or all triggered Tuki ideas once."""
    if idea_id:
        idea = get_idea_by_id(idea_id)
        if not idea:
            print(f"Idea {idea_id} not found.")
            return
        results = [process_idea(idea)]
    else:
        ideas = get_triggered_ideas(assigned_format="Tuki QRT")
        if not ideas:
            print("No triggered Tuki QRT ideas found.")
            return
        print(f"Found {len(ideas)} triggered Tuki QRT idea(s)")
        results = [process_idea(idea) for idea in ideas]

    successful = [r for r in results if r is not None]
    print(f"\n=== Done: {len(successful)}/{len(results)} ideas processed ===")
    for r in successful:
        print(f"  - {r['idea'][:60]} → draft {r['draft_id']} ({r['post_length']} chars)")


def run_poll():
    """Continuously poll for triggered Tuki ideas."""
    print(f"Tuki Pipeline — polling every {POLL_INTERVAL_SECONDS}s")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            ideas = get_triggered_ideas(assigned_format="Tuki QRT")
            if ideas:
                print(f"[POLL] Found {len(ideas)} triggered Tuki QRT idea(s)")
                for idea in ideas:
                    process_idea(idea)
            else:
                print("[POLL] No triggered Tuki QRT ideas. Sleeping...")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nPipeline stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Tuki Pipeline — GeniusGTX content automation")
    parser.add_argument("--poll", action="store_true", help="Continuously poll for triggered ideas")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--idea-id", type=str, help="Process a specific idea by Notion page ID")
    parser.add_argument("--url", type=str, help="Process a tweet URL directly (no Notion)")
    args = parser.parse_args()

    if args.url:
        run_from_url(args.url)
    elif args.poll:
        run_poll()
    elif args.once:
        run_once(idea_id=args.idea_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
