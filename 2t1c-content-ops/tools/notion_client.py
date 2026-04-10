"""
Notion client for the GeniusGTX content pipeline.
Wraps the notion-client SDK (v3) to interact with the Idea Pipeline database.

SETUP: The Notion integration must be granted access to the Idea Pipeline database.
Go to the Idea Pipeline page in Notion → ··· menu → Connections → add your integration.
"""

from __future__ import annotations

import os
from pathlib import Path
import requests as _requests
from notion_client import Client
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
notion = Client(auth=NOTION_API_KEY)

# The notion-client v3 SDK's request() method has URL issues with database queries.
# Use raw requests for query operations, SDK for page create/update.
_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _query_database(db_id: str, body: dict) -> dict:
    """Query a Notion database using raw requests (bypasses SDK URL bug)."""
    resp = _requests.post(
        f"{_NOTION_API_BASE}/databases/{db_id}/query",
        headers=_NOTION_HEADERS,
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
# Page IDs (NOT collection IDs) — these work with the REST API
IDEA_PIPELINE_DB_ID = os.getenv("NOTION_IDEA_PIPELINE_DB_ID", "c4fed84b-f0a9-4459-bad3-69c93f3de40a")
VIDEO_BACKLOG_DB_ID = os.getenv("NOTION_VIDEO_BACKLOG_DB_ID", "284bcb2c-fe18-4b27-b00d-b9e7fa886716")
LONGFORM_POST_DB_ID = os.getenv("NOTION_LONGFORM_POST_DB_ID", "d07478d0-0040-4b95-9c73-ea138ddbbe42")


def get_triggered_ideas(assigned_format: str = "Tuki QRT") -> list[dict]:
    """
    Query the Idea Pipeline for ideas with Status='Triggered' and a specific Assigned Format.

    Returns a list of dicts with keys: id, idea, status, urgency, source_url,
    source_account, content_angle, assigned_formats, notes.
    """
    filters = {
        "and": [
            {"property": "Status", "select": {"equals": "Triggered"}},
            {"property": "Assigned Formats", "multi_select": {"contains": assigned_format}},
        ]
    }

    # notion-client v3: databases.query was removed; use raw POST request
    response = _query_database(IDEA_PIPELINE_DB_ID,{"filter": filters},
    )

    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source_account": _get_rich_text(props.get("Source Account", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "notes": _get_rich_text(props.get("Notes", {})),
        })
    return ideas


def update_idea_status(idea_id: str, status: str) -> dict:
    """
    Update the Status property of an idea.

    Valid statuses: New, Triggered, Drafting, Ready for Review, Approved, Published, Killed.
    """
    return notion.pages.update(
        page_id=idea_id,
        properties={
            "Status": {"select": {"name": status}},
        },
    )


def save_typefully_draft_id(idea_id: str, draft_id: str, share_url: str = "") -> dict:
    """Save Typefully draft ID and share URL to the Notion idea page."""
    properties = {
        "Typefully Draft ID": {"rich_text": [{"text": {"content": draft_id}}]},
    }
    if share_url:
        properties["Typefully Shared URL"] = {"url": share_url}
    return notion.pages.update(
        page_id=idea_id,
        properties=properties,
    )


def get_backlog_videos(status: str = "Backlog") -> list[dict]:
    """
    Query the Video Backlog database for videos with a given status.

    Returns list of dicts: id, title, video_url, video_type, channel, status, notes.
    """
    filters = {"property": "Status", "status": {"equals": status}}
    response = _query_database(VIDEO_BACKLOG_DB_ID,{"filter": filters},
    )
    videos = []
    for page in response.get("results", []):
        props = page["properties"]
        videos.append({
            "id": page["id"],
            "title": _get_title(props.get("Video Title", {})),
            "video_url": _get_url(props.get("Video URL", {})),
            "video_type": _get_select(props.get("Video Type", {})),
            "channel": _get_rich_text(props.get("Channel", {})),
            "status": _get_status(props.get("Status", {})),
            "notes": _get_rich_text(props.get("Notes", {})),
        })
    return videos


def update_video_status(video_id: str, status: str) -> dict:
    """Update the Status property of a Video Backlog entry."""
    return notion.pages.update(
        page_id=video_id,
        properties={"Status": {"select": {"name": status}}},
    )


def create_longform_post(
    title: str,
    video_id: str | None = None,
    video_url: str = "",
    snippet_type: str = "",
    clip_start: str = "",
    clip_end: str = "",
    content_angle: str = "",
    post_text: str = "",
    status: str = "Draft",
    typefully_url: str = "",
    source_idea_url: str = "",
) -> dict:
    """
    Create a new entry in the Long-Form Post Library.

    Returns the created page dict from Notion.
    """
    properties = {
        "Post Title": {"title": [{"text": {"content": title}}]},
        "Status": {"select": {"name": status}},
    }
    if snippet_type:
        properties["Snippet Type"] = {"select": {"name": snippet_type}}
    if clip_start:
        properties["Clip Start"] = {"rich_text": [{"text": {"content": clip_start}}]}
    if clip_end:
        properties["Clip End"] = {"rich_text": [{"text": {"content": clip_end}}]}
    if content_angle:
        properties["Content Angle"] = {"rich_text": [{"text": {"content": content_angle}}]}
    if typefully_url:
        properties["Typefully Shared URL"] = {"url": typefully_url}
    if source_idea_url:
        # Source Idea is a relation property — pass the page ID
        properties["Source Idea"] = {"relation": [{"id": source_idea_url}]}

    # Add post body as page content (children blocks) if provided
    children = []
    if post_text:
        # Split into paragraphs and add as blocks (Notion limit: 2000 chars per block)
        for para in post_text.split("\n\n"):
            if para.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": para[:2000]}}]
                    },
                })

    body = {
        "parent": {"database_id": LONGFORM_POST_DB_ID},
        "properties": properties,
    }
    if children:
        body["children"] = children

    return notion.pages.create(**body)


def get_longform_posts(status: str = "Ready to Post") -> list[dict]:
    """Query the Long-Form Post Library for posts with a given status."""
    filters = {"property": "Status", "select": {"equals": status}}
    response = _query_database(LONGFORM_POST_DB_ID,{"filter": filters},
    )
    posts = []
    for page in response.get("results", []):
        props = page["properties"]
        posts.append({
            "id": page["id"],
            "title": _get_title(props.get("Post Title", {})),
            "status": _get_select(props.get("Status", {})),
            "snippet_type": _get_select(props.get("Snippet Type", {})),
            "clip_start": _get_rich_text(props.get("Clip Start", {})),
            "clip_end": _get_rich_text(props.get("Clip End", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "key_quote": _get_rich_text(props.get("Key Quote", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "qrt_url": _get_url(props.get("QRT Target URL", {})),
            "priority": props.get("Priority", {}).get("number"),
            "batch": _get_rich_text(props.get("Batch", {})),
            "format": _get_select(props.get("Format", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source_account": _get_rich_text(props.get("Source Account", {})),
            "publish_slot": _get_rich_text(props.get("Publish Slot", {})),
            "urgency": _get_select(props.get("Urgency", {})),
        })
    return posts


def update_longform_post(post_id: str, **properties) -> dict:
    """
    Update properties on a Long-Form Post Library entry.

    Accepts keyword args matching property names:
        status, typefully_draft_id, qrt_url, clip_start, clip_end
    """
    prop_map = {}
    if "status" in properties:
        prop_map["Status"] = {"select": {"name": properties["status"]}}
    if "typefully_draft_id" in properties:
        prop_map["Typefully Draft ID"] = {
            "rich_text": [{"text": {"content": properties["typefully_draft_id"]}}]
        }
    if "qrt_url" in properties:
        prop_map["QRT Target URL"] = {"url": properties["qrt_url"]}
    if "clip_start" in properties:
        prop_map["Clip Start"] = {
            "rich_text": [{"text": {"content": properties["clip_start"]}}]
        }
    if "clip_end" in properties:
        prop_map["Clip End"] = {
            "rich_text": [{"text": {"content": properties["clip_end"]}}]
        }
    if "format" in properties:
        prop_map["Format"] = {"select": {"name": properties["format"]}}
    if "source_url" in properties:
        prop_map["Source URL"] = {"url": properties["source_url"]}
    if "publish_slot" in properties:
        prop_map["Publish Slot"] = {
            "rich_text": [{"text": {"content": properties["publish_slot"]}}]
        }
    if "urgency" in properties:
        prop_map["Urgency"] = {"select": {"name": properties["urgency"]}}
    return notion.pages.update(page_id=post_id, properties=prop_map)


def get_idea_by_id(idea_id: str) -> dict:
    """Fetch a single idea page by its Notion page ID."""
    page = notion.pages.retrieve(page_id=idea_id)
    props = page["properties"]
    return {
        "id": page["id"],
        "idea": _get_title(props.get("Idea", {})),
        "status": _get_select(props.get("Status", {})),
        "urgency": _get_select(props.get("Urgency", {})),
        "source_url": _get_url(props.get("Source URL", {})),
        "source_account": _get_rich_text(props.get("Source Account", {})),
        "content_angle": _get_rich_text(props.get("Content Angle", {})),
        "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
        "notes": _get_rich_text(props.get("Notes", {})),
    }


def get_triggered_ideas_with_plans() -> list[dict]:
    """
    Query Idea Pipeline for ideas with Status='Triggered' that have an Extraction Plan.
    Used by content_orchestrator to parse plans and create Library entries.
    """
    filters = {
        "and": [
            {"property": "Status", "select": {"equals": "Triggered"}},
            {"property": "Extraction Plan", "rich_text": {"is_not_empty": True}},
        ]
    }
    response = _query_database(IDEA_PIPELINE_DB_ID,{"filter": filters},
    )
    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source_account": _get_rich_text(props.get("Source Account", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "notes": _get_rich_text(props.get("Notes", {})),
            "extraction_plan": _get_rich_text(props.get("Extraction Plan", {})),
            "content_map": _get_rich_text(props.get("Content Map", {})),
        })
    return ideas


def get_idea_by_id_full(idea_id: str) -> dict:
    """Fetch a single idea with ALL fields including extraction_plan and content_map."""
    page = notion.pages.retrieve(page_id=idea_id)
    props = page["properties"]
    return {
        "id": page["id"],
        "idea": _get_title(props.get("Idea", {})),
        "status": _get_select(props.get("Status", {})),
        "urgency": _get_select(props.get("Urgency", {})),
        "source_url": _get_url(props.get("Source URL", {})),
        "source_account": _get_rich_text(props.get("Source Account", {})),
        "content_angle": _get_rich_text(props.get("Content Angle", {})),
        "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
        "notes": _get_rich_text(props.get("Notes", {})),
        "extraction_plan": _get_rich_text(props.get("Extraction Plan", {})),
        "content_map": _get_rich_text(props.get("Content Map", {})),
    }


def create_longform_from_angle(
    title: str,
    source_idea_id: str,
    assigned_format: str,
    content_angle: str,
    source_url: str = "",
    source_account: str = "",
    publish_slot: str = "",
    urgency: str = "",
    priority: int = 0,
    parent_idea_title: str = "",
    parent_idea_notes: str = "",
    status: str = "Angle Found",
) -> dict:
    """
    Create a Long-Form Post Library entry from an angle in the Extraction Plan.
    Sets the Source Idea relation back to the parent Idea Pipeline entry.
    """
    properties = {
        "Post Title": {"title": [{"text": {"content": title}}]},
        "Source Idea": {"relation": [{"id": source_idea_id}]},
        "Format": {"select": {"name": assigned_format}},
        "Content Angle": {"rich_text": [{"text": {"content": content_angle}}]},
        "Status": {"select": {"name": status}},
        "Post Source": {"select": {"name": "Idea Pipeline"}},
        "Priority": {"number": priority},
    }
    if source_url:
        properties["Source URL"] = {"url": source_url}
    if source_account:
        properties["Source Account"] = {"rich_text": [{"text": {"content": source_account}}]}
    if publish_slot:
        properties["Publish Slot"] = {"rich_text": [{"text": {"content": publish_slot}}]}
    if urgency:
        properties["Urgency"] = {"select": {"name": urgency}}

    # Page body: parent context for Maya
    children = []
    if parent_idea_title:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"Parent Idea: {parent_idea_title}"}}]
            },
        })
    if parent_idea_notes:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"Notes: {parent_idea_notes[:2000]}"}}]
            },
        })

    body = {
        "parent": {"database_id": LONGFORM_POST_DB_ID},
        "properties": properties,
    }
    if children:
        body["children"] = children

    return notion.pages.create(**body)


def get_approved_ideas() -> list[dict]:
    """
    Query the Idea Pipeline for ideas with Status='Approved' that have a Typefully Draft ID.
    These are ready for the Account Manager to schedule.
    """
    filters = {
        "and": [
            {"property": "Status", "select": {"equals": "Approved"}},
            {"property": "Typefully Draft ID", "rich_text": {"is_not_empty": True}},
        ]
    }
    response = _query_database(IDEA_PIPELINE_DB_ID,{"filter": filters},
    )
    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "publish_slot": _get_rich_text(props.get("Publish Slot", {})),
            "source": "idea_pipeline",
        })
    return ideas


def get_approved_library_posts() -> list[dict]:
    """
    Query the Long-Form Post Library for posts with Status='Approved' that have a Typefully Draft ID.
    These are ready for the Account Manager to schedule.
    """
    filters = {
        "and": [
            {"property": "Status", "select": {"equals": "Approved"}},
            {"property": "Typefully Draft ID", "rich_text": {"is_not_empty": True}},
        ]
    }
    response = _query_database(LONGFORM_POST_DB_ID,{"filter": filters},
    )
    posts = []
    for page in response.get("results", []):
        props = page["properties"]
        posts.append({
            "id": page["id"],
            "title": _get_title(props.get("Post Title", {})),
            "status": _get_select(props.get("Status", {})),
            "format": _get_select(props.get("Format", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "publish_slot": _get_rich_text(props.get("Publish Slot", {})),
            "priority": props.get("Priority", {}).get("number"),
            "source": "library",
        })
    return posts


def mark_idea_scheduled(idea_id: str) -> dict:
    """Mark an Idea Pipeline entry as Scheduled."""
    return notion.pages.update(
        page_id=idea_id,
        properties={"Status": {"select": {"name": "Scheduled"}}},
    )


def mark_library_post_scheduled(post_id: str) -> dict:
    """Mark a Long-Form Post Library entry as Scheduled."""
    return notion.pages.update(
        page_id=post_id,
        properties={"Status": {"select": {"name": "Scheduled"}}},
    )


def get_ready_for_review_ideas() -> list[dict]:
    """
    Query the Idea Pipeline for ideas with Status='Ready for Review'.
    Used by the Telegram review bot to send drafts for approval.
    """
    filters = {"property": "Status", "select": {"equals": "Ready for Review"}}
    response = _query_database(IDEA_PIPELINE_DB_ID, {"filter": filters})
    ideas = []
    for page in response.get("results", []):
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "assigned_formats": _get_multi_select(props.get("Assigned Formats", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source": "idea_pipeline",
        })
    return ideas


def get_ready_for_review_library() -> list[dict]:
    """
    Query the Long-Form Post Library for posts with Status='Ready for Review'.
    Used by the Telegram review bot to send drafts for approval.
    """
    filters = {"property": "Status", "select": {"equals": "Ready for Review"}}
    response = _query_database(LONGFORM_POST_DB_ID, {"filter": filters})
    posts = []
    for page in response.get("results", []):
        props = page["properties"]
        posts.append({
            "id": page["id"],
            "title": _get_title(props.get("Post Title", {})),
            "status": _get_select(props.get("Status", {})),
            "format": _get_select(props.get("Format", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source": "library",
        })
    return posts


def save_review_feedback(page_id: str, feedback: str, source: str = "idea_pipeline") -> dict:
    """
    Save rejection feedback to a Notion page and revert status to 'Revision'.
    Works for both Idea Pipeline and Library entries.
    """
    props: dict = {"Status": {"select": {"name": "Revision"}}}
    if source == "idea_pipeline":
        props["Notes"] = {"rich_text": [{"text": {"content": f"[REVISION] {feedback}"}}]}
    else:
        props["Notes"] = {"rich_text": [{"text": {"content": f"[REVISION] {feedback}"}}]}
    return notion.pages.update(page_id=page_id, properties=props)


def get_library_entries_by_status(status: str = "Angle Found") -> list[dict]:
    """Query the Long-Form Post Library for entries with a given status."""
    filters = {"property": "Status", "select": {"equals": status}}
    response = _query_database(LONGFORM_POST_DB_ID,{"filter": filters},
    )
    entries = []
    for page in response.get("results", []):
        props = page["properties"]
        entries.append({
            "id": page["id"],
            "title": _get_title(props.get("Post Title", {})),
            "status": _get_select(props.get("Status", {})),
            "format": _get_select(props.get("Format", {})),
            "content_angle": _get_rich_text(props.get("Content Angle", {})),
            "source_url": _get_url(props.get("Source URL", {})),
            "source_account": _get_rich_text(props.get("Source Account", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "priority": props.get("Priority", {}).get("number"),
            "publish_slot": _get_rich_text(props.get("Publish Slot", {})),
            "qrt_url": _get_url(props.get("QRT Target URL", {})),
            "notes": _get_rich_text(props.get("Notes", {})),
            "key_quote": _get_rich_text(props.get("Key Quote", {})),
            "typefully_draft_id": _get_rich_text(props.get("Typefully Draft ID", {})),
        })
    return entries


# --- Property extractors ---

def _get_title(prop: dict) -> str:
    items = prop.get("title", [])
    return items[0]["plain_text"] if items else ""


def _get_rich_text(prop: dict) -> str:
    items = prop.get("rich_text", [])
    return items[0]["plain_text"] if items else ""


def _get_status(prop: dict) -> str:
    status = prop.get("status")
    return status["name"] if status else ""


def _get_select(prop: dict) -> str:
    select = prop.get("select")
    return select["name"] if select else ""


def _get_multi_select(prop: dict) -> list[str]:
    return [item["name"] for item in prop.get("multi_select", [])]


def _get_url(prop: dict) -> str:
    return prop.get("url") or ""
