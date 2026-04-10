---
name: notion-paperclip-sync
description: >
  Daily sync between Notion (source of truth) and Paperclip agent configuration.
  Triggered when: told to "sync Notion to Paperclip", "update agent config",
  "sync knowledge base", or automatically via daily routine.
  Notion is ALWAYS the source of truth. Changes flow: Notion → Paperclip, never reverse.
---

# Notion → Paperclip Sync

Notion is the single source of truth for all content operations knowledge.
This skill ensures Paperclip agents stay aligned with the latest Notion content.

## Direction: ONE WAY ONLY

```
Notion (source of truth) → Paperclip (consumer)
```

Never write back to Notion from this sync. If something in Paperclip conflicts
with Notion, Notion wins. Always.

## What Gets Synced

### 1. Content Operations Knowledge Base
Read these Notion pages and update the corresponding agent instructions:

| Notion Page | What It Contains | Update Target |
|-------------|-----------------|---------------|
| Media Workflow Guide (33004fca179481e3bd37d73e13b82d25) | GIF/clip/media rules | Maya + Jordan instructions |
| Writing Style Guide (33004fca-1794-81f9-b85c-de9132b145b6) | Voice, tone, format rules | Maya writing-system skill |
| Content Formats (check Content Operations parent page) | 11 format definitions | All agent instructions |
| Idea Pipeline DB (330aef7b-3feb-401e-abba-28452441a64d) | Active ideas, statuses | Kai + Maya task context |

### 2. Agent Instructions
Compare each agent's AGENTS.md against the current Notion knowledge base.
If Notion has new formats, new rules, or updated workflows, update the
corresponding agent instructions at:
```
~/.paperclip/instances/default/companies/COMPANY_ID/agents/AGENT_ID/instructions/AGENTS.md
```

### 3. Skills Content
Check if any skill SKILL.md files reference outdated information vs Notion.
Update the skill content in:
```
~/.paperclip/instances/default/skills/COMPANY_ID/SKILL_NAME/SKILL.md
```

## Sync Process

### Phase 1: Read Notion State
1. Fetch the Content Operations parent page and all children
2. Fetch the Media Workflow Guide
3. Fetch the Writing Style Guide
4. Fetch the Idea Pipeline DB schema (check for new properties)
5. Note any changes since last sync (check updated_at timestamps)

### Phase 2: Compare Against Paperclip
1. Read each agent's current AGENTS.md
2. Read each skill's current SKILL.md
3. Identify gaps: Notion has information that Paperclip agents don't know about

### Phase 3: Update Paperclip
1. Update agent instructions with new knowledge
2. Update skill files with new rules/workflows
3. Log what changed in `sync_log.md`

### Phase 4: Verify
1. Confirm all agent instruction files are valid
2. Confirm all skill files have correct YAML frontmatter
3. Report summary of changes

## Sync Log

Append to `/Users/toantruong/Desktop/AI Agents/2t1c-content-ops/sync_log.md`:

```
## [DATE] Daily Sync
- Notion pages checked: [count]
- Changes detected: [list]
- Agent instructions updated: [list]
- Skills updated: [list]
- No changes needed: [list]
```

## What NOT to Sync
- Idea Pipeline content (individual ideas) — agents read these in real-time via Notion MCP
- Draft content — lives in Typefully
- Analytics data — pulled live from Typefully
- Revenue data — pulled live from Stripe
- Agent runtime state (status, heartbeat, budget) — managed by Paperclip

## Conflict Resolution
If Paperclip has a custom instruction that contradicts Notion:
1. Log the conflict
2. Keep the Notion version
3. Note in sync_log.md what was overwritten and why
