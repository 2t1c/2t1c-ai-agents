"""
CEO Agent — Strategic command layer for GeniusGTX.

Toản talks to this agent via Telegram. It understands the full content operation,
reads/writes Notion, and steers the pipeline. Claude with tool use.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from anthropic import Anthropic
from dotenv import load_dotenv
from notion_client import Client as NotionClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
MODEL = "claude-sonnet-4-6"

# Typefully
TYPEFULLY_API_KEY = os.getenv("TYPEFULLY_API_KEY")
TYPEFULLY_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))

# Tavily (web research)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Persistent memory file
MEMORY_FILE = Path(__file__).resolve().parent / "memory.json"

# ── Notion IDs ──────────────────────────────────────────────────────────────

# Data source (collection) IDs — hardcoded because .env has page IDs for other scripts
IDEA_PIPELINE_DS_ID = "330aef7b-3feb-401e-abba-28452441a64d"
VIDEO_BACKLOG_DS_ID = "316f17ad-ba4f-4719-b239-67a38141b0c9"
WEEKLY_REPORTS_DS_ID = "a4cfa4c8-dead-44ab-a236-42ae91a864a8"
LONGFORM_POST_DS_ID = "d20d2ffc-839a-4435-aa65-6da6f8688644"

# Database page IDs — needed for pages.create (parent)
IDEA_PIPELINE_PAGE_ID = "c4fed84b-f0a9-4459-bad3-69c93f3de40a"
VIDEO_BACKLOG_PAGE_ID = "284bcb2c-fe18-4b27-b00d-b9e7fa886716"
CONTENT_OPS_PAGE_ID = "32f04fca-1794-8120-8f00-fe8fd4dd1cee"
SCORECARD_PAGE_ID = "33404fca-1794-8117-9efe-c41a84291e39"

# Notion page IDs for guidelines
WRITING_STYLE_PAGE = "33004fca-1794-81f9-b85c-de9132b145b6"
HOOK_WRITING_PAGE = "33004fca-1794-81cd-a1de-c88ca30837cc"
CONTENT_PLAYBOOK_PAGE = "33104fca-1794-818c-b9a8-fce540da0a66"
IDEATION_WORKFLOW_PAGE = "33004fca-1794-81af-b0aa-f0615386ad68"

# ── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are the CEO agent for GeniusGTX, a content operation run by Toản Truong (2T1C LLC).

You are Toản's strategic co-pilot. He talks to you on Telegram to steer the content machine. You understand the full operation and can take action via Notion (the source of truth).

## Your Role
- Listen to Toản's direction, ideas, and feedback
- Take action by reading/writing to Notion
- Confirm what you did and suggest next steps
- Be direct, concise, and sharp. No fluff.
- When Toản gives vague direction, ask one clarifying question — then act.
- You know EVERYTHING about this business. You have full access to every document, database, and guideline.

## The Business — 2T1C LLC / GeniusGTX
- Company: 2T1C LLC, founded by Toản Truong
- Brand: GeniusGTX (@GeniusGTX_2 on X/Twitter)
- Also manages: @LearningToan_1 (personal), @ovquang (Quang Do)
- Platform: X/Twitter primary, cross-posts to Threads and Bluesky via Typefully
- Typefully social set ID: 151393

## Content Operation
- 11 content formats: Tuki QRT, Bark QRT, Commentary Post, Stat Bomb, Explainer, Contrarian Take, Multi-Source Explainer, Thread, Video Clip Post, Clip Commentary, Clip Thread
- Content territories: ancient civilizations, systemic shifts, hidden figures, cognitive science, business strategy, geopolitics, breaking news
- Pipeline: Ideas → Triggered → Drafting → Ready for Review → Approved → Published
- Agents handle production. Toản handles taste/judgment/approval.

## Agent Team
- **Jordan** — Hook writer (Slack bot). Writes scroll-stopping hooks for X/Twitter.
- **Maya** — Thread/body writer (Slack bot). Writes full posts with format-specific rules.
- **Ellis** — (Placeholder, not built yet)
- **Kai** — (Placeholder, not built yet)

## Key Pipelines
- **Format Pipeline** — `python3 -m pipeline.format_pipeline` — processes all 11 formats
- **Long-form Pipeline** — `python3 -m pipeline.longform_pipeline` — YouTube → transcript → posts + clips
- **Tuki Pipeline** — `python3 -m pipeline.tuki_pipeline` — dedicated Tuki QRT processor
- **Weekly Report** — `python3 -m pipeline.weekly_report` — performance analytics

## Notion Workspace Map
All guidelines, rules, and data live in Notion. This is the source of truth.

Content Operations page (parent of everything):
- Writing Style Guide — voice, tone, rules for all content
- Hook Writing Guide — Jordan's hook system rules
- Content Generation Playbook — end-to-end process for content creation
- Ideation Workflow Architecture — how ideas flow from raw signal to pipeline
- Media Workflow Guide — GIF, QRT, clip attachment rules
- Content Repurposing Matrix — how to repurpose across formats
- Content Format Bank (database) — definitions for each format
- Idea Pipeline (database) — the main content pipeline
- Account Monitor List (database) — accounts we track for content signals
- GIF Library (database) — media assets
- Business Scorecard — performance tracking + weekly reports
- Long-Form Content Hub — Video Backlog + Post Library databases
- Content Format Insights — per-format performance insights
- Posting Schedule & Content Calendar Rules

## Q2 2026 Targets
- Posts/week: 25-35
- Avg impressions/post: 100,000 (target), 50,000 (minimum)
- Engagement rate: >1.75%
- Saves/post: 150+
- Profile clicks/post: 50+

## Autoresearch — Continuous Improvement (Karpathy Pattern)
You run an autoresearch loop adapted from Karpathy's autonomous optimization pattern.

The correct flow — NEVER skip steps:
1. BASELINE → Establish current metrics (use get_analytics / analyze_performance)
2. MUST-HAVES → Every variation must pass the 59-rule gate check (voice, formatting, hooks, quality, brand). The gate is automatic — variations get checked before you show them.
3. ANALYZE → What's working? What's underperforming? Group by hook type, format, length.
4. HYPOTHESIZE → Propose ONE specific, testable change. "Number hooks outperform questions" not "make hooks better."
5. TEST → Generate A/B variations. Both get gate-checked. If B fails the gate, flag it.
6. EVALUATE → Toản picks A, B, or Neither + gives feedback. Log the result.
7. KEEP/DISCARD → Binary decision. If kept, save as memory for future reference.

Key behaviors:
- When discussing what's working/not working, use analyze_performance to get REAL data first
- Proactively suggest A/B tests when you spot opportunities ("Your number hooks get 3x more views — want to test a variation?")
- When Toản gives feedback on a post ("this one crushed it" or "this didn't land"), offer to create an experiment
- After A/B tests, always ask for pick (A, B, Neither) and log with feedback
- Use saved memories to track what patterns have been tested and what works
- In daily briefings, include experiment insights
- NEVER present a variation that fails the must-haves gate without flagging it

## What You Can Do (tools)
- Query the Idea Pipeline (status, count, search)
- Add new ideas to the pipeline
- Query the Video Backlog
- Add videos to the backlog
- Read any Notion guideline page
- Update Notion guideline pages
- Query weekly performance reports
- Update the Business Scorecard targets

Always use tools when action is needed. Don't just describe what you'd do — do it.

## Formatting Rules (Telegram)
You are talking via Telegram. Format for mobile readability:
- Use **bold** for emphasis and section headers
- Use bullet lists, not markdown tables. Tables render poorly on mobile.
- For data with numbers, use a clean list format like:
  Posts: 27
  Impressions: 1.6M (59K avg)
  Engagement: 1.69%
- Keep responses concise. No walls of text.
- Use line breaks between sections for visual breathing room.

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
"""

# ── Tool Definitions ────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "query_ideas",
        "description": "Query the Idea Pipeline. Filter by status, format, or get all. Returns count and list of ideas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: New, Triggered, Drafting, Ready for Review, Approved, Published, Killed. Leave empty for all.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return. Default 10.",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "add_idea",
        "description": "Add a new idea to the Idea Pipeline in Notion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea": {"type": "string", "description": "The idea title/description"},
                "content_angle": {"type": "string", "description": "The specific angle or spin"},
                "assigned_formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Formats to assign: Tuki QRT, Bark QRT, Commentary Post, Stat Bomb, Explainer, Contrarian Take, Multi-Source Explainer, Thread, Video Clip Post, Clip Commentary, Clip Thread",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["🔴 Breaking", "🟡 Trending", "🟢 Evergreen", "⚪ Backlog"],
                    "description": "Urgency level",
                },
                "source_url": {"type": "string", "description": "URL of the source content (tweet, article, video)"},
                "notes": {"type": "string", "description": "Additional notes or context"},
            },
            "required": ["idea"],
        },
    },
    {
        "name": "update_idea_status",
        "description": "Update the status of an idea in the pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The Notion page ID of the idea"},
                "status": {
                    "type": "string",
                    "enum": ["New", "Triggered", "Drafting", "Ready for Review", "Approved", "Published", "Killed"],
                },
            },
            "required": ["idea_id", "status"],
        },
    },
    {
        "name": "add_video",
        "description": "Add a YouTube video to the Video Backlog for long-form repurposing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Video title"},
                "video_url": {"type": "string", "description": "YouTube URL"},
                "video_type": {
                    "type": "string",
                    "enum": ["Podcast", "Normal Video"],
                    "description": "Type of video",
                },
                "notes": {"type": "string", "description": "Why this video, what to extract"},
            },
            "required": ["video_url"],
        },
    },
    {
        "name": "read_guideline",
        "description": "Read a Notion guideline page. Use this to check current rules before updating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": ["writing_style", "hook_writing", "content_playbook", "ideation_workflow"],
                    "description": "Which guideline to read",
                },
            },
            "required": ["page"],
        },
    },
    {
        "name": "update_guideline",
        "description": "Append a new rule or update to a guideline page in Notion. This adds to the end of the page — it does not replace existing content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": ["writing_style", "hook_writing", "content_playbook", "ideation_workflow"],
                },
                "update_text": {
                    "type": "string",
                    "description": "The new rule, guideline, or feedback to add. Will be appended with a date stamp.",
                },
            },
            "required": ["page", "update_text"],
        },
    },
    {
        "name": "query_weekly_reports",
        "description": "Get recent weekly performance reports from the Business Scorecard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent reports. Default 3.", "default": 3},
            },
        },
    },
    {
        "name": "update_targets",
        "description": "Update Q2 2026 performance targets on the Business Scorecard page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Which metric to update (e.g. 'Avg impressions/post', 'Posts published/week')"},
                "new_target": {"type": "string", "description": "The new target value"},
            },
            "required": ["metric", "new_target"],
        },
    },
    {
        "name": "pipeline_summary",
        "description": "Get a quick summary of pipeline health: counts by status, recent ideas, backlog depth.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_notion",
        "description": "Search the entire Notion workspace for pages, databases, or content. Use this to find anything.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_page",
        "description": "Read any Notion page by its ID. Returns the full page content. Use search_notion first to find the page ID if you don't know it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page ID (UUID format)"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "update_page",
        "description": "Append content to any Notion page. Use read_page first to see current content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page ID to update"},
                "content": {"type": "string", "description": "Text content to append to the page"},
                "heading": {"type": "string", "description": "Optional heading for the new section"},
            },
            "required": ["page_id", "content"],
        },
    },
    {
        "name": "run_pipeline",
        "description": "Run a pipeline command on the local machine. Use for: format_pipeline, longform_pipeline, tuki_pipeline, weekly_report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "format_pipeline --all --once",
                        "format_pipeline --format 'Tuki QRT' --once",
                        "format_pipeline --format 'Stat Bomb' --once",
                        "format_pipeline --format 'Thread' --once",
                        "format_pipeline --format 'Bark QRT' --once",
                        "format_pipeline --format 'Explainer' --once",
                        "longform_pipeline --process",
                        "longform_pipeline --finalize",
                        "tuki_pipeline --once",
                        "weekly_report --dry-run",
                        "weekly_report",
                    ],
                    "description": "Pipeline command to run",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "query_format_bank",
        "description": "Query the Content Format Bank database to see format definitions, rules, and examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "format_name": {"type": "string", "description": "Filter by format name (e.g. 'Tuki QRT'). Leave empty for all."},
            },
        },
    },
    {
        "name": "query_monitor_list",
        "description": "Query the Account Monitor List — accounts we track for content signals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["Twitter", "YouTube"], "description": "Filter by platform"},
            },
        },
    },
    {
        "name": "get_analytics",
        "description": "Get post analytics from Typefully for GeniusGTX. Shows impressions, engagement, saves, profile clicks for recent posts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days back to look. Default 7.",
                    "default": 7,
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top posts to return by impressions. Default 5.",
                    "default": 5,
                },
            },
        },
    },
    {
        "name": "analyze_performance",
        "description": "Analyze content performance from Typefully analytics. Groups by post characteristics to identify what's working and what's not. Returns top/bottom performers, pattern insights.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to analyze. Default 30.", "default": 30},
            },
        },
    },
    {
        "name": "ab_test",
        "description": "Generate an A/B test: two variations of a post on the same topic. Variation A uses current writing rules. Variation B uses a proposed change. Present both to Toản for feedback. Logs the experiment to Notion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic or idea to write about"},
                "hypothesis": {"type": "string", "description": "What you're testing (e.g. 'shorter hooks with numbers perform better')"},
                "area": {"type": "string", "enum": ["Hooks", "Voice", "Format", "Examples"], "description": "Which area the experiment targets"},
                "variation_b_instruction": {"type": "string", "description": "Specific instruction for how Variation B should differ from A"},
            },
            "required": ["topic", "hypothesis", "area", "variation_b_instruction"],
        },
    },
    {
        "name": "log_experiment_result",
        "description": "Log the result of an A/B test or experiment after Toản gives feedback. Updates the Notion experiment entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "experiment_id": {"type": "string", "description": "The Notion page ID of the experiment"},
                "user_pick": {"type": "string", "enum": ["A", "B", "Neither"], "description": "Which variation Toản preferred"},
                "feedback": {"type": "string", "description": "Toản's feedback/reasoning"},
                "status": {"type": "string", "enum": ["Kept", "Discarded", "Awaiting Analytics"], "description": "Experiment outcome"},
            },
            "required": ["experiment_id", "user_pick", "feedback", "status"],
        },
    },
    {
        "name": "get_experiments",
        "description": "Get recent autoresearch experiments from the tracking database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: Running, Awaiting Review, Awaiting Analytics, Kept, Discarded"},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "web_research",
        "description": "Search the web for trending topics, news, or research to fuel the content pipeline. Returns summarized results with URLs. Use when Toản asks to research a topic, find trending content, or wants fresh ideas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'trending AI news today', 'psychology of money research 2026')"},
                "max_results": {"type": "integer", "description": "Number of results. Default 5.", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "analyze_image",
        "description": "Analyze a screenshot or image. Use when Toản sends a photo of a viral tweet, post, or any visual content. Describes what's in the image and can propose a GeniusGTX version if it's a post/tweet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "URL or file path of the image"},
                "instruction": {"type": "string", "description": "What to do with the image (e.g. 'analyze why this went viral', 'write a GeniusGTX version')", "default": "Analyze this content. What makes it work? Propose a GeniusGTX angle."},
            },
            "required": ["image_url"],
        },
    },
    {
        "name": "save_memory",
        "description": "Save an important decision, preference, or context that should persist across conversations. Use when Toản states a preference, makes a strategic decision, or gives feedback that should be remembered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short label for this memory (e.g. 'content_direction', 'format_preference')"},
                "content": {"type": "string", "description": "The decision, preference, or context to remember"},
            },
            "required": ["key", "content"],
        },
    },
    {
        "name": "recall_memories",
        "description": "Recall all saved memories/decisions from past conversations.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "habits_status",
        "description": "Check today's non-negotiables status. Shows which of the 6 daily habits are done/pending.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "habits_complete",
        "description": "Mark a daily non-negotiable as complete. IDs: posts, write, read, cardio, study, strength. Can also accept natural language like 'finished cardio' or 'wrote 1000 words'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "habit_id": {
                    "type": "string",
                    "enum": ["posts", "write", "read", "cardio", "study", "strength"],
                    "description": "The habit to mark complete",
                },
            },
            "required": ["habit_id"],
        },
    },
    {
        "name": "habits_week",
        "description": "Show the weekly habits summary — scores per day, average, strongest/weakest habit.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ── Tool Implementations ───────────────────────────────────────────────────

def _get_title(prop: dict) -> str:
    items = prop.get("title", [])
    return items[0]["plain_text"] if items else ""

def _get_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel["name"] if sel else ""

def _get_rich_text(prop: dict) -> str:
    items = prop.get("rich_text", [])
    return items[0]["plain_text"] if items else ""

def _get_multi_select(prop: dict) -> list[str]:
    return [o["name"] for o in prop.get("multi_select", [])]

def _get_url(prop: dict) -> str:
    return prop.get("url") or ""

PAGE_MAP = {
    "writing_style": WRITING_STYLE_PAGE,
    "hook_writing": HOOK_WRITING_PAGE,
    "content_playbook": CONTENT_PLAYBOOK_PAGE,
    "ideation_workflow": IDEATION_WORKFLOW_PAGE,
}

# Additional database data source IDs
FORMAT_BANK_DS_ID = "f7184d53-90b9-4674-8a36-8eb46309fb65"
MONITOR_LIST_DS_ID = "571130ac-da7b-4d5d-b302-e64473f52c9d"
EXPERIMENTS_DS_ID = "ceb7a5b3-d49c-43bf-8292-ef4a4d85e173"
EXPERIMENTS_DB_PAGE_ID = "b89782292f064dcb8af72a28740064d1"


def execute_tool(name: str, input: dict) -> str:
    """Execute a tool and return JSON-serializable result."""
    try:
        if name == "query_ideas":
            return _query_ideas(input.get("status"), input.get("limit", 10))
        elif name == "add_idea":
            return _add_idea(input)
        elif name == "update_idea_status":
            return _update_idea_status(input["idea_id"], input["status"])
        elif name == "add_video":
            return _add_video(input)
        elif name == "read_guideline":
            return _read_guideline(input["page"])
        elif name == "update_guideline":
            return _update_guideline(input["page"], input["update_text"])
        elif name == "query_weekly_reports":
            return _query_weekly_reports(input.get("limit", 3))
        elif name == "update_targets":
            return _update_targets(input["metric"], input["new_target"])
        elif name == "pipeline_summary":
            return _pipeline_summary()
        elif name == "search_notion":
            return _search_notion(input["query"])
        elif name == "read_page":
            return _read_page(input["page_id"])
        elif name == "update_page":
            return _update_page(input["page_id"], input["content"], input.get("heading"))
        elif name == "run_pipeline":
            return _run_pipeline(input["command"])
        elif name == "query_format_bank":
            return _query_format_bank(input.get("format_name"))
        elif name == "query_monitor_list":
            return _query_monitor_list(input.get("platform"))
        elif name == "get_analytics":
            return _get_analytics(input.get("days", 7), input.get("top_n", 5))
        elif name == "analyze_performance":
            return _analyze_performance(input.get("days", 30))
        elif name == "ab_test":
            return _ab_test(input["topic"], input["hypothesis"], input["area"], input["variation_b_instruction"])
        elif name == "log_experiment_result":
            return _log_experiment_result(input["experiment_id"], input["user_pick"], input["feedback"], input["status"])
        elif name == "get_experiments":
            return _get_experiments(input.get("status"), input.get("limit", 5))
        elif name == "web_research":
            return _web_research(input["query"], input.get("max_results", 5))
        elif name == "analyze_image":
            return _analyze_image(input["image_url"], input.get("instruction", "Analyze this content."))
        elif name == "save_memory":
            return _save_memory(input["key"], input["content"])
        elif name == "recall_memories":
            return _recall_memories()
        elif name == "habits_status":
            return _habits_status()
        elif name == "habits_complete":
            return _habits_complete(input["habit_id"])
        elif name == "habits_week":
            return _habits_week()
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _query_ideas(status: str | None, limit: int) -> str:
    body = {}
    if status:
        body["filter"] = {"property": "Status", "select": {"equals": status}}
    body["page_size"] = min(limit, 100)

    resp = notion.data_sources.query(data_source_id=IDEA_PIPELINE_DS_ID, **body)
    results = resp.get("results", [])

    ideas = []
    for page in results[:limit]:
        props = page["properties"]
        ideas.append({
            "id": page["id"],
            "idea": _get_title(props.get("Idea", {})),
            "status": _get_select(props.get("Status", {})),
            "urgency": _get_select(props.get("Urgency", {})),
            "formats": _get_multi_select(props.get("Assigned Formats", {})),
            "angle": _get_rich_text(props.get("Content Angle", {})),
        })

    return json.dumps({"count": len(results), "showing": len(ideas), "ideas": ideas})


def _add_idea(input: dict) -> str:
    properties = {
        "Idea": {"title": [{"text": {"content": input["idea"]}}]},
        "Status": {"select": {"name": "New"}},
    }
    if input.get("content_angle"):
        properties["Content Angle"] = {"rich_text": [{"text": {"content": input["content_angle"]}}]}
    if input.get("assigned_formats"):
        properties["Assigned Formats"] = {"multi_select": [{"name": f} for f in input["assigned_formats"]]}
    if input.get("urgency"):
        properties["Urgency"] = {"select": {"name": input["urgency"]}}
    if input.get("source_url"):
        properties["Source URL"] = {"url": input["source_url"]}
    if input.get("notes"):
        properties["Notes"] = {"rich_text": [{"text": {"content": input["notes"]}}]}

    page = notion.pages.create(
        parent={"database_id": IDEA_PIPELINE_PAGE_ID},
        properties=properties,
    )
    return json.dumps({"success": True, "id": page["id"], "url": page["url"]})


def _update_idea_status(idea_id: str, status: str) -> str:
    notion.pages.update(
        page_id=idea_id,
        properties={"Status": {"select": {"name": status}}},
    )
    return json.dumps({"success": True, "idea_id": idea_id, "new_status": status})


def _add_video(input: dict) -> str:
    properties = {
        "Video Title": {"title": [{"text": {"content": input.get("title", "Untitled")}}]},
        "Video URL": {"url": input["video_url"]},
        "Status": {"select": {"name": "New"}},
    }
    if input.get("video_type"):
        properties["Video Type"] = {"select": {"name": input["video_type"]}}
    if input.get("notes"):
        properties["Notes"] = {"rich_text": [{"text": {"content": input["notes"]}}]}

    page = notion.pages.create(
        parent={"database_id": VIDEO_BACKLOG_PAGE_ID},
        properties=properties,
    )
    return json.dumps({"success": True, "id": page["id"], "url": page["url"]})


def _read_guideline(page_key: str) -> str:
    page_id = PAGE_MAP.get(page_key)
    if not page_id:
        return json.dumps({"error": f"Unknown page: {page_key}"})

    # Fetch child blocks to read content
    blocks = notion.blocks.children.list(block_id=page_id)
    text_parts = []
    for block in blocks.get("results", []):
        block_type = block["type"]
        if block_type in ("paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"):
            rich_texts = block[block_type].get("rich_text", [])
            line = "".join(rt["plain_text"] for rt in rich_texts)
            if block_type.startswith("heading"):
                level = block_type[-1]
                line = f"{'#' * int(level)} {line}"
            elif block_type == "bulleted_list_item":
                line = f"- {line}"
            text_parts.append(line)
        elif block_type == "divider":
            text_parts.append("---")

    return json.dumps({"page": page_key, "content": "\n".join(text_parts)})


def _update_guideline(page_key: str, update_text: str) -> str:
    page_id = PAGE_MAP.get(page_key)
    if not page_id:
        return json.dumps({"error": f"Unknown page: {page_key}"})

    # Append new content as blocks
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    new_blocks = [
        {"type": "divider", "divider": {}},
        {
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": f"Update — {date_stamp}"}}],
            },
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": update_text}}],
            },
        },
    ]
    notion.blocks.children.append(block_id=page_id, children=new_blocks)
    return json.dumps({"success": True, "page": page_key, "added": update_text[:100] + "..."})


def _query_weekly_reports(limit: int) -> str:
    resp = notion.data_sources.query(
        data_source_id=WEEKLY_REPORTS_DS_ID,
        sorts=[{"property": "Week Start", "direction": "descending"}],
        page_size=min(limit, 10),
    )
    reports = []
    for page in resp.get("results", []):
        props = page["properties"]
        reports.append({
            "week": _get_title(props.get("Week", {})),
            "posts": props.get("Posts Published", {}).get("number"),
            "impressions": props.get("Total Impressions", {}).get("number"),
            "avg_impressions": props.get("Avg Impressions/Post", {}).get("number"),
            "engagement_rate": props.get("Engagement Rate %", {}).get("number"),
            "saves": props.get("Saves", {}).get("number"),
            "status": _get_select(props.get("Status", {})),
            "notes": _get_rich_text(props.get("Notes", {})),
        })
    return json.dumps({"reports": reports})


def _update_targets(metric: str, new_target: str) -> str:
    # Read the scorecard page to find the current value
    blocks = notion.blocks.children.list(block_id=SCORECARD_PAGE_ID)
    for block in blocks.get("results", []):
        if block["type"] == "table":
            # Found the targets table — update via the table rows
            rows = notion.blocks.children.list(block_id=block["id"])
            for row in rows.get("results", []):
                if row["type"] == "table_row":
                    cells = row["table_row"]["cells"]
                    if cells and len(cells) >= 2:
                        cell_text = "".join(rt["plain_text"] for rt in cells[0])
                        if metric.lower() in cell_text.lower():
                            # Update the target cell
                            notion.blocks.update(
                                block_id=row["id"],
                                table_row={
                                    "cells": [
                                        cells[0],  # keep metric name
                                        [{"type": "text", "text": {"content": new_target}}],
                                        cells[2] if len(cells) > 2 else [],  # keep baseline
                                    ]
                                },
                            )
                            return json.dumps({"success": True, "metric": metric, "new_target": new_target})

    return json.dumps({"error": f"Could not find metric '{metric}' in scorecard"})


def _pipeline_summary() -> str:
    statuses = ["New", "Triggered", "Drafting", "Ready for Review", "Approved", "Published", "Killed"]
    counts = {}
    for status in statuses:
        resp = notion.data_sources.query(
            data_source_id=IDEA_PIPELINE_DS_ID,
            filter={"property": "Status", "select": {"equals": status}},
        )
        count = len(resp.get("results", []))
        if count > 0:
            counts[status] = count

    # Video backlog
    try:
        video_resp = notion.data_sources.query(data_source_id=VIDEO_BACKLOG_DS_ID)
        video_count = len(video_resp.get("results", []))
    except Exception:
        video_count = 0

    total = sum(counts.values())
    return json.dumps({
        "total_ideas": total,
        "by_status": counts,
        "videos_in_backlog": video_count,
    })


# ── General Notion Tools ────────────────────────────────────────────────────

def _search_notion(query: str) -> str:
    resp = notion.search(query=query, page_size=10)
    results = []
    for item in resp.get("results", []):
        obj_type = item["object"]
        title = ""
        if obj_type == "page":
            title_prop = item.get("properties", {}).get("title", item.get("properties", {}).get("Name", {}))
            if isinstance(title_prop, dict):
                title_items = title_prop.get("title", [])
                title = title_items[0]["plain_text"] if title_items else ""
            # Try other title-like properties
            if not title:
                for prop_name, prop_val in item.get("properties", {}).items():
                    if isinstance(prop_val, dict) and prop_val.get("type") == "title":
                        title_items = prop_val.get("title", [])
                        title = title_items[0]["plain_text"] if title_items else ""
                        break
        elif obj_type == "database":
            title_items = item.get("title", [])
            title = title_items[0]["plain_text"] if title_items else ""

        results.append({
            "id": item["id"],
            "type": obj_type,
            "title": title or "(untitled)",
            "url": item.get("url", ""),
        })
    return json.dumps({"count": len(results), "results": results})


def _read_page(page_id: str) -> str:
    # Get page properties
    page = notion.pages.retrieve(page_id=page_id)
    title = ""
    for prop_name, prop_val in page.get("properties", {}).items():
        if isinstance(prop_val, dict) and prop_val.get("type") == "title":
            title_items = prop_val.get("title", [])
            title = title_items[0]["plain_text"] if title_items else ""
            break

    # Get page content
    blocks = notion.blocks.children.list(block_id=page_id)
    text_parts = []
    for block in blocks.get("results", []):
        block_type = block["type"]
        if block_type in ("paragraph", "heading_1", "heading_2", "heading_3",
                          "bulleted_list_item", "numbered_list_item", "to_do", "quote", "callout"):
            content_obj = block.get(block_type, {})
            rich_texts = content_obj.get("rich_text", [])
            line = "".join(rt["plain_text"] for rt in rich_texts)
            if block_type.startswith("heading"):
                level = block_type[-1]
                line = f"{'#' * int(level)} {line}"
            elif block_type == "bulleted_list_item":
                line = f"- {line}"
            elif block_type == "numbered_list_item":
                line = f"1. {line}"
            elif block_type == "to_do":
                checked = content_obj.get("checked", False)
                line = f"[{'x' if checked else ' '}] {line}"
            text_parts.append(line)
        elif block_type == "divider":
            text_parts.append("---")
        elif block_type == "child_database":
            db_title = block.get("child_database", {}).get("title", "Database")
            text_parts.append(f"[Database: {db_title}]")

    return json.dumps({
        "title": title,
        "id": page_id,
        "content": "\n".join(text_parts),
    })


def _update_page(page_id: str, content: str, heading: str | None = None) -> str:
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    new_blocks = [{"type": "divider", "divider": {}}]

    if heading:
        new_blocks.append({
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": f"{heading} — {date_stamp}"}}],
            },
        })

    # Split content into paragraphs
    for paragraph in content.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            new_blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": paragraph}}],
                },
            })

    notion.blocks.children.append(block_id=page_id, children=new_blocks)
    return json.dumps({"success": True, "page_id": page_id, "content_added": content[:100] + "..."})


def _run_pipeline(command: str) -> str:
    import subprocess
    full_cmd = f"cd '{PROJECT_ROOT}' && python3 -m pipeline.{command}"
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
        if result.returncode != 0:
            error = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            return json.dumps({"success": False, "command": command, "output": output, "error": error})
        return json.dumps({"success": True, "command": command, "output": output})
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "command": command, "error": "Timed out after 120s"})


def _query_format_bank(format_name: str | None = None) -> str:
    body = {}
    if format_name:
        body["filter"] = {"property": "Format Name", "title": {"contains": format_name}}

    try:
        resp = notion.data_sources.query(data_source_id=FORMAT_BANK_DS_ID, **body)
    except Exception as e:
        return json.dumps({"error": str(e)})

    formats = []
    for page in resp.get("results", []):
        props = page["properties"]
        formats.append({
            "id": page["id"],
            "name": _get_title(props.get("Format Name", props.get("Name", {}))),
        })
    return json.dumps({"count": len(formats), "formats": formats})


def _query_monitor_list(platform: str | None = None) -> str:
    body = {}
    if platform:
        body["filter"] = {"property": "Platform", "select": {"equals": platform}}

    try:
        resp = notion.data_sources.query(data_source_id=MONITOR_LIST_DS_ID, **body)
    except Exception as e:
        return json.dumps({"error": str(e)})

    accounts = []
    for page in resp.get("results", []):
        props = page["properties"]
        accounts.append({
            "name": _get_title(props.get("Account Name", {})),
            "handle": _get_rich_text(props.get("Handle", {})),
            "platform": _get_select(props.get("Platform", {})),
            "tier": _get_select(props.get("Tier", {})),
            "status": _get_select(props.get("Status", {})),
        })
    return json.dumps({"count": len(accounts), "accounts": accounts})


# ── Typefully Analytics ────────────────────────────────────────────────────

def _get_analytics(days: int = 7, top_n: int = 5) -> str:
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    all_posts = []
    offset = 0
    while True:
        resp = requests.get(
            f"https://api.typefully.com/v2/social-sets/{TYPEFULLY_SOCIAL_SET_ID}/analytics/x/posts",
            headers={"Authorization": f"Bearer {TYPEFULLY_API_KEY}"},
            params={
                "start_date": start_date,
                "end_date": end_date,
                "limit": 100,
                "offset": offset,
                "include_replies": "false",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"Typefully API returned {resp.status_code}"})

        data = resp.json()
        results = data.get("results", [])
        all_posts.extend(results)
        if data.get("next") and len(results) == 100:
            offset += 100
        else:
            break

    if not all_posts:
        return json.dumps({"period": f"Last {days} days", "posts": 0, "note": "No analytics data available for this period"})

    total_imp = sum(p["metrics"]["impressions"] for p in all_posts)
    total_eng = sum(p["metrics"]["engagement"]["total"] for p in all_posts)
    total_likes = sum(p["metrics"]["engagement"]["likes"] for p in all_posts)
    total_saves = sum(p["metrics"]["engagement"]["saves"] for p in all_posts)
    total_clicks = sum(p["metrics"]["engagement"]["profile_clicks"] for p in all_posts)
    count = len(all_posts)

    top_posts = sorted(all_posts, key=lambda p: p["metrics"]["impressions"], reverse=True)[:top_n]
    top_list = []
    for p in top_posts:
        top_list.append({
            "impressions": p["metrics"]["impressions"],
            "engagement": p["metrics"]["engagement"]["total"],
            "saves": p["metrics"]["engagement"]["saves"],
            "preview": p["preview_text"][:150],
            "url": p.get("url", ""),
        })

    return json.dumps({
        "period": f"Last {days} days ({start_date} to {end_date})",
        "total_posts": count,
        "total_impressions": total_imp,
        "avg_impressions": round(total_imp / count),
        "total_engagement": total_eng,
        "engagement_rate": round(total_eng / total_imp * 100, 2) if total_imp else 0,
        "total_likes": total_likes,
        "total_saves": total_saves,
        "total_profile_clicks": total_clicks,
        "saves_per_post": round(total_saves / count, 1),
        "clicks_per_post": round(total_clicks / count, 1),
        "top_posts": top_list,
    })


# ── Performance Analyzer ───────────────────────────────────────────────────

def _fetch_typefully_posts(days: int) -> list[dict]:
    """Shared helper to pull Typefully analytics."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    all_posts = []
    offset = 0
    while True:
        resp = requests.get(
            f"https://api.typefully.com/v2/social-sets/{TYPEFULLY_SOCIAL_SET_ID}/analytics/x/posts",
            headers={"Authorization": f"Bearer {TYPEFULLY_API_KEY}"},
            params={"start_date": start_date, "end_date": end_date, "limit": 100, "offset": offset, "include_replies": "false"},
            timeout=30,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        results = data.get("results", [])
        all_posts.extend(results)
        if data.get("next") and len(results) == 100:
            offset += 100
        else:
            break
    return all_posts


def _analyze_performance(days: int = 30) -> str:
    posts = _fetch_typefully_posts(days)
    if not posts:
        return json.dumps({"error": "No analytics data available", "period": f"Last {days} days"})

    # Analyze by post length buckets
    short, medium, long_posts = [], [], []
    for p in posts:
        text_len = len(p.get("preview_text", ""))
        if text_len < 100:
            short.append(p)
        elif text_len < 280:
            medium.append(p)
        else:
            long_posts.append(p)

    def bucket_stats(bucket, name):
        if not bucket:
            return {"name": name, "count": 0}
        imp = [p["metrics"]["impressions"] for p in bucket]
        eng = [p["metrics"]["engagement"]["total"] for p in bucket]
        return {
            "name": name,
            "count": len(bucket),
            "avg_impressions": round(sum(imp) / len(imp)),
            "avg_engagement": round(sum(eng) / len(eng)),
            "median_impressions": sorted(imp)[len(imp) // 2],
        }

    # Top and bottom performers
    sorted_by_imp = sorted(posts, key=lambda p: p["metrics"]["impressions"], reverse=True)
    top_5 = [{
        "impressions": p["metrics"]["impressions"],
        "engagement": p["metrics"]["engagement"]["total"],
        "saves": p["metrics"]["engagement"]["saves"],
        "preview": p["preview_text"][:120],
        "url": p.get("url", ""),
    } for p in sorted_by_imp[:5]]

    bottom_5 = [{
        "impressions": p["metrics"]["impressions"],
        "engagement": p["metrics"]["engagement"]["total"],
        "preview": p["preview_text"][:120],
    } for p in sorted_by_imp[-5:]]

    # Hook analysis: first line patterns
    hook_patterns = {}
    for p in posts:
        first_line = p.get("preview_text", "").split("\n")[0][:50]
        # Classify hook type
        if first_line.startswith(("I'm ", "I ")):
            hook_type = "First person opener"
        elif "?" in first_line:
            hook_type = "Question hook"
        elif any(c.isdigit() for c in first_line):
            hook_type = "Number/stat hook"
        elif first_line.isupper() or first_line.startswith(("BREAKING", "THIS", "THE ")):
            hook_type = "Bold statement"
        elif ":" in first_line:
            hook_type = "Setup:reveal"
        else:
            hook_type = "Other"

        if hook_type not in hook_patterns:
            hook_patterns[hook_type] = {"count": 0, "total_imp": 0, "total_eng": 0}
        hook_patterns[hook_type]["count"] += 1
        hook_patterns[hook_type]["total_imp"] += p["metrics"]["impressions"]
        hook_patterns[hook_type]["total_eng"] += p["metrics"]["engagement"]["total"]

    hook_analysis = []
    for htype, data in hook_patterns.items():
        hook_analysis.append({
            "type": htype,
            "count": data["count"],
            "avg_impressions": round(data["total_imp"] / data["count"]),
            "avg_engagement": round(data["total_eng"] / data["count"]),
        })
    hook_analysis.sort(key=lambda x: x["avg_impressions"], reverse=True)

    # Save analysis
    total_imp = sum(p["metrics"]["impressions"] for p in posts)
    total_eng = sum(p["metrics"]["engagement"]["total"] for p in posts)

    return json.dumps({
        "period": f"Last {days} days",
        "total_posts": len(posts),
        "avg_impressions": round(total_imp / len(posts)),
        "avg_engagement": round(total_eng / len(posts)),
        "by_length": [bucket_stats(short, "Short (<100 chars)"), bucket_stats(medium, "Medium (100-280)"), bucket_stats(long_posts, "Long (280+)")],
        "by_hook_type": hook_analysis,
        "top_5_posts": top_5,
        "bottom_5_posts": bottom_5,
        "insight_ready": True,
    })


# ── Must-Haves Gate ────────────────────────────────────────────────────────

MUST_HAVES_PAGE_ID = "33404fca-1794-81d3-b8fb-ddd9cf2cc998"

GATE_CHECK_PROMPT = """You are a strict quality gate for GeniusGTX content experiments.

Review the following post against EVERY must-have rule below. Be ruthless — if it fails ANY rule, it fails the gate.

MUST-HAVES:

VOICE: Systems thinker (never moralizes), incentive-first, ownership vs participation lens, calibrated urgency (no doom/hype), contrarian by method not identity, reader is smart, exit feeling = world more legible + one actionable thing, conviction on AI/wealth/power, analytical on geopolitics, advice as individual ownership.

FORMATTING: One paragraph per line with blank lines, max 2 sentences per paragraph, NO em dashes, one idea per paragraph, hook within 280 chars, max ~25 paragraphs.

HOOKS: Angle passes visualization test, passes unexpected association + primal trigger test, one sentence per line, exactly one pivot phrase, pivot verbs from approved list only, absolute superlatives, exact numbers, speed reveals use 'just', adversarial verbs active+named, max 2-3 narrator phrases, lead with the gap.

QUALITY: No banned AI words (delve/tapestry/nuanced/pivotal/groundbreaking/etc), no banned openers, no filler transitions (Furthermore/Moreover/etc), no hedging, no sycophantic openers, no false balance, no motivational pivot, no rhetorical question headers, no list-as-prose, no explaining what you just said, no vague transitions, varied rhythm, must fail "could generic AI write this?" test, must end with crystallized one-liner, quotes never open cold, default half the "complete" length.

BRAND: Never cynical/nihilistic, never breathless, never preachy, no bullet-point prose, CTA never transactional, identity = "gallery for greatest minds", contrarian must be defensible, no guru energy, advice as ownership not activism.

POST TO REVIEW:
{post_text}

Respond in EXACTLY this format:
PASS: yes/no
FAILURES: [list each failed rule, or "none"]
SEVERITY: [critical/minor/none]
SUGGESTION: [one-line fix if failed, or "none"]"""


def _gate_check(post_text: str) -> dict:
    """Run a post through the must-haves gate. Returns pass/fail with details."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": GATE_CHECK_PROMPT.format(post_text=post_text)}],
    )
    result_text = response.content[0].text

    passed = "PASS: yes" in result_text.lower() or "pass: yes" in result_text
    failures = []
    suggestion = ""

    for line in result_text.split("\n"):
        if line.startswith("FAILURES:"):
            failures_text = line.replace("FAILURES:", "").strip()
            if failures_text.lower() != "none" and failures_text != "[]":
                failures = [f.strip() for f in failures_text.split(",") if f.strip()]
        if line.startswith("SUGGESTION:"):
            suggestion = line.replace("SUGGESTION:", "").strip()

    return {
        "passed": passed,
        "failures": failures,
        "suggestion": suggestion,
        "raw": result_text,
    }


# ── A/B Testing (with Gate Check) ─────────────────────────────────────────

def _ab_test(topic: str, hypothesis: str, area: str, variation_b_instruction: str) -> str:
    """Generate two variations, gate-check both, log experiment to Notion."""

    # Step 1: Generate both variations
    variation_prompt = f"""You are writing content for GeniusGTX (@GeniusGTX_2), a content account on X/Twitter.

Voice: Systems thinker. Diagnose mechanisms, never moralize. Incentive-first. Calibrated urgency. Direct, sharp, educational.
Topics: ancient civilizations, systemic shifts, hidden figures, cognitive science, business strategy, geopolitics.
Rules: One sentence per line. No em dashes. Max 2 sentences per paragraph. No banned AI words (delve, tapestry, nuanced, pivotal, etc). Lead hooks with the gap between assumption and reality. End with a crystallized one-liner.

Topic: {topic}

Write TWO variations of a post about this topic.

**Variation A (Control):** Standard GeniusGTX voice. Follow all rules exactly.

**Variation B (Experiment):** Same topic, same rules, but with this specific change: {variation_b_instruction}

Both variations must follow ALL GeniusGTX voice and formatting rules. The only difference should be the experimental change.

Format your response EXACTLY as:
VARIATION_A:
[the post text]

VARIATION_B:
[the post text]"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": variation_prompt}],
    )
    text = response.content[0].text

    var_a = ""
    var_b = ""
    if "VARIATION_A:" in text and "VARIATION_B:" in text:
        parts = text.split("VARIATION_B:")
        var_a = parts[0].replace("VARIATION_A:", "").strip()
        var_b = parts[1].strip()
    else:
        var_a = text[:len(text) // 2]
        var_b = text[len(text) // 2:]

    # Step 2: Gate check both variations
    gate_a = _gate_check(var_a)
    gate_b = _gate_check(var_b)

    gate_summary = {
        "variation_a": {"passed": gate_a["passed"], "failures": gate_a["failures"]},
        "variation_b": {"passed": gate_b["passed"], "failures": gate_b["failures"]},
    }

    # Step 3: If variation B fails gate, flag it
    b_failed_gate = not gate_b["passed"]
    status = "Awaiting Review"
    gate_note = ""

    if b_failed_gate and gate_b["failures"]:
        gate_note = f"⚠️ Variation B failed gate check: {', '.join(gate_b['failures'][:3])}"
        if gate_b.get("suggestion") and gate_b["suggestion"] != "none":
            gate_note += f"\nSuggestion: {gate_b['suggestion']}"

    # Step 4: Log to Notion
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        page = notion.pages.create(
            parent={"database_id": EXPERIMENTS_DB_PAGE_ID},
            properties={
                "Experiment": {"title": [{"text": {"content": f"A/B: {topic[:80]}"}}]},
                "Area": {"select": {"name": area}},
                "Status": {"select": {"name": status}},
                "Hypothesis": {"rich_text": [{"text": {"content": hypothesis}}]},
                "Variation A": {"rich_text": [{"text": {"content": var_a[:2000]}}]},
                "Variation B": {"rich_text": [{"text": {"content": var_b[:2000]}}]},
                "Started": {"date": {"start": today}},
            },
        )
        experiment_id = page["id"]
    except Exception as e:
        experiment_id = None

    result = {
        "experiment_id": experiment_id,
        "hypothesis": hypothesis,
        "area": area,
        "variation_a": var_a,
        "variation_b": var_b,
        "gate_check": gate_summary,
    }

    if b_failed_gate:
        result["gate_warning"] = gate_note
        result["status"] = f"Variation B flagged — {gate_note}. Still showing both for your review."
    else:
        result["status"] = "Both variations passed the must-haves gate. Which do you prefer — A, B, or Neither?"

    return json.dumps(result)


def _log_experiment_result(experiment_id: str, user_pick: str, feedback: str, status: str) -> str:
    """Update experiment in Notion with result."""
    today = datetime.now().strftime("%Y-%m-%d")
    properties = {
        "User Pick": {"select": {"name": user_pick}},
        "Feedback": {"rich_text": [{"text": {"content": feedback}}]},
        "Status": {"select": {"name": status}},
        "Completed": {"date": {"start": today}},
    }
    notion.pages.update(page_id=experiment_id, properties=properties)

    # Also save as memory if kept
    if status == "Kept":
        _save_memory(
            f"experiment_{today}",
            f"Kept experiment: {feedback}. User preferred variation {user_pick}.",
        )

    return json.dumps({"success": True, "experiment_id": experiment_id, "status": status})


def _get_experiments(status: str | None = None, limit: int = 5) -> str:
    body = {"page_size": min(limit, 20)}
    if status:
        body["filter"] = {"property": "Status", "select": {"equals": status}}
    body["sorts"] = [{"property": "Started", "direction": "descending"}]

    try:
        resp = notion.data_sources.query(data_source_id=EXPERIMENTS_DS_ID, **body)
    except Exception as e:
        return json.dumps({"error": str(e)})

    experiments = []
    for page in resp.get("results", []):
        props = page["properties"]
        experiments.append({
            "id": page["id"],
            "name": _get_title(props.get("Experiment", {})),
            "area": _get_select(props.get("Area", {})),
            "status": _get_select(props.get("Status", {})),
            "hypothesis": _get_rich_text(props.get("Hypothesis", {})),
            "user_pick": _get_select(props.get("User Pick", {})),
            "feedback": _get_rich_text(props.get("Feedback", {})),
        })
    return json.dumps({"count": len(experiments), "experiments": experiments})


# ── Web Research ───────────────────────────────────────────────────────────

def _web_research(query: str, max_results: int = 5) -> str:
    if not TAVILY_API_KEY:
        return json.dumps({"error": "TAVILY_API_KEY not set in .env"})

    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "include_answer": True,
            "search_depth": "advanced",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return json.dumps({"error": f"Tavily returned {resp.status_code}"})

    data = resp.json()
    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:300],
        })

    return json.dumps({
        "query": query,
        "answer": data.get("answer", ""),
        "results": results,
    })


# ── Image Analysis ─────────────────────────────────────────────────────────

def _analyze_image(image_source: str, instruction: str) -> str:
    """Analyze an image using Claude's vision capability."""
    import base64

    content_blocks = []

    if image_source.startswith(("http://", "https://")):
        # URL-based image
        content_blocks.append({
            "type": "image",
            "source": {"type": "url", "url": image_source},
        })
    elif os.path.exists(image_source):
        # Local file — encode as base64
        with open(image_source, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
        ext = image_source.rsplit(".", 1)[-1].lower()
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_data},
        })
    else:
        return json.dumps({"error": f"Cannot access image: {image_source}"})

    content_blocks.append({
        "type": "text",
        "text": f"""You are the CEO agent for GeniusGTX, analyzing content for a high-performance X/Twitter account.

{instruction}

If this is a tweet or social media post:
1. Break down why it works (or doesn't): hook, structure, emotional trigger, topic
2. Identify the pattern that could be replicated
3. Propose a GeniusGTX version — same pattern, our voice (systems thinker, incentive-first, no em dashes, one sentence per line)
4. Suggest which format it maps to (Tuki QRT, Thread, Stat Bomb, Explainer, etc.)

If it's something else, describe what you see and how it could inform our content strategy.""",
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": content_blocks}],
    )
    return json.dumps({"analysis": response.content[0].text})


# ── Persistent Memory ──────────────────────────────────────────────────────

def _load_memory() -> dict:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {}


def _save_memory_to_disk(memory: dict):
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_memory(key: str, content: str) -> str:
    memory = _load_memory()
    memory[key] = {
        "content": content,
        "saved_at": datetime.now().isoformat(),
    }
    _save_memory_to_disk(memory)
    return json.dumps({"success": True, "key": key, "total_memories": len(memory)})


def _recall_memories() -> str:
    memory = _load_memory()
    if not memory:
        return json.dumps({"memories": [], "note": "No memories saved yet."})
    items = []
    for key, val in memory.items():
        items.append({
            "key": key,
            "content": val["content"],
            "saved": val.get("saved_at", "unknown"),
        })
    return json.dumps({"memories": items})


def get_memory_context() -> str:
    """Load memories as context string for the system prompt. Called at chat time."""
    memory = _load_memory()
    if not memory:
        return ""
    parts = ["## Remembered Context (from past conversations)"]
    for key, val in memory.items():
        parts.append(f"- **{key}**: {val['content']} (saved {val.get('saved_at', 'unknown')[:10]})")
    return "\n".join(parts)


# ── Habits Tracker ─────────────────────────────────────────────────────────

def _habits_status() -> str:
    from agents.ceo.habits import get_today_status, get_today_score, NON_NEGOTIABLES, get_streak
    status = get_today_status()
    done, total = get_today_score()
    streak = get_streak()
    items = []
    for h in NON_NEGOTIABLES:
        check = "done" if status.get(h["id"], False) else "pending"
        items.append({"id": h["id"], "name": h["short"], "status": check})
    return json.dumps({"score": f"{done}/{total}", "streak": streak, "habits": items})


def _habits_complete(habit_id: str) -> str:
    from agents.ceo.habits import mark_complete, get_today_score, NON_NEGOTIABLES
    success = mark_complete(habit_id)
    if not success:
        return json.dumps({"error": f"Unknown habit: {habit_id}"})
    done, total = get_today_score()
    name = next((h["short"] for h in NON_NEGOTIABLES if h["id"] == habit_id), habit_id)
    return json.dumps({"success": True, "marked": name, "score": f"{done}/{total}"})


def _habits_week() -> str:
    from agents.ceo.habits import get_week_summary, format_weekly_summary
    return json.dumps({"summary": format_weekly_summary()})


# ── Conversation Engine ────────────────────────────────────────────────────

def chat(message: str, conversation_history: list | None = None) -> tuple[str, list]:
    """
    Process a message with tool use. Returns (response_text, updated_history).

    The conversation_history is a list of message dicts for Claude's messages API.
    """
    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": message})

    # Inject persistent memories into system prompt
    memory_ctx = get_memory_context()
    full_system = SYSTEM_PROMPT + ("\n\n" + memory_ctx if memory_ctx else "")

    # Tool use loop
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=full_system,
            messages=messages,
            tools=TOOLS,
        )

        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Add assistant message with tool calls
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
            # Loop back for Claude to process tool results

        else:
            # Final response — extract text
            messages.append({"role": "assistant", "content": response.content})
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            return text, messages
