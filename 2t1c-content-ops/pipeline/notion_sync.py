"""
Notion Sync — Pulls the latest content from Notion pages and updates local files.

Notion is the source of truth. This script syncs Notion → local.
Local files are cached copies used by agents when running offline or via API.

Usage:
    python -m pipeline.notion_sync --all         # sync everything
    python -m pipeline.notion_sync --writing      # sync Writing Style Guide only
    python -m pipeline.notion_sync --hooks        # sync Hook Writing Guide only
    python -m pipeline.notion_sync --docs         # sync operational docs only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Notion Page ID → Local File mapping
# ---------------------------------------------------------------------------

SYNC_MAP = {
    "writing-style-guide": {
        "notion_page_id": "33004fca-1794-81f9-b85c-de9132b145b6",
        "local_path": PROJECT_ROOT / "skills" / "writing-system" / "SKILL.md",
        "description": "✍️ Writing Style Guide (Maya's writing rules)",
        "frontmatter_template": {
            "name": "writing-system",
            "version": "2.1.0",
            "source_of_truth": "notion",
        },
    },
    "hook-writing-guide": {
        "notion_page_id": "33004fca-1794-81cd-a1de-c88ca30837cc",
        "local_path": PROJECT_ROOT / "skills" / "hook-writing-system" / "SKILL.md",
        "description": "🪝 Hook Writing Guide (Jordan's hook rules)",
        "frontmatter_template": {
            "name": "hook-writing-system",
            "version": "1.0.0",
            "source_of_truth": "notion",
        },
    },
    "media-workflow-guide": {
        "notion_page_id": "33004fca-1794-81e3-bd37-d73e13b82d25",
        "local_path": PROJECT_ROOT / "docs" / "media-workflow-guide.md",
        "description": "🎬 Media Workflow Guide",
    },
    "content-generation-playbook": {
        "notion_page_id": "33104fca-1794-818c-b9a8-fce540da0a66",
        "local_path": PROJECT_ROOT / "docs" / "content-generation-playbook.md",
        "description": "📋 Content Generation Playbook",
    },
    "ideation-workflow": {
        "notion_page_id": "33004fca-1794-81af-b0aa-f0615386ad68",
        "local_path": PROJECT_ROOT / "docs" / "ideation-workflow-architecture.md",
        "description": "🧠 Ideation Workflow Architecture",
    },
    "repurposing-matrix": {
        "notion_page_id": "33004fca-1794-8163-a08f-eec8e6beaa6a",
        "local_path": PROJECT_ROOT / "docs" / "content-repurposing-matrix.md",
        "description": "🔄 Content Repurposing Matrix",
    },
}

# ---------------------------------------------------------------------------
# Notion content extraction
# ---------------------------------------------------------------------------

def fetch_notion_page(page_id: str) -> str:
    """
    Fetch a Notion page's content as markdown.

    This function is designed to be called from within Claude Code sessions
    where Notion MCP tools are available. For standalone execution, it uses
    the notion-client SDK as a fallback.
    """
    try:
        from notion_client import Client
        import os
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=True)
        notion = Client(auth=os.getenv("NOTION_API_KEY"))

        # Fetch all blocks from the page
        blocks = []
        cursor = None
        while True:
            response = notion.blocks.children.list(
                block_id=page_id.replace("-", ""),
                start_cursor=cursor,
            )
            blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return _blocks_to_markdown(blocks)

    except Exception as e:
        print(f"    WARN: Notion SDK fetch failed ({e})")
        print(f"    To sync, run this from a Claude Code session with Notion MCP tools.")
        return ""


def _blocks_to_markdown(blocks: list) -> str:
    """Convert Notion blocks to markdown text."""
    lines = []
    for block in blocks:
        block_type = block.get("type", "")

        if block_type == "paragraph":
            text = _rich_text_to_str(block["paragraph"].get("rich_text", []))
            lines.append(text)
            lines.append("")

        elif block_type.startswith("heading_"):
            level = int(block_type[-1])
            text = _rich_text_to_str(block[block_type].get("rich_text", []))
            lines.append(f"{'#' * level} {text}")
            lines.append("")

        elif block_type == "bulleted_list_item":
            text = _rich_text_to_str(block["bulleted_list_item"].get("rich_text", []))
            lines.append(f"- {text}")

        elif block_type == "numbered_list_item":
            text = _rich_text_to_str(block["numbered_list_item"].get("rich_text", []))
            lines.append(f"1. {text}")

        elif block_type == "divider":
            lines.append("---")
            lines.append("")

        elif block_type == "code":
            text = _rich_text_to_str(block["code"].get("rich_text", []))
            lang = block["code"].get("language", "")
            lines.append(f"```{lang}")
            lines.append(text)
            lines.append("```")
            lines.append("")

        elif block_type == "quote":
            text = _rich_text_to_str(block["quote"].get("rich_text", []))
            lines.append(f"> {text}")
            lines.append("")

        elif block_type == "callout":
            text = _rich_text_to_str(block["callout"].get("rich_text", []))
            lines.append(f"> {text}")
            lines.append("")

    return "\n".join(lines)


def _rich_text_to_str(rich_text: list) -> str:
    """Convert Notion rich text array to plain string with basic markdown."""
    parts = []
    for segment in rich_text:
        text = segment.get("plain_text", "")
        annotations = segment.get("annotations", {})
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("code"):
            text = f"`{text}`"
        parts.append(text)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------

def sync_page(key: str, content: str | None = None) -> bool:
    """
    Sync a single page from Notion to local.

    Args:
        key: Key from SYNC_MAP (e.g., "writing-style-guide")
        content: Pre-fetched content (if None, fetches from Notion SDK)
    """
    entry = SYNC_MAP[key]
    page_id = entry["notion_page_id"]
    local_path = entry["local_path"]
    description = entry["description"]

    print(f"\n--- Syncing: {description}")
    print(f"    Notion: {page_id}")
    print(f"    Local:  {local_path}")

    if content is None:
        content = fetch_notion_page(page_id)

    if not content or len(content.strip()) < 50:
        print(f"    SKIP: No content fetched (empty or too short)")
        return False

    # Add sync metadata header for docs
    header = f"> Source of truth: Notion page `{page_id}`\n> Last synced: {datetime.now().strftime('%Y-%m-%d')}\n\n"

    # For SKILL.md files, preserve frontmatter and add sync metadata
    if "frontmatter_template" in entry:
        fm = entry["frontmatter_template"]
        frontmatter = f"""---
name: {fm['name']}
version: {fm['version']}
source_of_truth: {fm['source_of_truth']}
notion_page_id: {page_id}
last_synced: "{datetime.now().strftime('%Y-%m-%d')}"
---

"""
        final_content = frontmatter + content
    else:
        final_content = header + content

    # Write to local
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(final_content, encoding="utf-8")
    print(f"    DONE: {len(final_content)} chars written")
    return True


def sync_all():
    """Sync all pages from Notion to local."""
    print(f"Notion Sync — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Source of truth: Notion")
    print(f"Syncing {len(SYNC_MAP)} pages...\n")

    results = {}
    for key in SYNC_MAP:
        results[key] = sync_page(key)

    success = sum(results.values())
    print(f"\n=== Done: {success}/{len(results)} pages synced ===")
    for key, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {SYNC_MAP[key]['description']}")


def sync_group(keys: list[str]):
    """Sync a specific group of pages."""
    for key in keys:
        if key in SYNC_MAP:
            sync_page(key)
        else:
            print(f"Unknown sync key: {key}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

GROUPS = {
    "writing": ["writing-style-guide"],
    "hooks": ["hook-writing-guide"],
    "docs": ["media-workflow-guide", "content-generation-playbook", "ideation-workflow", "repurposing-matrix"],
    "skills": ["writing-style-guide", "hook-writing-guide"],
}


def main():
    parser = argparse.ArgumentParser(description="Notion Sync — pull Notion pages to local files")
    parser.add_argument("--all", action="store_true", help="Sync everything")
    parser.add_argument("--writing", action="store_true", help="Sync Writing Style Guide")
    parser.add_argument("--hooks", action="store_true", help="Sync Hook Writing Guide")
    parser.add_argument("--docs", action="store_true", help="Sync operational docs")
    parser.add_argument("--skills", action="store_true", help="Sync both skill files")
    parser.add_argument("--list", action="store_true", help="List all syncable pages")
    args = parser.parse_args()

    if args.list:
        print("Syncable pages:")
        for key, entry in SYNC_MAP.items():
            print(f"  {key}: {entry['description']}")
            print(f"    Notion: {entry['notion_page_id']}")
            print(f"    Local:  {entry['local_path']}")
        return

    if args.all:
        sync_all()
    elif args.writing:
        sync_group(GROUPS["writing"])
    elif args.hooks:
        sync_group(GROUPS["hooks"])
    elif args.docs:
        sync_group(GROUPS["docs"])
    elif args.skills:
        sync_group(GROUPS["skills"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
