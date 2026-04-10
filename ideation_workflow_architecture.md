# Content Ideation Workflow Architecture
## The Fountain of Ideas — Full System Design

---

## ACCOUNT
> **@GeniusGTX_2 (Genius Thinking)** — Typefully social set ID: 151393.
> All content, drafts, and scheduling target this account exclusively.

---

## SYSTEM OVERVIEW

This system is a content intelligence engine with three input funnels feeding into one central Idea Pipeline. Each idea gets scored, assigned to formats, drafted automatically in Typefully, and scheduled with staggering logic so audiences never feel overwhelmed.

```
┌─────────────────────────────────────────────────────────────┐
│                    3 INPUT FUNNELS                           │
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐     │
│  │ TWITTER   │    │ DAILY        │    │ YOUTUBE       │     │
│  │ MONITOR   │    │ RESEARCH     │    │ MONITOR       │     │
│  │           │    │              │    │               │     │
│  │ • QRT     │    │ • Newsletters│    │ • Podcast     │     │
│  │   accounts│    │ • News sites │    │   clips       │     │
│  │ • News    │    │ • Blogs      │    │ • Tech        │     │
│  │   sources │    │ • Viral      │    │   creators    │     │
│  │ • 3 tiers │    │   content    │    │ • News        │     │
│  │ • Timeline│    │              │    │   channels    │     │
│  └─────┬─────┘    └──────┬───────┘    └───────┬───────┘     │
│        │                 │                    │             │
│        └────────────┬────┴────────────────────┘             │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              NOTION IDEA PIPELINE                     │   │
│  │                                                       │   │
│  │  Score → Classify → Assign ALL Viable Formats          │   │
│  └───────────────────────┬───────────────────────────────┘   │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              ▼                       ▼                       │
│  ┌────────────────┐     ┌────────────────────┐              │
│  │ RAPID TRIGGER  │     │ MORNING BRIEF      │              │
│  │ (Breaking)     │     │ (Strategic)        │              │
│  │                │     │                    │              │
│  │ Auto-draft in  │     │ Email digest with  │              │
│  │ Typefully for  │     │ day's best ideas,  │              │
│  │ immediate      │     │ trending topics,   │              │
│  │ review         │     │ suggested plan     │              │
│  └───────┬────────┘     └────────────────────┘              │
│          ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              TYPEFULLY DRAFTS                         │   │
│  │                                                       │   │
│  │  Format-matched drafts → @GeniusGTX_2 → Scheduled    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## PART 1: INPUT FUNNEL #1 — TWITTER MONITORING

### 1A. QRT Account Monitoring

**Purpose:** Track accounts that actively QRT news (like Bark and Tuki). Collect BOTH their QRT commentary AND the original tweet being QRT'd. This gives us two things: proven content formats (their QRT) and validated news sources (the tweets they chose to QRT).

**Accounts to monitor:**

| Account | Handle | Why | What to collect |
|---------|--------|-----|-----------------|
| Bark | @barkmeta | "Let me explain" QRT master | His QRTs + the original tweets |
| Tuki | @TukiFromKL | "Do you understand" QRT + daily roundups | His QRTs + originals + roundup items |
| [Add more QRT creators as discovered] | | | |

**Collection method:** Chrome scroll of each account's profile → extract recent QRTs → capture both layers (their commentary + the original tweet URL/text).

**Frequency:** Every 2-3 hours during active news hours (6am-10pm).

---

### 1B. News Source Account Monitoring

**Purpose:** Monitor the accounts that GET QRT'd by the big creators. When these accounts post something with early momentum, it's a signal that QRT creators will be all over it — and we want to beat them.

**Starter list (from our analysis):**

| Account | Handle | Type | Topics |
|---------|--------|------|--------|
| Spectator Index | @spectatorindex | Breaking news | Geopolitics, world events |
| Unusual Whales | @unusual_whales | Financial data | Market anomalies, insider trading, options |
| PopBase | @PopBase | Pop culture | Celebrity, viral moments, deaths |
| FearedBuck | @FearedBuck | Crime/fraud | Criminal cases, scams, fraud |
| Andrej Karpathy | @karpathy | AI/Tech | AI research, security, dev tools |
| Watcher Guru | @WatcherGuru | Crypto/Finance | Crypto news, market moves |
| DogeDesigner | @cb_doge | Tech/Meme culture | Elon Musk, tech culture |
| Mario Nawfal | @MarioNawfal | Spaces/News | Breaking news aggregation |
| Collin Rugg | @CollinRugg | Political news | US politics, policy |
| Wall Street Silver | @WallStreetSilv | Economics | Macro economics, commodities |
| [Expand this list over time] | | | |

**Trigger criteria — the post must meet BOTH conditions:**
1. **Topic match:** Falls within Tech, Finance, or Geopolitics niche
2. **Momentum threshold:**

| Time since posting | Minimum views |
|-------------------|---------------|
| ≤ 1 hour | 50,000 |
| ≤ 2 hours | 70,000 |
| ≤ 3 hours | 100,000 |
| ≤ 6 hours | 200,000 |

**When both conditions are met → trigger the content creation workflow automatically.**

---

### 1C. Three-Tier Creator Monitoring

**Tier 1: Top News Creators**
These are the accounts that break or amplify news. We track them to catch stories before they hit critical mass.

| Account | Handle | Niche |
|---------|--------|-------|
| Sawyer Merritt | @SawyerMerritt | Tech/EV/AI |
| Deitaone | @DeItaone | Financial breaking news |
| Zerohedge | @zaborhedge | Finance/macro |
| Globe Eye News | @GlobeEyeNews | Geopolitics |
| The Kobeissi Letter | @KobeissiLetter | Markets/macro analysis |
| [You add more] | | |

**Tier 2: Frequent Educational Creators**
Not news-driven — these create educational/evergreen content. Slower cadence, ideas can be scheduled days out.

| Account | Handle | Niche |
|---------|--------|-------|
| Ric RTP | @Ric_RTP | AI/Tech investigative |
| Felix Prehn | @felixprehn | Economics/systemic issues |
| Camus | @newstart_2024 | Social commentary/culture |
| Growth Labs | @growthhub_ | Self-improvement/psychology |
| [You add more] | | |

**Tier 3: Timeline Scroll**
This is the wild card. Rather than monitoring specific accounts, this task scrolls your actual X timeline for a set period (5-10 minutes of scrolling) to capture what the algorithm is surfacing. This catches things the curated lists might miss — emerging creators, unexpected viral moments, cross-niche stories.

**Method:** Use Chrome MCP to scroll @GeniusGTX_2's timeline (or whichever account you're logged into). Capture any post meeting the momentum thresholds above. Also note any emerging patterns (same topic appearing from multiple unrelated accounts = strong signal).

**Frequency:** 2-3 times daily (morning, midday, evening).

---

### 1D. Twitter Monitoring — Two Output Modes

**Mode 1: RAPID TRIGGER (Real-time)**
- When a post from any monitored source hits the momentum thresholds
- System immediately:
  1. Creates an entry in Notion Idea Pipeline (status: "Triggered")
  2. Determines the best format(s) based on the content type
  3. Determines the best account(s) based on the topic
  4. Auto-creates Typefully draft(s) using the format guide
  5. Notifies you for review
- Target: Idea → draft ready in under 10 minutes

**Mode 2: DAILY BRIEF (Strategic)**
- Morning email digest summarizing:
  - Top 10 trending ideas collected overnight
  - What the QRT creators (Bark, Tuki) posted and what they QRT'd
  - Momentum data: which stories are still growing
  - Recommended content plan for the day (which ideas, which formats, which accounts, what time)
  - Any patterns (same story appearing across multiple sources = high-priority)

---

## PART 2: INPUT FUNNEL #2 — CLAUDE DAILY RESEARCH

### Purpose
Proactively crawl the web to find content the Twitter funnels might miss — newsletter exclusives, blog deep-dives, news articles not yet gaining Twitter traction, and emerging stories that haven't hit social media yet.

### Sources to Crawl

**Newsletters:**

| Newsletter | Focus | Why |
|------------|-------|-----|
| TLDR | Tech/AI daily digest | Curated tech news, already filtered |
| The Hustle | Business/startups | Entrepreneurship + tech intersection |
| Morning Brew | Business/finance/markets | Accessible financial news |
| Stratechery (Ben Thompson) | Tech strategy/analysis | Deep tech business analysis |
| CB Insights | AI/VC/startups | Data-driven tech trends |
| Axios AI+ | AI policy/industry | AI-specific news |
| Chartr | Data/charts | Visual data stories (great for Format 3 & 6) |
| [Expand over time] | | |

**News Outlets:**

| Outlet | Focus | What to look for |
|--------|-------|-----------------|
| TechCrunch | Tech/startups | Funding rounds, product launches, acquisitions |
| The Verge | Tech/culture | Consumer tech, AI tools, platform changes |
| Bloomberg | Finance/macro | Market moves, economic data, corporate news |
| Reuters | World news | Geopolitical developments |
| Ars Technica | Deep tech | Security, AI research, science |
| The Information | Tech industry | Insider scoops on big tech |
| [Expand over time] | | |

**Blogs / Independent Sources:**

| Source | Focus |
|--------|-------|
| Hacker News (top stories) | Tech community signal |
| Product Hunt (top launches) | New AI/tech tools |
| ArXiv (trending papers) | AI research breakthroughs |
| Reddit r/technology, r/artificial | Community discussions |

### Research Criteria
For a story to enter the Idea Pipeline from Daily Research, it must meet ALL of:
1. **Relevance:** Falls within Tech, Finance, or Geopolitics
2. **Recency:** Published within last 24 hours (for news) or last 7 days (for analysis/features)
3. **Interest signal:** At least ONE of:
   - Multiple sources covering the same story (convergence signal)
   - Involves a recognizable name/company (celebrity factor)
   - Contains specific surprising data/numbers (shareability factor)
   - Contrarian or counterintuitive angle (debate potential)
   - Direct impact on everyday people (relatability factor)

### Output
Each qualifying story gets an Idea Pipeline entry with:
- Source URL(s)
- One-line summary
- Suggested angle(s)
- Suggested format(s)
- Suggested account(s)
- Urgency level (breaking vs. can schedule)

---

## PART 3: INPUT FUNNEL #3 — YOUTUBE MONITORING

### Purpose
Two distinct modes: finding **recent viral videos** for timely content, and mining **all-time high performers** for evergreen content.

### Mode A: Recent Viral Videos

**Channels to monitor:**

| Channel | Type | What to extract |
|---------|------|-----------------|
| Lex Fridman | Long-form interviews (AI, science, philosophy) | Quotable moments, controversial takes |
| Joe Rogan (JRE Clips) | Interviews (broad) | Viral clips, hot takes |
| CNBC | Financial news | Market analysis, CEO interviews |
| Bloomberg | Finance/markets | Economic data breakdowns |
| All-In Podcast | Tech/VC/politics | Industry predictions, debates |
| My First Million | Business/entrepreneurship | Business ideas, success stories |
| Huberman Lab | Neuroscience/health | Research findings, practical tips |
| Colin and Samir | Creator economy | Platform changes, creator strategies |
| Patrick Boyle | Finance/macro | Market analysis with wit |
| Y Combinator | Startups/tech | Startup advice, industry trends |
| [Add channels specific to your clipping tool workflow] | | |

**What to look for:**
- Videos published in last 48 hours with high view velocity
- Specific quotable moments (for Format 2: Quote-Extract + Video)
- Controversial claims or predictions (for Format 1: Long-form Narrative)
- Short, self-contained clips (for Format 4: Short Caption + Clip)

**Clipping integration:** You mentioned having an internal clipping tool. The YouTube monitor identifies the SOURCE video and timestamps of key moments. Your clipping tool handles the extraction. The ideation system tags the clip with format recommendations.

### Mode B: All-Time High Performers (Evergreen Mining)

**Purpose:** Go through channel back catalogs to find videos that performed exceptionally well historically. These are proven concepts that can be remixed into tweet content at any time.

**Criteria:**
- Views significantly above the channel's average (2x+ their median)
- Topic still relevant today
- Contains extractable quotes, data, or narratives

**Use case:** These fill the "educational" side of your content calendar. They're not time-sensitive, so they get scheduled across days/weeks, filling gaps between breaking news content.

**Output:** Each qualifying video/clip gets an Idea Pipeline entry tagged "Evergreen" with lower urgency.

---

## PART 4: THE NOTION IDEA PIPELINE (Central Hub)

### Database Schema

**Database name:** 💡 Idea Pipeline

| Property | Type | Values / Description |
|----------|------|---------------------|
| Idea | Title | One-line description of the content idea |
| Status | Select | New → Triggered → Drafting → Ready for Review → Approved → Published → Killed |
| Urgency | Select | 🔴 Breaking (publish ASAP) / 🟡 Trending (publish today) / 🟢 Evergreen (schedule this week) / ⚪ Backlog |
| Source Funnel | Select | Twitter Monitor / Daily Research / YouTube Monitor / Timeline Scroll |
| Source URL | URL | Link to original tweet, article, or video |
| Source Account | Text | @handle or publication name |
| Momentum Score | Number | View count at time of capture |
| Time Since Posted | Text | How old the source was when captured |
| Topic Tags | Multi-select | AI, Finance, Geopolitics, Business, Psychology, Philosophy, Marketing, Tech, Crypto, Health, Culture |
| Assigned Formats | Multi-select | All format names from our Format Guide (Tuki QRT, Bark QRT, Long-form + Video, etc.) |
| Assigned Formats (ALL viable) | Multi-select | All format names from the Format Guide — assign every format the idea can support |
| Content Angle | Text | The specific spin/angle for this idea |
| Typefully Draft IDs | Text | IDs of auto-created drafts (for tracking) |
| Publish Date(s) | Date | When content was/will be published |
| Performance | Number | Post-publish metrics (views, likes, retweets) |
| Notes | Text | Additional context, related ideas, or instructions |

### Relation to Content Format Bank
The Idea Pipeline database links to the existing 📋 Content Format Bank. When a format is assigned, the creator can click through to see the full recreation guide for that format.

### Status Flow
```
New → An idea just entered the pipeline from any funnel
  │
  ├─ 🔴 Breaking → Triggered (auto-draft created in Typefully)
  │     → Ready for Review (you check the draft)
  │     → Approved (you confirm) → Published
  │
  ├─ 🟡 Trending → Appears in morning brief
  │     → Triggered (after your approval from brief)
  │     → Drafting → Ready for Review → Approved → Published
  │
  └─ 🟢 Evergreen → Backlog
        → Scheduled (assigned to a future date)
        → Drafting → Ready for Review → Approved → Published
```

---

## PART 5: MAXIMUM EXTRACTION PRINCIPLE

> **Core rule: Every qualifying idea gets pushed through AS MANY formats as possible.**
> If an idea passes the filters, it doesn't just get one post. We extract maximum value by creating multiple pieces across different formats, staggered over time, so the audience experiences the same core idea through different lenses without feeling like they're seeing the same thing twice.

### How Maximum Extraction Works

**Example: "Amazon lays off 14,000 warehouse workers, replaces them with robots"**

| Time | Format | Angle | Why it feels fresh |
|------|--------|-------|-------------------|
| +0 min | Tuki QRT (5b-i) | Quick fact breakdown with editorial spin | Rapid news summary — "do you understand what just happened" |
| +2 hrs | Bark QRT (5a-i) | Deep analysis with historical parallels | Different voice, deeper context, connects to past automation waves |
| +4 hrs | One-Tweet News (6) | Single shocking stat + side-by-side image | Totally different format — visual, minimal text |
| +Next day | Long-form Text Only (3) | Data narrative on the economics of automation | Essay-style, no QRT — standalone piece with stats and mechanism |
| +2 days | Short Caption + Clip (4) | Hook + video clip of Amazon CEO or expert reacting | Video-driven, caption is just a teaser |

**Same idea, 5 pieces of content, 5 different formats, spread across 3 days. Each one feels like a different post because the FORMAT changes the experience.**

### Format Extraction Checklist

When a qualifying idea enters the pipeline, run through this checklist to determine ALL formats it can support:

| Format | Can we use it? | Requirement |
|--------|---------------|-------------|
| Tuki Single-Story QRT | Is there a tweet to QRT? | Needs a source tweet |
| Bark "Let me explain" QRT | Can we add deep analysis? | Needs enough context for 150+ word analysis |
| Long-form + Video | Is there a video source? | Needs a podcast/interview clip |
| Quote-Extract + Video | Is there a quotable moment on video? | Needs a specific powerful quote |
| Long-form Text Only | Is there data/numbers? | Needs statistics, dollar amounts, percentages |
| Short Caption + Clip | Is there a short clip (under 2 min)? | Needs a self-contained video moment |
| One-Tweet News | Can it be said in ONE sentence? | Needs a single shocking claim |
| X Article | Can it be turned into a step-by-step guide? | Needs an actionable/educational angle |
| Tuki Daily Roundup | Can it be one bullet in today's compilation? | Always — add it to the evening roundup |

**Minimum: Every qualifying idea should produce AT LEAST 2-3 pieces.** The daily roundup bullet is almost always possible as a bonus.

---

## PART 6: CONTENT STAGGERING LOGIC

### Breaking News (🔴 Urgency)
```
Priority: SPEED first, then depth.

Stagger plan:
  +0 min:   Tuki-style QRT (fastest format to produce)
  +2-3 hrs: Bark-style deep analysis (adds context the QRT didn't have)
  +4-6 hrs: One-tweet news or educational long-form (different format entirely)
  +Next AM:  Long-form text-only or data narrative (evergreen angle)
  +Evening:  Include as a bullet in the daily roundup
```

### Trending Story (🟡 Urgency)
```
Priority: QUALITY over speed. Same-day but with more polish.

Stagger plan:
  Morning:   QRT or short caption + clip
  Afternoon: Different format — long-form or one-tweet news
  Evening:   Include in daily roundup
  +1-2 days: Deep educational angle (long-form text only or article)
```

### Evergreen Content (🟢 Urgency)
```
Priority: SPREAD across the week.

Stagger plan:
  Day 1: Primary format (best fit)
  Day 2-3: Second format (different angle)
  Day 4-5: Third format if applicable

Never more than 1 piece from the same evergreen idea per day.
```

### Anti-Repetition Rules
1. **Time gap:** Never publish two pieces from the same idea within 3 hours
2. **Format variety:** Never use the same format twice for the same idea — every piece must be a different format
3. **Angle variety:** Each piece from the same idea must have a DISTINCT angle/spin
4. **Daily cap:** Maximum 2 pieces from the same original idea per day
5. **Weekly cap:** No single idea generates more than 6 total pieces
6. **Format spacing:** Don't use the same format back-to-back (e.g., two Tuki QRTs in a row on different topics is fine, but vary where possible)

---

## PART 7: MORNING BRIEF — EMAIL FORMAT

**Sent to:** info@geniusgtx.com
**Time:** 8:00 AM daily
**Subject line:** "📊 Content Brief — [Day, Date] | [X] ideas ready, [Y] trending"

### Brief Structure:

```
🔴 BREAKING / TIME-SENSITIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Any stories that triggered overnight that still need attention]
- Idea: [one-line]
- Source: [URL]
- Momentum: [views] in [hours]
- Draft status: [link to Typefully draft if auto-created]
- Recommended: [format] — PUBLISH BY [time]

🟡 TRENDING TODAY
━━━━━━━━━━━━━━━━
[Top 5-10 ideas with strong momentum, sorted by potential]
1. [Idea] — [source] — [views/momentum]
   → Best format: [X]
   → Additional formats: [Y], [Z] (for maximum extraction)

2. [Idea] — [source] — [views/momentum]
   → Best format: [X]

🟢 EVERGREEN OPPORTUNITIES
━━━━━━━━━━━━━━━━━━━━━━━━━
[3-5 non-urgent ideas that can be scheduled this week]

📈 YESTERDAY'S PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━
[Top 3 best-performing posts from yesterday]
- "[post preview]" — [views], [likes], [retweets]

🎯 RECOMMENDED CONTENT PLAN FOR TODAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Specific posting schedule with times, formats, and ideas]
09:00 — Tuki QRT — [idea 1]
11:00 — Long-form text — [idea 2]
14:00 — One-tweet news — [idea 1, different angle]
17:00 — Short caption + clip — [idea 3]
20:00 — Daily roundup self-QRT — [compilation of today's stories]
```

---

## PART 8: SCHEDULED TASKS

### Task 1: Twitter Monitor (runs every 2-3 hours)
```
Trigger: Scheduled (6am, 9am, 12pm, 3pm, 6pm, 9pm)
Actions:
1. Open Chrome → scroll each monitored account's profile
2. Check each QRT creator's recent posts (Bark, Tuki)
3. Check each news source account for posts hitting momentum thresholds
4. For any qualifying posts:
   a. Create Notion Idea Pipeline entry
   b. Assign urgency, format, and account
   c. If 🔴 Breaking: auto-create Typefully draft
5. Log results
```

### Task 2: Timeline Scroll (runs 2-3x daily)
```
Trigger: Scheduled (8am, 1pm, 7pm)
Actions:
1. Open Chrome → navigate to X home timeline
2. Scroll for 5-10 minutes, capturing any posts meeting criteria
3. Note emerging patterns (same topic from multiple unrelated sources)
4. Create Notion entries for qualifying ideas
5. Feed into morning brief
```

### Task 3: Daily Research (runs once, early morning)
```
Trigger: Scheduled (5:30am — before morning brief)
Actions:
1. Crawl newsletter archives, news sites, HN, etc.
2. Filter for relevance + interest signals
3. Create Notion entries for qualifying stories
4. Compile findings for the morning brief email
```

### Task 4: YouTube Monitor (runs 1-2x daily)
```
Trigger: Scheduled (7am, 5pm)
Actions:
1. Check monitored channels for new uploads (last 24h)
2. Check trending/viral videos in relevant categories
3. Identify quotable moments and clip-worthy segments
4. Create Notion entries with timestamps and format recommendations
```

### Task 5: Morning Brief (runs once daily)
```
Trigger: Scheduled (8:00am)
Actions:
1. Pull all Notion Idea Pipeline entries from last 24 hours
2. Sort by urgency and momentum
3. Generate recommended content plan for the day
4. Pull yesterday's performance data
5. Compile and send email to info@geniusgtx.com
```

### Task 6: Performance Tracker (runs once daily, evening)
```
Trigger: Scheduled (10:00pm)
Actions:
1. Check Typefully analytics for all published posts
2. Update Notion Idea Pipeline entries with performance data
3. Identify top performers and patterns
4. Feed insights back into tomorrow's brief
```

---

## PART 9: IMPLEMENTATION PHASES

### Phase A: Foundation (Build Now)
1. Create the Notion 💡 Idea Pipeline database
2. Build the account monitoring lists
3. Set up the first scheduled task (Twitter Monitor) as a proof of concept
4. Test the rapid trigger → Typefully draft flow

### Phase B: Full Funnels (Week 1-2)
5. Set up Daily Research crawl
6. Set up YouTube Monitor
7. Set up Timeline Scroll task
8. Build and test the morning brief email

### Phase C: Optimization (Week 3+)
9. Set up Performance Tracker
10. Refine momentum thresholds based on real data
11. Expand account monitoring lists based on what sources produce the best content
12. Build feedback loop: high-performing posts → influence future format/topic selection

---

## PART 10: ACCOUNT MONITORING LISTS — STARTER SET

### QRT Creators (Track their output + what they QRT)
- @barkmeta
- @TukiFromKL

### News Source Accounts (Track their posts for momentum triggers)
- @spectatorindex
- @unusual_whales
- @PopBase
- @FearedBuck
- @karpathy
- @WatcherGuru
- @MarioNawfal
- @CollinRugg
- @WallStreetSilv
- @DeItaone

### Tier 1: News Creators
- @SawyerMerritt
- @GlobeEyeNews
- @KobeissiLetter
- @zaborhedge
- @elikiiba

### Tier 2: Educational Creators
- @Ric_RTP
- @felixprehn
- @newstart_2024
- @growthhub_
- @YourDocGoku
- @damianplayer

### YouTube Channels — Current Subscriptions (from Genius Thinking account)

**Geopolitics & World Affairs:**
- DW News (6.21M subs) — European perspective, conflict coverage, deep analysis
- The Economic Times (3.4M) — Live political hearings, US/global policy, clip-heavy
- Geopolitical Futures (69.7K) — George Friedman, strategic analysis
- ViewPoint Geopolitics (3.9K) — Smaller but focused geopolitical breakdowns
- DW History and Culture (340K) — Historical context for current events

**Finance & Economics:**
- Bloomberg Originals (4.98M) — Business/culture intersection, documentaries
- CNBC International (1.43M) — Market analysis, CEO interviews
- Lock Stock Finance (121K) — Accessible finance/wealth education
- Adam's Axiom (38K) — Economics breakdowns, market insights
- Crayon Capital (189K) — Finance visualizations

**Science, Education & Ideas:**
- Veritasium (20.5M) — Science/tech, high production value
- SciShow (8.37M) — Science explainers
- Vox (12.7M) — Current affairs explainers, data journalism
- TED (27.3M) — Ideas/talks across all domains
- Big Think (8.63M) — Expert interviews, philosophy, science
- Johnny Harris (7.61M) — Independent journalism, geopolitics
- Yuval Noah Harari (826K) — Philosophy, AI, humanity's future

**Investigative & Documentary:**
- 60 Minutes (4.06M) — Investigative journalism
- OBF (635K) — Documentary-style content

### YouTube Channels — Suggested Additions

**AI & Technology (gap in current subs):**
- Lex Fridman — Long-form AI/tech interviews (ideal for Quote-Extract format)
- Two Minute Papers — AI research breakdowns (fast, clip-friendly)
- AI Explained — AI news/analysis (educational content)
- Fireship — Tech/dev news in fast format
- Matt Wolfe — AI tools and news

**Business & Startups (gap in current subs):**
- All-In Podcast — Tech/VC/politics debates (highly clip-worthy)
- My First Million — Business ideas, entrepreneurship
- Y Combinator — Startup advice
- Patrick Boyle — Finance with wit (great for educational posts)

**Psychology & Human Behavior (gap in current subs):**
- Huberman Lab — Neuroscience, health, performance
- Einzelgänger — Philosophy/psychology essays
- After Skool — Animated philosophy/psychology

---

---

## PART 11: IDEA FILTERING CRITERIA — WHAT MAKES AN IDEA WORTH CREATING

### The Two-Signal Framework

Every idea must pass through TWO filters before entering the pipeline:

**Signal 1: MOMENTUM (quantitative)**
Does this idea have evidence of audience resonance?

**Signal 2: ANGLE (qualitative)**
Can we add value that the original source doesn't have?

Both must be present. High momentum with no angle = we're just reposting. Great angle with no momentum = we're guessing.

### Momentum Thresholds by Source

**Twitter Posts:**

| Time since posting | Minimum views | Classification |
|-------------------|---------------|----------------|
| ≤ 1 hour | 50,000 | 🔴 Breaking — act immediately |
| ≤ 2 hours | 70,000 | 🔴 Breaking — act immediately |
| ≤ 3 hours | 100,000 | 🟡 Trending — act today |
| ≤ 6 hours | 200,000 | 🟡 Trending — act today |
| ≤ 24 hours | 500,000 | 🟡 Trending — still viable if angle is fresh |
| > 24 hours | 1,000,000+ | 🟢 Evergreen — still valuable, schedule for later |

**YouTube Videos:**

| Time since upload | Minimum views | Classification |
|------------------|---------------|----------------|
| ≤ 24 hours | 100,000 | 🟡 Trending — fast-moving viral |
| ≤ 48 hours | 250,000 | 🟡 Trending — building momentum |
| ≤ 7 days | 500,000 | 🟢 Evergreen — proven performer |
| Any age | 2x channel average | 🟢 Evergreen — standout content |
| Any age | 1,000,000+ | 🟢 Evergreen — mine for clips/ideas |

**Web/Newsletter Stories:**
No direct view count available. Use convergence signals instead:
- Story appears in 3+ sources → 🟡 Trending
- Story involves a recognizable name/company → 🟡 Trending
- Story has surprising specific data → 🟢 Evergreen candidate
- Story has contrarian angle → 🟢 Evergreen candidate

### Qualitative Filters — What Makes an Idea "Interesting"

An idea passes the qualitative filter if it scores YES on **at least 3 of these 7 criteria**:

| # | Criterion | Question to Ask | Example |
|---|-----------|-----------------|---------|
| 1 | **Celebrity factor** | Does it involve a recognizable name? | Elon Musk, Jensen Huang, Trump, Sam Altman |
| 2 | **Surprise factor** | Is there a counterintuitive or shocking element? | "The CEO who preaches human creativity just fired his entire design team" |
| 3 | **Number density** | Does it contain specific, shareable data points? | "$1.5 billion bet placed 5 minutes before the announcement" |
| 4 | **Emotional trigger** | Does it provoke outrage, awe, fear, or inspiration? | "Private equity firms bought 500 hospitals. Death rates went up 13%." |
| 5 | **Debate potential** | Would people argue about this in the replies? | "AI agents will replace all white-collar jobs in 5 years" |
| 6 | **Personal impact** | Does it directly affect the reader's life/money/career? | "Your retirement savings are about to be worth less" |
| 7 | **Pattern recognition** | Does it connect to a larger systemic trend? | "This is the third tech company this week to..." |

### Content Exclusion Rules

**HARD EXCLUSIONS — never create content about these as the PRIMARY topic:**
- **Direct war/conflict coverage:** No breaking news on active wars, military strikes, or combat operations. We do NOT cover "Iran strikes" or "troops deployed" as the main story.
  - **ALLOWED:** Referencing war/conflict as CONTEXT for another topic (e.g., "oil prices surge due to Middle East tensions" — the story is oil prices, not the war)
  - **ALLOWED:** Downstream effects — economic impact, supply chain disruption, market reactions, psychological effects on populations
  - **NOT ALLOWED:** Play-by-play conflict updates, military operations, casualty reports, ceasefire negotiations as the primary content
- **Pure crypto/blockchain:** Avoid crypto-specific content (token launches, DeFi protocols, blockchain drama). Exception: if a crypto story has massive mainstream crossover (e.g., "SEC shuts down largest exchange" — that's a finance/regulation story).

### Auto-Reject Criteria — Ideas That Never Enter the Pipeline

Skip the idea entirely if ANY of these are true:
- **Off-niche:** Doesn't touch Tech, Finance, Geopolitics, Business, Psychology, or Philosophy
- **War/conflict as primary:** The main story is about military operations, combat, or armed conflict
- **Pure crypto:** Story is only relevant to crypto-native audiences
- **No angle:** We can't add context, analysis, or editorial spin beyond what already exists
- **Stale news:** Breaking story is 24+ hours old AND has already been covered by QRT creators (Bark, Tuki)
- **Engagement-bait without substance:** Looks viral but has no real information to work with
- **Duplicate:** Same story/angle already exists in the pipeline
- **Low-quality source:** Unverified claims with no credible sourcing

### Format Matching Rules

Once an idea passes both filters, assign format(s) based on content type:

| Content Type | Primary Format | Secondary Format | Notes |
|-------------|----------------|------------------|-------|
| Breaking news tweet | Tuki Single-Story QRT | Bark "Let me explain" QRT | Speed matters — QRT first |
| Interview/podcast clip | Quote-Extract + Video | Short Caption + Clip | Depends on clip length |
| Data-heavy revelation | Long-form Text Only | Bark QRT (if it's a news story) | Numbers are the weapon |
| Controversial take | Tuki QRT | Long-form + Video (if source video exists) | Debate drives engagement |
| Step-by-step system | X Article | Long-form Text Only | Needs the article format's structure |
| Celebrity quote | Short Caption + Clip | Quote-Extract + Video | Name recognition does the work |
| Single shocking stat | One-Tweet News | Tuki QRT (if more context available) | Brevity is power |
| End-of-day compilation | Tuki Daily Roundup | — | Only one per day, evening post |

### Content Velocity Rules (@GeniusGTX_2)

| Metric | Rule |
|--------|------|
| Max posts per day | 5-8 (mix of formats) |
| Min spacing between posts | 2 hours |
| Max QRT-style posts per day | 3 |
| Max long-form posts per day | 2 |
| Daily roundup | 1 per day maximum (evening) |
| Same-topic posts | Max 2 per day, different formats |

---

*Architecture designed March 2026. To be refined continuously based on performance data.*
