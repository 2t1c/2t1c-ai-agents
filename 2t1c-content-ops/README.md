# 2T1C Content Operations

The autonomous content pipeline behind **[@GeniusGTX_2](https://x.com/GeniusGTX_2)** — a gallery for the greatest minds in economics, psychology, and history.

This repo is the **single source of truth** for the GeniusGTX writing voice, hook system, CTA template, and content generation orchestration. Cloud-scheduled tasks fetch the playbooks from this repo at runtime via `raw.githubusercontent.com`.

---

## Architecture

```
Notion (Idea Pipeline DB)
     │
     ▼
Cloud routine: content-generator (every 6h)
  ├─ Step 0:   load MCP connectors (Notion, Typefully)
  ├─ Step 0.5: WebFetch this repo's docs/* files at runtime
  ├─ Phase 0:  audit pipeline (8 status queries in parallel)
  ├─ Phase 1:  pick 2-3 highest-urgency "New" ideas
  ├─ Phase 2:  research (3+ data points, 1-2 attributed quotes)
  ├─ Phase 3:  QRT-first media strategy
  ├─ Phase 4:  hook (apply hook-writing.md)
  ├─ Phase 5:  body (apply writing-style.md)
  ├─ Phase 6:  CTA (apply cta-template.md)
  ├─ Phase 6.5: community routing (apply community-registry.md)
  ├─ Phase 7:  create Typefully drafts
  ├─ Phase 8:  update Notion (status → "Needs Media")
  └─ Phase 9:  report
     │
     ▼
Cloud routine: media-attacher (every 6h)
  └─ Find clips/GIFs, attach to Typefully drafts, advance to "Ready for Review"
     │
     ▼
[Human review in Typefully]
     │
     ▼
Cloud routine: schedule-approved-posts (every 3h)
  └─ Schedule "Approved" posts to Typefully queue, sync published, clean killed
```

---

## Repo layout

```
2t1c-content-ops/
├── README.md                          ← you are here
├── .gitignore                         ← .env, .DS_Store, logs/, JEMS-U30-*
│
├── docs/                              ← THE RULEBOOK (cloud routines fetch these)
│   ├── writing-style.md               ← voice, body structure, sentence rules
│   ├── hook-writing.md                ← opener types, SETUP→STAKES→PIVOT→PROMISE
│   ├── cta-template.md                ← 5-part close with reciprocity bridge
│   ├── community-registry.md          ← X community routing rules
│   └── swipe-file.md                  ← ~115 proven viral hooks (AI reference)
│
├── cloud-tasks/                       ← Orchestration specs (cloud routines fetch these)
│   ├── content-generator.md           ← Pick ideas → research → write → draft
│   ├── media-attacher.md              ← Find media → attach → advance
│   ├── pipeline-qa.md                 ← Daily QA audit
│   └── schedule-approved-posts.md     ← Schedule approved drafts
│
└── skills/                            ← Tooling skills (kept; not voice rules)
    ├── account-manager/
    ├── autoresearch/
    ├── browse/
    ├── char-counter/
    ├── clip-extractor/
    ├── investigate/
    ├── media-attacher/
    ├── notion-paperclip-sync/
    ├── research-pipeline/
    ├── review/
    └── ship/
```

---

## How cloud routines stay in sync with this repo

Each cloud routine in [claude.ai/code/routines](https://claude.ai/code/routines) is a **thin wrapper** (~10 lines) that fetches its playbook from this repo at runtime:

```
This is an automated run of the content-generator task.

Fetch and follow the orchestration spec:
  WebFetch https://raw.githubusercontent.com/2t1c/2t1c-ai-agents/main/2t1c-content-ops/cloud-tasks/content-generator.md

Runtime values:
  TODAY: <today's date>
  TYPEFULLY_SOCIAL_SET_ID: 151393
```

That's it. **All future rule changes happen in git → push → cloud routine picks up the new version on next run** (WebFetch caches for ~15min).

---

## How to update the writing rules

1. Edit the relevant file in `docs/`
2. `git push` to `main`
3. Done. Next cloud routine run uses the updated rules automatically.

**Do not edit the cloud routine prompt directly in claude.ai/code/routines.** It should stay as a thin wrapper that points to this repo. If the cloud routine prompt drifts from the wrapper pattern, restore it.

---

## Title marker convention (state-machine encoding)

Cloud-routine Notion MCP has no property-filter query tool — `notion-search` is semantic only and silently ignores property filters. To work around this, the pipeline encodes "actionable state" in title prefixes that `notion-search` can find reliably (title matches rank highest in semantic search).

| Status | Title prefix | Set by | Removed by |
|---|---|---|---|
| New | `🆕 ` | **Ideation agent** (you, when creating a new card) | content-generator (Phase 1, when picking) |
| Writing | (none) | content-generator | (next transition) |
| Needs Media | `📺 ` | content-generator (Phase 8, when handing off) | media-attacher (when media done) |
| Ready for Review | (none) | media-attacher | — |
| Approved / Scheduled / Published / Killed | (no marker) | — | — |

### Critical: the ideation agent must add `🆕 ` to every new card

When creating a card in the Idea Pipeline (manually or via your ideation script), **always prepend `🆕 ` to the title**. Without the marker, content-generator will not find the card.

Example:
- ✅ `🆕 In 1847, a Hungarian doctor cut maternal deaths from 18% to 2%`
- ❌ `In 1847, a Hungarian doctor cut maternal deaths from 18% to 2%` (won't be picked up)

If you forget the marker, you can fix it by editing the title in Notion to add `🆕 ` at the start. content-generator will pick it up on the next run.

### Why markers and not Notion views?

Per-status Notion views would also work and would be slightly faster, but require manual setup of 4-8 views in the Notion UI. The marker approach works with zero Notion configuration and is more portable across data sources. If you ever want to migrate to views, the agents can switch with a one-line spec change.

---

## Voice principles (the short version)

GeniusGTX is a gallery for the greatest minds in economics, psychology, and history. The voice carries weight without announcing itself.

- **One big idea per post.** No listicles.
- **Truth Over Trust.** Build causally to the claim. Show what has to be true.
- **Specific over abstract.** "$7.4 BILLION" not "billions." "In 28 days" not "quickly."
- **Calibrated urgency.** Never doom. Never hype.
- **Humanist landing.** The reader leaves more capable, not more anxious.

Full rules in [`docs/writing-style.md`](./docs/writing-style.md).

---

## License

Open source — published as a reference for how to build an autonomous content pipeline. The voice, brand, and product (gumroad toolkit) are 2T1C LLC.

---

*Maintained by [@toantruong2t1c](https://x.com/toantruong2t1c) — 2T1C LLC*
