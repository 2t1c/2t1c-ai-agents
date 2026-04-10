# Remove All Tags from Typefully Drafts

Strip all tags from every draft on Typefully for social set 151393. Notion is now the single source of truth for status tracking.

## Steps

1. List ALL drafts (status: draft, scheduled) using:
   ```
   typefully_list_drafts(social_set_id: 151393, limit: 50)
   ```
   Paginate with offset until you've fetched all drafts.

2. For each draft that has tags, update it to remove all tags:
   ```
   typefully_edit_draft(social_set_id: 151393, draft_id: <id>, tags: [])
   ```

3. Report how many drafts were cleaned.

Do NOT delete any drafts. Do NOT modify any content. Only remove tags.
