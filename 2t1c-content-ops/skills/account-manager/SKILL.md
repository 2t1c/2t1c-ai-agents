# Account Manager Scheduling Skill

**Purpose:** Schedules "Ready to Post" content from GeniusGTX's Notion pipeline to Typefully with intelligent timing that respects velocity rules, anti-repetition logic, and content urgency levels.

## What This Skill Does

Reads scheduled-for-posting items from:
- **Notion Idea Pipeline** (status: "Ready for Review" or "Approved")
- **Long-Form Post Library** (status: "Ready to Schedule")

Then schedules each post to Typefully (@GeniusGTX_2, Social Set 151393) following:
1. **Velocity rules** (max posts/day, spacing, format limits)
2. **Anti-repetition logic** (no same-idea within 3hrs, format variety)
3. **Content staggering** (breaking/trending/evergreen timing)
4. **Approval enforcement** (never auto-publish, always draft)

## Velocity Rules

**Daily Maximums:**
- 5-8 posts total per day
- Max 3 QRTs per day (Tuki + Bark formats)
- Max 2 long-form per day (Thread, Explainer, Educational)
- All others (Stats Bomb, Commentary, Contrarian, etc.) fill remaining slots

**Spacing:**
- Minimum 2 hours between any two posts from different ideas
- Minimum 3 hours between posts from the same idea

**Topic Rotation:**
- Avoid posting 3+ consecutive posts from the same topic (AI, Finance, Geopolitics, etc.)
- Rotate topic tags across the day

## Content Staggering by Urgency

### 🔴 Breaking (24-hour window)
- **T+0–15min:** First format posts (usually Tuki/Bark QRT)
- **T+1–3hrs:** Second format (Stat Bomb or Commentary)
- **T+Next day:** Third format (Thread or Explainer) if still relevant

### 🟡 Trending (1–2 day window)
- **T+2–4hrs:** First format (Stat Bomb or Commentary)
- **T+4–12hrs:** Second format (Contrarian or Explainer)
- **T+Next day:** Remaining formats spread throughout

### 🟢 Evergreen (3–7 day window)
- Spread all formats across the week
- Can be pre-scheduled in advance
- Use to fill gaps between breaking/trending content

## Anti-Repetition Logic

1. **Same-idea spacing:** Minimum 3 hours between posts derived from the same Idea (per Notion Idea Pipeline entry)
2. **No duplicate formats:** Never post the same format twice for the same idea
3. **Multi-post per day rule:** If 3+ posts from same idea on one day, move remaining to next day
4. **Topic rotation:** Don't post 3 AI-tagged posts in a row without mixing in Finance/Geopolitics/etc.

## Data Flow

```
Notion Idea Pipeline
    ↓ (filter: status = "Approved" or "Ready for Review")
    ↓
Notion Long-Form Post Library
    ↓ (filter: status = "Ready to Schedule")
    ↓
Schedule Optimizer
    ├─ Check velocity constraints
    ├─ Apply anti-repetition rules
    ├─ Determine optimal post time
    └─ Generate schedule
    ↓
Typefully Draft Creator
    ├─ Assemble post text (hook + body + CTA)
    ├─ Attach media if needed (GIF or clip via media_id)
    ├─ Attach QRT source URL if applicable
    └─ Tag with metadata (needs-review, source type, format)
    ↓
Typefully Draft
    (Status: DRAFT — awaiting human review/approval)
```

## Notion Fields Required

### From Idea Pipeline
- `Title` (Idea name)
- `Status` (must be "Approved" or "Ready for Review")
- `Urgency` (🔴 Breaking / 🟡 Trending / 🟢 Evergreen)
- `Topic Tags` (for rotation checking)
- `Typefully Draft ID` (to track linked draft)

### From Long-Form Post Library
- `Title` (Post title/description)
- `Status` (must be "Ready to Schedule")
- `Format` (Tuki QRT, Stat Bomb, etc.)
- `Idea Link` (relation to Idea Pipeline for anti-repetition)
- `Post Text` (hook + body assembled)
- `Media` (GIF or video clip if applicable)
- `Source URL` (for QRT formats)

## Typefully Metadata (Scratchpad)

Every draft includes structured metadata in the scratchpad:

```
Source: [EXACT URL to original content]
Source Type: [YouTube | Twitter | Articles]
Notion Idea: https://www.notion.so/[IDEA_ID_NO_DASHES]
Format: [format name]
Urgency: [🔴 Breaking | 🟡 Trending | 🟢 Evergreen]
Generated: [YYYY-MM-DD]
Scheduled For: [YYYY-MM-DD HH:MM (timezone)]
```

**Tags (always include):**
- Status: `needs-review` (all new drafts)
- Source type: `source-youtube`, `source-twitter`, or `source-articles`
- Format category: `format-qrt`, `format-statbomb`, `format-thread`, etc. (optional)

## Algorithm: Optimal Scheduling

1. **Fetch all "Ready to Schedule" posts** from Long-Form Post Library and Idea Pipeline (both Approved status)
2. **Group by Idea** to apply anti-repetition rules
3. **Sort by Urgency:** Breaking → Trending → Evergreen
4. **For each post:**
   - Calculate earliest possible publish time (respecting 2hr min spacing from last post, 3hr if same idea)
   - Check velocity constraints:
     - Count QRTs and long-form already scheduled for that day
     - Ensure not exceeding max daily posts (5-8)
     - Reserve spacing slots
   - Check topic rotation: no 3-in-a-row same topic
   - Assign publish slot (exact time, or "next available" if using Typefully's queue)
5. **Create Typefully drafts** with publish_at timestamp (or queue slot reference)
6. **Save draft IDs back to Notion** (Typefully Draft ID field)
7. **Status update:** Mark posts as "Scheduled" in Notion

## Failure Modes

**When to skip/block:**

- **Velocity exceeded:** If adding post would exceed daily max or spacing rule, mark post as `blocked` with comment "Velocity limit reached. Will schedule next available slot."
- **Missing required fields:** If post missing Format, Post Text, or Idea Link, mark as `blocked` with comment "Missing required fields: [field names]"
- **Invalid Notion data:** If Idea Link broken or Idea not found, mark as `blocked` with comment "Cannot resolve Idea: [link]"
- **Typefully API error:** If draft creation fails, mark as `blocked` with comment "Typefully API error: [error details]. Retry or check authentication."

## Implementation Notes

- **No auto-publish:** All drafts created with status DRAFT (never auto-published)
- **Timezone-aware:** Schedule times should respect GeniusGTX's operational timezone (US Eastern)
- **Queue preference:** Use Typefully's queue system when available (simpler than exact timestamps)
- **Batch operation:** Process all ready posts together to optimize global scheduling
- **Idempotency:** Rerunning should not double-schedule; check for existing draft before creating
- **Logging:** Log all scheduling decisions for audit trail

## Notion Database IDs

- **Idea Pipeline:** 330aef7b-3feb-401e-abba-28452441a64d
- **Long-Form Post Library:** d20d2ffc-839a-4435-aa65-6da6f8688644

## Typefully Account

- **Handle:** @GeniusGTX_2
- **Social Set ID:** 151393
- **Account:** Primary account for all content scheduling

## Triggers

This skill runs:
1. **On-demand:** `/account-manager:schedule` command
2. **Scheduled routine:** 3x daily (6am, 12pm, 6pm Eastern)
3. **Webhook:** When Notion post status changes to "Ready to Schedule"

## Success Criteria

- ✅ All "Ready to Schedule" posts processed within 5 minutes
- ✅ Zero posts exceed velocity rules
- ✅ Drafts tagged correctly with metadata
- ✅ All posts include Typefully Draft ID back to Notion
- ✅ Scheduling log accessible for audit
