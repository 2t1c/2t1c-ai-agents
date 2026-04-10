"""
Media Attacher — Monitors Typefully drafts tagged 'Needs Media',
picks a random reaction GIF from the local folder, uploads it,
attaches it to the draft, and changes the tag to 'Ready for Review'.

Usage:
    python -m pipeline.media_attacher --once       # process all 'Needs Media' drafts once
    python -m pipeline.media_attacher --poll        # continuously poll
    python -m pipeline.media_attacher --draft-id N  # process a specific draft
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.typefully_client import pick_random_gif

# MCP tools are used when running through Claude Code.
# For standalone execution, these functions wrap the Typefully REST API.
import requests
import os
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env", override=True)

API_BASE = "https://api.typefully.com/v2"
API_KEY = os.getenv("TYPEFULLY_API_KEY", "")
SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))

TAG_NEEDS_MEDIA = "needs-media"
TAG_QC_REVIEW = "qc-review"
TAG_READY_FOR_REVIEW = "ready-for-review"
POLL_INTERVAL_SECONDS = 120  # 2 minutes


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def list_drafts_needing_media() -> list[dict]:
    """Fetch all drafts tagged 'needs-media'."""
    resp = requests.get(
        f"{API_BASE}/social-sets/{SOCIAL_SET_ID}/drafts",
        headers=_headers(),
        params={
            "status": "draft",
            "tag": TAG_NEEDS_MEDIA,
            "limit": 50,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def upload_media_file(file_path: Path) -> str:
    """Upload a media file and return the media_id."""
    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in ".-_()" else "_" for c in file_path.name)
    if not safe_name:
        safe_name = f"reaction{file_path.suffix}"

    # Get presigned URL
    resp = requests.post(
        f"{API_BASE}/social-sets/{SOCIAL_SET_ID}/media-uploads",
        headers=_headers(),
        json={"file_name": safe_name},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # Upload raw bytes
    put_resp = requests.put(data["upload_url"], data=file_path.read_bytes())
    put_resp.raise_for_status()

    return data["media_id"]


def update_draft_media_and_tag(draft_id: int, media_id: str, existing_post_text: str, existing_qrt_url: str | None = None) -> dict:
    """Attach media to a draft and change tag from 'Needs Media' to 'Ready for Review'."""
    post = {"text": existing_post_text, "media_ids": [media_id]}
    if existing_qrt_url:
        post["quote_post_url"] = existing_qrt_url

    resp = requests.patch(
        f"{API_BASE}/social-sets/{SOCIAL_SET_ID}/drafts/{draft_id}",
        headers=_headers(),
        json={
            "platforms": {
                "x": {
                    "enabled": True,
                    "posts": [post],
                }
            },
            "tags": [TAG_READY_FOR_REVIEW],
        },
    )
    resp.raise_for_status()
    return resp.json()


def process_draft(draft: dict) -> bool:
    """Process a single draft: pick GIF, upload, attach, re-tag."""
    draft_id = draft["id"]
    title = draft.get("draft_title") or draft.get("preview", "")[:60]
    print(f"\n--- Processing draft {draft_id}: {title}")

    # Extract existing post text and QRT URL
    x_platform = draft.get("platforms", {}).get("x", {})
    posts = x_platform.get("posts", [])
    if not posts:
        print(f"    SKIP: No X posts found in draft")
        return False

    post_text = posts[0].get("text", "")
    qrt_url = posts[0].get("quote_post_url")

    # Pick a random GIF
    gif_path = pick_random_gif()
    if not gif_path:
        print("    ERROR: No GIF files found in reaction folder")
        return False
    print(f"    GIF: {gif_path.name[:50]}")

    # Upload
    try:
        media_id = upload_media_file(gif_path)
        print(f"    Uploaded: {media_id}")
    except Exception as e:
        print(f"    ERROR uploading: {e}")
        return False

    # Attach media and re-tag
    try:
        update_draft_media_and_tag(draft_id, media_id, post_text, qrt_url)
        print(f"    Tag: {TAG_NEEDS_MEDIA} → {TAG_QC_REVIEW} (routed to Ellis QC)")
    except Exception as e:
        print(f"    ERROR updating draft: {e}")
        return False

    return True


def process_all_needs_media() -> int:
    """Fetch all 'needs-media' drafts, process them, return count of successes."""
    drafts = list_drafts_needing_media()
    if not drafts:
        print("No drafts tagged 'needs-media'.")
        return 0
    print(f"Found {len(drafts)} draft(s) needing media")
    success = sum(1 for d in drafts if process_draft(d))
    print(f"Media attached: {success}/{len(drafts)}")
    return success


def run_once(draft_id: int | None = None):
    """Process one or all 'Needs Media' drafts."""
    if draft_id:
        # Fetch specific draft
        resp = requests.get(
            f"{API_BASE}/drafts/{draft_id}/",
            headers=_headers(),
            params={"social-set-id": SOCIAL_SET_ID},
        )
        resp.raise_for_status()
        drafts = [resp.json()]
    else:
        drafts = list_drafts_needing_media()
        if not drafts:
            print("No drafts tagged 'Needs Media'.")
            return
        print(f"Found {len(drafts)} draft(s) needing media")

    results = [process_draft(d) for d in drafts]
    success = sum(results)
    print(f"\n=== Done: {success}/{len(results)} drafts processed ===")


def run_poll():
    """Continuously poll for drafts needing media."""
    print(f"Media Attacher — polling every {POLL_INTERVAL_SECONDS}s")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            drafts = list_drafts_needing_media()
            if drafts:
                print(f"[POLL] Found {len(drafts)} draft(s) needing media")
                for d in drafts:
                    process_draft(d)
            else:
                print("[POLL] No drafts need media. Sleeping...")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Media Attacher — attach GIFs to Typefully drafts")
    parser.add_argument("--once", action="store_true", help="Process all 'Needs Media' drafts once")
    parser.add_argument("--poll", action="store_true", help="Continuously poll")
    parser.add_argument("--draft-id", type=int, help="Process a specific draft by ID")
    args = parser.parse_args()

    if args.poll:
        run_poll()
    elif args.once or args.draft_id:
        run_once(draft_id=args.draft_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
