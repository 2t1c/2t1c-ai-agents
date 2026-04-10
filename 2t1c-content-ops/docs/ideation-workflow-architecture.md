# 🧠 Ideation Workflow Architecture

> Source of truth: Notion page `33004fca-1794-81af-b0aa-f0615386ad68`
> Last synced: 2026-03-28

## System Overview

The ideation workflow operates through 3 input funnels, a central Notion hub, and automated drafting — running 24/7 for @GeniusGTX_2 (Genius Thinking).

**Single Account:** All content posts to @GeniusGTX_2 — Typefully Social Set ID: 151393

---

## Architecture Flow

```
┌─────────────────────────────────────────────┐
│              3 INPUT FUNNELS                 │
├──────────────┬──────────────┬───────────────┤
│  🐦 Twitter  │  🔬 Daily    │  📺 YouTube   │
│   Monitor    │  Research    │   Monitor     │
├──────────────┴──────────────┴───────────────┤
│                    ↓                        │
│        💡 NOTION IDEA PIPELINE              │
│    (Central Hub — Filter & Enrich)          │
│                    ↓                        │
│        📝 TYPEFULLY AUTO-DRAFT              │
│    (Draft ready for human review)           │
│                    ↓                        │
│        📧 MORNING BRIEF (8am email)         │
│    (Daily digest to info@geniusgtx.com)     │
└─────────────────────────────────────────────┘
```

---

## Input Funnels

### Funnel 1: Twitter Monitor
**Schedule:** Every 3 hours (6am-9pm)

**QRT Creators:** @barkmeta, @TukiFromKL
**News Sources:** @spectatorindex, @unusual_whales, @PopBase, @FearedBuck, @karpathy, @WatcherGuru, @MarioNawfal, @CollinRugg
**Tier 1 (News):** @KobeissiLetter, @SawyerMerritt
**Tier 2 (Educational):** @Ric_RTP, @felixprehn, @newstart_2024, @growthhub_
**Tier 3 (Timeline Discovery):** Algorithm-surfaced content

### Two-Signal Framework

**Signal 1: Momentum (Quantitative)**

Core metric: **Viral Ratio = Impressions ÷ Follower Count**

| Time Window | Viral Ratio Threshold | Urgency |
|---|---|---|
| ≤ 1 hour | ≥ 0.20 (20%) | 🔴 Breaking |
| ≤ 2 hours | ≥ 0.30 (30%) | 🔴 Breaking |
| ≤ 3 hours | ≥ 0.50 (50%) | 🟡 Trending |
| ≤ 6 hours | ≥ 0.75 (75%) | 🟡 Trending |
| ≤ 12 hours | ≥ 1.0 (100%) | 🟡 Trending |
| > 12 hours | ≥ 2.0 (200%) | 🟢 Evergreen (qual ≥ 5) |

**Absolute Minimums:**
- 🔴 Breaking: 150K impressions
- 🟡 Trending: 100K impressions
- 🟢 Evergreen: 75K impressions
- Below 75K → auto-skip

**Engagement Velocity Kicker:** If like-to-impression ratio > 5%, lower viral ratio threshold by one tier.

**Cross-Platform Convergence Bonus:** Same story on 2+ platforms → upgrade urgency by one tier.

**Signal 2: Angle (Qualitative)**

7 criteria scored 0 or 1: Celebrity factor, Surprise factor, Number density, Emotional trigger, Debate potential, Personal impact, Pattern recognition.

Score ≥ 5 = qualifies. Score 4 = only if 🔴 Breaking. Score ≤ 3 = auto-skip.

### Funnel 2: Daily Research
**Schedule:** 5:30am daily. Crawls news sites, newsletters, Hacker News.

### Funnel 3: YouTube Monitor
**Schedule:** 2x daily (7am, 5pm). Channels: DW News, Geopolitical Futures, Bloomberg Originals, Veritasium.

### Funnel 3.5: Timeline Scroll
**Schedule:** 3x daily (8am, 1pm, 7pm). Scrolls X timeline for algorithm-surfaced content.

---

## Idea Pipeline Schema

| Property | Type | Purpose |
|---|---|---|
| Idea | Title | Short descriptive name |
| Status | Select | New → Triggered → Drafting → Ready for Review → Approved → Published → Killed |
| Urgency | Select | 🔴 Breaking / 🟡 Trending / 🟢 Evergreen / ⚪ Backlog |
| Source Funnel | Select | Twitter Monitor / Daily Research / YouTube Monitor / Timeline Scroll |
| Source URL | URL | Link to original content |
| Source Account | Text | @handle or channel name |
| Momentum Score | Number | Impressions at time of capture |
| Topic Tags | Multi-select | AI, Finance, Geopolitics, Business, Psychology, Philosophy, etc. |
| Assigned Formats | Multi-select | All 10+ content formats |
| Content Angle | Text | The specific editorial spin |
| Typefully Draft ID | Text | Links to auto-generated draft |
| Notes | Text | Free-form notes |

---

## Auto-Reject Criteria

- War/armed conflict as primary topic (hard exclusion)
- Pure cryptocurrency/blockchain (soft exclusion)
- No clear editorial angle after 30 seconds
- Source account has history of misinformation
- Story > 24 hours old with no unique angle remaining

---

## Writing Agent Handoff Chain

1. **Jordan writes the hook** (except Tuki Style — Maya handles full post)
2. **Maya writes the body** following Writing Style Guide
3. **Media workflow runs** (GIF/Clip/None based on format)
4. **Typefully draft created** (hook + body + CTA + media + QRT)

Draft is never auto-published. Always requires human review.

---

## Content Staggering Logic

| Urgency | First Post | Additional |
|---|---|---|
| 🔴 Breaking | Within 15 min | +1-3hrs, then next day |
| 🟡 Trending | Within 2-4 hrs | Spread across 1-2 days |
| 🟢 Evergreen | Scheduled | Spread across 3-7 days |

### Anti-Repetition Rules
- 3-hour minimum gap between same-idea posts
- Never post same format twice for same idea
- Rotate topic tags

---

## Scheduled Tasks

| Task ID | Schedule | Purpose |
|---|---|---|
| twitter-monitor | Every 3hrs (6a-9p) | Scan Twitter, check momentum, create entries |
| daily-research | 5:30am | Crawl news/newsletters |
| timeline-scroll | 3x daily (8a, 1p, 7p) | Scroll X timeline |
| youtube-monitor | 2x daily (7a, 5p) | Browse YouTube subs |
| morning-brief | 8am | Compile daily email digest |
| add-account | On-demand | Onboard new monitored accounts |

---

*Single source of truth for how the ideation system works. All scheduled tasks reference these rules.*
