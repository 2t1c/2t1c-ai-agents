"""
Typefully client for the GeniusGTX content pipeline.
Uses the Typefully v2 REST API with Bearer auth to create and manage drafts.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

API_BASE = "https://api.typefully.com/v2"
API_KEY = os.getenv("TYPEFULLY_API_KEY", "")
DEFAULT_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))

GIF_FOLDER = PROJECT_ROOT / "skills" / "writing-system" / "Reaction GIF for twitter content"
ALLOWED_EXTENSIONS = {".mp4", ".gif", ".jpg", ".jpeg", ".png", ".webp", ".mov"}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _get_presigned_upload(file_name: str, social_set_id: int | None = None) -> dict:
    """Get a presigned S3 upload URL from Typefully via MCP JSON-RPC.

    The REST API v2 doesn't expose media uploads. The MCP server does.
    We call it via JSON-RPC over HTTP with SSE accept headers.
    """
    import json as _json

    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    MCP_KEY = os.getenv("TYPEFULLY_MCP_API_KEY", "Kmw6C71gGVO1ycYqgK3YXIxPdPAK7iS9")

    resp = requests.post(
        f"https://mcp.typefully.com/mcp?TYPEFULLY_API_KEY={MCP_KEY}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "typefully_create_media_upload",
                "arguments": {
                    "social_set_id": sid,
                    "requestBody": {"file_name": file_name},
                },
            },
            "id": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()

    # Parse SSE response — the data is in "event: message\ndata: {...}"
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            data = _json.loads(line[6:])
            # Extract the JSON from the text content
            text = data.get("result", {}).get("content", [{}])[0].get("text", "")
            # The text contains "API Response (Status: 201):\n{...}"
            json_start = text.find("{")
            if json_start >= 0:
                return _json.loads(text[json_start:])

    raise RuntimeError("Could not parse media upload response from Typefully MCP")


def upload_media(file_path: Path, social_set_id: int | None = None) -> str:
    """
    Upload a media file to Typefully and return the media_id.

    1. Request a presigned upload URL (via MCP or API)
    2. PUT the raw file bytes to that URL (no auth headers — presigned)
    3. Return the media_id for use in create_draft
    """
    file_name = file_path.name

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in ".-_()" else "_" for c in file_name)
    if not safe_name or not any(safe_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        safe_name = f"reaction{file_path.suffix}"

    # Step 1: Get presigned upload URL
    data = _get_presigned_upload(safe_name, social_set_id)
    upload_url = data["upload_url"]
    media_id = data["media_id"]

    # Step 2: PUT raw bytes — NO auth headers, NO content-type (presigned URL includes signature)
    file_bytes = file_path.read_bytes()
    put_resp = requests.put(upload_url, data=file_bytes)
    put_resp.raise_for_status()

    return media_id


def pick_random_gif() -> Path | None:
    """Pick a random media file from the Reaction GIF folder."""
    if not GIF_FOLDER.exists():
        return None
    files = [f for f in GIF_FOLDER.iterdir() if f.suffix.lower() in ALLOWED_EXTENSIONS]
    if not files:
        return None
    return random.choice(files)


def create_draft(
    post_text: str,
    qrt_url: str | None = None,
    media_ids: list[str] | None = None,
    social_set_id: int | None = None,
    schedule_at: str | None = None,
    draft_title: str | None = None,
    scratchpad: str | None = None,
) -> dict:
    """
    Create a Typefully draft with optional media and QRT.

    Args:
        post_text: The full post text.
        qrt_url: URL to quote-retweet (for Tuki QRT format).
        media_ids: List of media IDs from upload_media().
        social_set_id: Typefully social set ID. Defaults to GeniusGTX_2 (151393).
        schedule_at: ISO 8601 datetime or "now" or "next-free-slot". None = draft only.
        draft_title: Internal title for the draft (not posted to social media).
        scratchpad: Internal notes/metadata (source URLs, format info, etc).
    """
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID

    post: dict = {"text": post_text}
    if qrt_url:
        post["quote_post_url"] = qrt_url
    if media_ids:
        post["media_ids"] = media_ids

    payload: dict = {
        "platforms": {
            "x": {
                "enabled": True,
                "posts": [post],
            }
        }
    }

    if draft_title:
        payload["draft_title"] = draft_title
    if scratchpad:
        payload["scratchpad_text"] = scratchpad
    if schedule_at:
        payload["publish_at"] = schedule_at

    resp = requests.post(
        f"{API_BASE}/social-sets/{sid}/drafts",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_draft(draft_id: str | int, social_set_id: int | None = None) -> dict:
    """Fetch a draft by ID."""
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.get(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def list_drafts(
    status: str | None = None,
    tag: list[str] | None = None,
    social_set_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    List drafts from Typefully, optionally filtered by status and/or tags.

    Args:
        status: Filter by status — "scheduled", "published", "draft", or None for all.
        tag: Filter by tag names (e.g. ["needs-media", "ready-for-review"]).
        social_set_id: Typefully social set ID.
        limit: Max results per page (max 50 for v2).

    Returns list of draft dicts.
    """
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    params: dict = {"limit": min(limit, 50)}
    if status:
        params["status"] = status

    all_drafts = []
    offset = 0

    while True:
        params["offset"] = offset

        # Build URL with tag params (v2 uses repeated tag= params)
        url = f"{API_BASE}/social-sets/{sid}/drafts"
        if tag:
            tag_params = "&".join(f"tag={t}" for t in tag)
            url = f"{url}?{tag_params}"

        resp = requests.get(
            url,
            headers=_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", []) if isinstance(data, dict) else data
        all_drafts.extend(results)

        if isinstance(data, dict) and data.get("next") and len(results) >= min(limit, 50):
            offset += min(limit, 50)
        else:
            break

    return all_drafts


def add_tag_to_draft(draft_id: str | int, tag: str, social_set_id: int | None = None) -> dict:
    """Add a tag to an existing draft."""
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.patch(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        json={"tags": [tag]},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def edit_draft_text(
    draft_id: str | int,
    new_posts: list[dict],
    social_set_id: int | None = None,
) -> dict:
    """
    Update the text of an existing draft in place.
    Preserves media, QRT URLs, tags, and all other settings.
    """
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.patch(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        json={
            "platforms": {
                "x": {
                    "enabled": True,
                    "posts": new_posts,
                }
            }
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def enable_sharing(draft_id: str | int, social_set_id: int | None = None) -> str | None:
    """Enable public sharing on a draft and return the share_url."""
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.patch(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        json={"share": True},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("share_url")


def get_scheduled_times(social_set_id: int | None = None) -> list[str]:
    """
    Get ISO timestamps of all currently scheduled (but not yet published) drafts.
    Used by the Account Manager to avoid double-booking time slots.
    """
    drafts = list_drafts(status="scheduled", social_set_id=social_set_id)
    times = []
    for d in drafts:
        pub = d.get("publish_at") or d.get("scheduled_at") or d.get("scheduled_date")
        if pub:
            times.append(pub)
    return times


def schedule_draft(draft_id: str | int, publish_at: str, social_set_id: int | None = None) -> dict:
    """
    Schedule an existing draft for publishing.

    Args:
        draft_id: The Typefully draft ID.
        publish_at: ISO 8601 datetime string, "now", or "next-free-slot".
    """
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.patch(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        json={"scheduled_date": publish_at},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def delete_draft(draft_id: str | int, social_set_id: int | None = None) -> bool:
    """Delete a draft by ID. Returns True if deleted."""
    sid = social_set_id or DEFAULT_SOCIAL_SET_ID
    resp = requests.delete(
        f"{API_BASE}/social-sets/{sid}/drafts/{draft_id}",
        headers=_headers(),
        timeout=15,
    )
    return resp.status_code in (200, 204)
