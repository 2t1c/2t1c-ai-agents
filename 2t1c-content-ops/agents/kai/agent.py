"""
Kai — Research Lead Agent for GeniusGTX (Standalone)

Autonomous research agent that:
1. Scans trending sources via Tavily search
2. Evaluates ideas against Two-Signal Framework + Qualitative Filter
3. Runs 8-Angle Enrichment Routine on qualifying ideas
4. Creates Notion Idea Pipeline entries with Extraction Plans + Content Maps

Uses Anthropic tool_use API — no Paperclip dependency.

Usage:
    python -m agents.kai.agent --scan              # one research sweep
    python -m agents.kai.agent --scan --topic "AI"  # focused sweep
    python -m agents.kai.agent --poll               # continuous scanning
    python -m agents.kai.agent --enrich --idea-id <id>  # enrich existing idea
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from tools.notion_client import (
    get_triggered_ideas_with_plans,
    get_idea_by_id_full,
    update_idea_status,
)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
IDEA_PIPELINE_DB_ID = os.getenv("NOTION_IDEA_PIPELINE_DB_ID", "c4fed84b-f0a9-4459-bad3-69c93f3de40a")

POLL_INTERVAL_SECONDS = 1800  # 30 minutes
SCAN_TOPICS = [
    "AI artificial intelligence breakthrough",
    "finance economics market",
    "geopolitics trade policy",
    "business strategy startup",
    "psychology cognitive science research",
    "technology innovation",
]


# ---------------------------------------------------------------------------
# Tool definitions for Anthropic tool_use
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "tavily_search",
        "description": "Search the web for recent news, articles, and trending topics. Returns relevant results with snippets. Use this to find trending stories and source material.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific for better results.",
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": "Search depth. Use 'advanced' for comprehensive research.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10).",
                    "default": 5,
                },
                "days": {
                    "type": "integer",
                    "description": "Only return results from the last N days.",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "tavily_extract",
        "description": "Extract the full content of a web page given its URL. Use this to read full articles after finding them via search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to extract content from (max 5).",
                },
            },
            "required": ["urls"],
        },
    },
    {
        "name": "notion_create_idea",
        "description": "Create a new entry in the Notion Idea Pipeline database. Use this after evaluating an idea and completing the 8-Angle Enrichment Routine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "One-line idea description.",
                },
                "source_url": {
                    "type": "string",
                    "description": "Exact URL to the source content.",
                },
                "source_type": {
                    "type": "string",
                    "enum": ["YouTube", "Twitter", "Articles"],
                    "description": "Type of source.",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["🔴 Breaking", "🟡 Trending", "🟢 Evergreen"],
                    "description": "Urgency level based on story age and momentum.",
                },
                "content_angle": {
                    "type": "string",
                    "description": "Primary angle one-liner (whichever ranks #1 in Priority Order).",
                },
                "topic_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topic tags (e.g., AI, Finance, Geopolitics).",
                },
                "assigned_formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ALL formats identified across all applicable angles.",
                },
                "extraction_plan": {
                    "type": "string",
                    "description": "Full structured output from the 8-Angle Enrichment Routine.",
                },
                "content_map": {
                    "type": "string",
                    "description": "Full time schedule output (T+0 through T+Day 5-7).",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context or notes about the idea.",
                },
                "source_account": {
                    "type": "string",
                    "description": "@handle or channel name of the source.",
                },
            },
            "required": ["title", "source_url", "source_type", "urgency", "content_angle", "assigned_formats", "extraction_plan", "content_map"],
        },
    },
    {
        "name": "notion_query_ideas",
        "description": "Query the Idea Pipeline to check for existing ideas (avoid duplicates). Returns recent ideas matching a search term.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_text": {
                    "type": "string",
                    "description": "Text to search for in idea titles.",
                },
            },
            "required": ["search_text"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a string."""

    if tool_name == "tavily_search":
        return _tavily_search(tool_input)
    elif tool_name == "tavily_extract":
        return _tavily_extract(tool_input)
    elif tool_name == "notion_create_idea":
        return _notion_create_idea(tool_input)
    elif tool_name == "notion_query_ideas":
        return _notion_query_ideas(tool_input)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _tavily_search(params: dict) -> str:
    """Execute a Tavily web search."""
    if not TAVILY_API_KEY:
        return json.dumps({"error": "TAVILY_API_KEY not set in .env"})

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": params["query"],
                "search_depth": params.get("search_depth", "basic"),
                "max_results": min(params.get("max_results", 5), 10),
                "days": params.get("days", 3),
                "include_answer": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # Slim down for context window
        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
                "published_date": r.get("published_date", ""),
            })

        return json.dumps({
            "answer": data.get("answer", ""),
            "results": results,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Tavily search failed: {str(e)}"})


def _tavily_extract(params: dict) -> str:
    """Extract content from URLs via Tavily."""
    if not TAVILY_API_KEY:
        return json.dumps({"error": "TAVILY_API_KEY not set in .env"})

    try:
        urls = params.get("urls", [])[:5]
        resp = requests.post(
            "https://api.tavily.com/extract",
            json={
                "api_key": TAVILY_API_KEY,
                "urls": urls,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append({
                "url": r.get("url", ""),
                "raw_content": r.get("raw_content", "")[:3000],
            })

        return json.dumps({"results": results}, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Tavily extract failed: {str(e)}"})


def _notion_create_idea(params: dict) -> str:
    """Create a Notion Idea Pipeline entry."""
    from notion_client import Client
    notion = Client(auth=NOTION_API_KEY)

    properties = {
        "Idea": {"title": [{"text": {"content": params["title"]}}]},
        "Status": {"select": {"name": "Triggered"}},
        "Source URL": {"url": params["source_url"]},
        "Source Type": {"select": {"name": params["source_type"]}},
        "Urgency": {"select": {"name": params["urgency"]}},
        "Content Angle": {"rich_text": [{"text": {"content": params["content_angle"]}}]},
        "Extraction Plan": {"rich_text": [{"text": {"content": params["extraction_plan"][:2000]}}]},
        "Content Map": {"rich_text": [{"text": {"content": params["content_map"][:2000]}}]},
    }

    if params.get("assigned_formats"):
        properties["Assigned Formats"] = {
            "multi_select": [{"name": f} for f in params["assigned_formats"]]
        }
    if params.get("topic_tags"):
        properties["Topic Tags"] = {
            "multi_select": [{"name": t} for t in params["topic_tags"]]
        }
    if params.get("notes"):
        properties["Notes"] = {"rich_text": [{"text": {"content": params["notes"][:2000]}}]}
    if params.get("source_account"):
        properties["Source Account"] = {"rich_text": [{"text": {"content": params["source_account"]}}]}

    try:
        page = notion.pages.create(
            parent={"database_id": IDEA_PIPELINE_DB_ID},
            properties=properties,
        )
        return json.dumps({
            "success": True,
            "page_id": page["id"],
            "title": params["title"],
            "url": f"https://www.notion.so/{page['id'].replace('-', '')}",
        })
    except Exception as e:
        return json.dumps({"error": f"Notion create failed: {str(e)}"})


def _notion_query_ideas(params: dict) -> str:
    """Query Notion Idea Pipeline for existing ideas (duplicate check)."""
    try:
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{IDEA_PIPELINE_DB_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "filter": {
                    "property": "Idea",
                    "title": {"contains": params["search_text"]},
                },
                "page_size": 10,
            },
            timeout=30,
        )
        resp.raise_for_status()
        response = resp.json()

        results = []
        for page in response.get("results", []):
            props = page["properties"]
            title_items = props.get("Idea", {}).get("title", [])
            title = title_items[0]["plain_text"] if title_items else ""
            status = props.get("Status", {}).get("select", {})
            results.append({
                "id": page["id"],
                "title": title,
                "status": status.get("name", "") if status else "",
            })

        return json.dumps({"count": len(results), "ideas": results}, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Notion query failed: {str(e)}"})


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Build Kai's full system prompt with the research framework."""
    return f"""You are Kai, the Research Lead at GeniusGTX. You find the ideas that become content.

APPROVAL RULE: ALL content goes through Toản. No auto-publishing. Every idea you create goes into Notion as "Triggered" for pipeline processing.

## Your Job
1. Research trending topics across AI, finance, geopolitics, business, psychology
2. Evaluate ideas against the Two-Signal Framework and Qualitative Filter
3. For every qualifying idea: run the 8-Angle Enrichment Routine
4. Create the Notion Idea Pipeline entry with the full Extraction Plan and Content Map
5. Set status to "Triggered" so the writing pipeline begins

## Two-Signal Framework (BOTH must pass)
**Signal 1 — Momentum:** Evidence of audience resonance (view counts, multiple sources covering same story)
**Signal 2 — Angle:** Can we add value the original doesn't have?

## Qualitative Filter (minimum 3 of 7)
1. Celebrity factor — recognizable name?
2. Surprise factor — counterintuitive or shocking?
3. Number density — specific, shareable data points?
4. Emotional trigger — outrage, awe, fear, inspiration?
5. Debate potential — would people argue in replies?
6. Personal impact — affects reader's life/money/career?
7. Pattern recognition — connects to a larger trend?

## Urgency Tagging
- 🔴 Breaking: story < 3 hours old, high momentum
- 🟡 Trending: story < 24 hours, strong momentum
- 🟢 Evergreen: proven content, no time pressure

## Hard Exclusions (NEVER create ideas about)
- Direct war/conflict coverage as primary topic
- Pure crypto/blockchain (unless massive mainstream crossover)
- Off-niche topics outside content territories

## Content Territories
AI, Finance, Geopolitics, Business, Psychology, Philosophy, Marketing, Tech, History

## 8-Angle Enrichment Routine

Evaluate all 8 angles against the source:

| # | Angle | What It Asks |
|---|---|---|
| 1 | Straight | What happened / what was said |
| 2 | Systems lens | What mechanism explains why this happened |
| 3 | Contrarian | Why the common take is wrong |
| 4 | Historical pattern | When did this exact thing happen before |
| 5 | Human impact | What this means for the reader's life, money, or career |
| 6 | Ownership | Who captures the value vs. who operates inside it |
| 7 | Institutional failure | How a system enabled or caused this |
| 8 | Early signal | What this predicts is coming next |

## Angle → Format Mapping

| Angle | Best-fit Formats |
|---|---|
| Straight | Tuki QRT, Bark QRT, Stat Bomb |
| Systems lens | Thread, Explainer, Multi-Source Explainer |
| Contrarian | Contrarian Take, Commentary Post |
| Historical pattern | Thread, Explainer |
| Human impact | Stat Bomb, Commentary Post, Explainer |
| Ownership | Stat Bomb, Thread, Contrarian Take |
| Institutional failure | Commentary Post, Thread, Contrarian Take |
| Early signal | Commentary Post, Contrarian Take |

## Priority Order by Urgency
- 🔴 Breaking: Straight → Human impact → Systems/Contrarian/Historical
- 🟡 Trending: Human impact → Contrarian/Systems → Historical
- 🟢 Evergreen: Rank by strongest angles for this story

## Extraction Plan Output Format
```
SOURCE TYPE: [Tweet / Article / Podcast / YouTube]
URGENCY: [🔴 Breaking / 🟡 Trending / 🟢 Evergreen]

ANGLE EXTRACTION:
1. Straight: [brief] → Format: [format]
2. Systems lens: [brief] → Format: [format]
...
PRIORITY ORDER: [e.g., 1, 5, 6, 2, 3, 8]
TOTAL POSTS: [N]
```

## Content Map Output Format
```
CONTENT MAP — [Idea Title]
Source: [URL]
Total: [N] posts

T+0: [Format] — [Angle] — [description]
T+Same day: [Format] — [Angle] — [description]
T+Day 1: [Format] — [Angle] — [description]
T+Day 2-3: [Format] — [Angle] — [description]
T+Day 5-7: [Format] — [Angle] — [description]
```

## Workflow
1. Use tavily_search to find trending stories
2. For each promising story, use tavily_extract to get full content
3. Use notion_query_ideas to check for duplicates
4. Evaluate against Two-Signal Framework + Qualitative Filter
5. For qualifying ideas, run the 8-Angle Enrichment Routine
6. Use notion_create_idea to create the pipeline entry

IMPORTANT: Always search for duplicates before creating. Quality over quantity — only create ideas that genuinely pass both signals and the qualitative filter.

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agent(user_message: str, max_turns: int = 25) -> str:
    """
    Run Kai's agentic loop. Sends a message, processes tool calls,
    and continues until Kai produces a final text response.
    """
    system_prompt = build_system_prompt()
    messages = [{"role": "user", "content": user_message}]

    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Check if there are tool calls
        tool_calls = [block for block in response.content if block.type == "tool_use"]
        text_blocks = [block for block in response.content if block.type == "text"]

        if not tool_calls:
            # No more tool calls — return the final text
            return "\n".join(block.text for block in text_blocks)

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_call in tool_calls:
            print(f"    [Kai] Tool: {tool_call.name}({json.dumps(tool_call.input)[:100]}...)")
            result = execute_tool(tool_call.name, tool_call.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

        # Print any text blocks from this turn
        for block in text_blocks:
            if block.text.strip():
                print(f"    [Kai] {block.text[:200]}")

    return "Max turns reached. Kai may need a longer context for this task."


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def scan(topic: str | None = None):
    """Run a single research sweep."""
    if topic:
        prompt = f"""Run a focused research sweep on: {topic}

Search for the latest trending stories, evaluate each against the Two-Signal Framework and Qualitative Filter, and create Notion entries for any qualifying ideas with full Extraction Plans and Content Maps.

Before creating any idea, check for duplicates in Notion first."""
    else:
        prompt = f"""Run a full research sweep across all content territories: AI, Finance, Geopolitics, Business, Psychology, Tech.

For each territory, search for the latest trending stories (last 2-3 days). Evaluate each against the Two-Signal Framework and Qualitative Filter. Create Notion entries for qualifying ideas with full Extraction Plans and Content Maps.

Aim for quality — only create entries for ideas that genuinely pass both signals. Check for duplicates before creating.

Today's topics to scan: {', '.join(SCAN_TOPICS)}"""

    print(f"\n{'='*60}")
    print(f"KAI — Research Sweep {'(' + topic + ')' if topic else '(full)'}")
    print(f"{'='*60}")

    result = run_agent(prompt)
    print(f"\n--- Kai's Summary ---\n{result}")
    return result


def enrich_idea(idea_id: str):
    """Enrich an existing idea with 8-Angle Extraction Plan."""
    idea = get_idea_by_id_full(idea_id)
    if not idea:
        print(f"Idea {idea_id} not found.")
        return

    if idea.get("extraction_plan"):
        print(f"Idea already has an Extraction Plan. Skipping.")
        return

    prompt = f"""An idea already exists in the pipeline but needs enrichment:

Title: {idea['idea']}
Source URL: {idea.get('source_url', 'none')}
Source Account: {idea.get('source_account', 'none')}
Urgency: {idea.get('urgency', 'unknown')}
Notes: {idea.get('notes', 'none')}

1. Use tavily_extract to read the full source content
2. Run the full 8-Angle Enrichment Routine
3. Generate the Extraction Plan and Content Map
4. Create a NEW Notion entry with the full enrichment (the pipeline will pick it up)

Do NOT modify the existing entry — create a fresh one with the complete data."""

    print(f"\n--- Enriching: {idea['idea'][:60]} ---")
    result = run_agent(prompt)
    print(f"\n--- Done ---\n{result}")
    return result


def run_poll(topic: str | None = None):
    """Continuously scan for new ideas."""
    print(f"Kai — polling every {POLL_INTERVAL_SECONDS // 60} minutes")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            scan(topic=topic)
            print(f"\n[POLL] Sleeping {POLL_INTERVAL_SECONDS // 60}m...")
            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nKai stopped.")
            break
        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Kai — GeniusGTX Research Lead Agent")
    parser.add_argument("--scan", action="store_true", help="Run one research sweep")
    parser.add_argument("--topic", type=str, help="Focus sweep on a specific topic")
    parser.add_argument("--enrich", action="store_true", help="Enrich an existing idea")
    parser.add_argument("--idea-id", type=str, help="Idea ID for --enrich mode")
    parser.add_argument("--poll", action="store_true", help="Continuously scan for new ideas")
    args = parser.parse_args()

    if args.enrich and args.idea_id:
        enrich_idea(args.idea_id)
    elif args.scan or args.topic:
        scan(topic=args.topic)
    elif args.poll:
        run_poll(topic=args.topic)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
