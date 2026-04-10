# Iterate on Scheduled Task Prompts

You are helping redesign the 5 scheduled task prompts for the GeniusGTX content pipeline. The tasks run as Claude Code scheduled agents on Anthropic's cloud with Notion + Typefully MCP access.

## Context

Read these files to understand the full system:

1. **The 5 draft prompts** (iterate on these):
   - `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/prompts/scheduled-tasks/task1-ideation.md`
   - `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/prompts/scheduled-tasks/task2-writer.md`
   - `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/prompts/scheduled-tasks/task3-media-attacher.md`
   - `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/prompts/scheduled-tasks/task4-scheduler.md`
   - `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/prompts/scheduled-tasks/task5-tracker.md`

2. **The writing rules** (source of truth for how posts are written):
   - Notion page: fetch `33004fca-1794-81f9-b85c-de9132b145b6` (Writing Style Guide)
   - Notion page: fetch `33004fca-1794-81cd-a1de-c88ca30837cc` (Hook Writing Guide)

3. **The Notion database schema** (what properties exist):
   - Fetch the Idea Pipeline: `collection://330aef7b-3feb-401e-abba-28452441a64d`

4. **Existing scheduled tasks** (reference for how they're structured):
   - List remote triggers to see what's already running
   - If there's an existing ideation task, read its prompt and incorporate its approach

5. **The plan** (what we're building toward):
   - `/Users/toantruong/.claude/plans/temporal-watching-tarjan.md`

## What to do

Work through each of the 5 task prompts with the user. For each one:

1. Read the current draft prompt
2. Read the relevant Notion docs (writing guide, hook guide, database schema)
3. Identify gaps or improvements, specifically:
   - **Task 1 (Ideation):** Should also search Twitter/X for viral tweets as sources, not just Tavily web search. Use the approach from any existing ideation task we already have.
   - **Task 2 (Writer):** Needs more specific hook writing guidance — use insights from the Hook Writing Guide. Prioritize direct quotes in quotation marks from sources. Be more explicit about the hook anatomy (opener types, pivot phrases, emotional triggers).
   - **Task 3 (Media):** QRT fallback for article sources. Clip extraction flow.
   - **Task 4 (Scheduler):** Time slot logic.
   - **Task 5 (Tracker):** Published status sync + killed draft cleanup.
4. Present the improved version to the user for feedback
5. Once approved, save the updated prompt

## Key requirements from the user

- QRT-first strategy: every post should try to QRT a trending tweet
- Hooks should use Jordan's hook writing system (angle finding, visualization test, pivot phrases)
- Prioritize direct quotes from sources in quotation marks
- Notion is the single source of truth — no Typefully tags
- Each prompt must be self-contained (no file reads at runtime — embed all rules directly)
- Format detection is automatic: Twitter source → Tuki QRT, everything else → Long-Form Post

## Output

Updated task prompt files saved to the same locations. Each prompt should be ready to paste directly into claude.ai/code/scheduled as a scheduled task.
