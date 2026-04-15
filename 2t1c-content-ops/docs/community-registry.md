# X Community Routing Registry

**Status:** Source of truth for routing posts to X Communities. Cloud routines fetch this file at runtime.

---

## The Registry

| Slug | Community ID | Size | Topics | Eligible | Notes |
|---|---|---|---|---|---|
| `history` | `1691711931751534664` | 64.4k | history, ancient, wars, empires, civilizations, archaeology | yes | strong engagement |
| `x-finance` | `1506800881525829633` | 280k | money, investing, stocks, options, commodities, economics, banking, crypto, markets, macro | yes | largest finance community, ok engagement |
| `money` | `1961141943544513005` | 2.7k | money, personal finance, wealth | yes | small but on-topic |
| `build-in-public` | `1493446837214187523` | 254k | building products, startups, indie hacking, shipping, founder journey | yes | ok engagement |

---

## Routing Decision Process

Run for each post AFTER body + CTA are written, BEFORE creating the Typefully draft.

**Goal:** pick at most ONE community that fits the post. Default is no community (post to timeline only). Only route when the topic is a clear match — never force a fit.

### Step 1 — Eligibility gate

For the current draft, filter the registry:

- `eligible = yes` (currently all four)
- The community's content rules do not conflict with this draft. **Rule:** any community that bans external links in posts is ineligible if the post contains the gumroad URL (which it always does, in the inline CTA).

### Step 2 — Topic match

Score against the post's topic + final body text:

- **history** → primarily about historical events, figures, empires, wars, ancient civilizations, archaeology
- **x-finance** → primarily about markets, investing, macro, stocks, options, commodities, banking, crypto, economics
- **money** → primarily about personal finance, wealth building, money psychology
- **build-in-public** → about founders shipping, startup building, indie hacking, product launches, founder lessons

### Step 3 — Decide

- **Pick the single best match.** If two match (e.g. money + x-finance), pick the larger community (x-finance > money).
- **If no community clearly matches → do NOT route.** Leave `community_id` unset. Timeline-only is the safe default.
- **Never pick more than one community per draft.** Typefully accepts only one community_id per post.
- **Apply only to the main post.** If there's a follow-up reply, do not pass community_id on the reply.

### Step 4 — Record

In the run report, log:

```
Community: [slug] (id: [community_id])
```

OR

```
Community: none (reason: [no match / ineligible])
```

---

## Examples

| Post topic | Routing decision |
|---|---|
| Semmelweis institutional defense | **history** (medical history, 19th century) |
| AlexNet 2012 paradigm shift | **build-in-public** (underdog founders) — debatable, could also fit none if more about academic AI than founder story |
| Nixon Shock 1971 | **x-finance** (monetary policy, macro) |
| Milgram experiments | **none** — psychology angle, no community matches; timeline only |
| Jim Simons Renaissance | **x-finance** (trading, hedge funds) |
| Steve Jobs return to Apple | **build-in-public** (founder comeback) |
| Marie Curie | **history** |
| Compounding mental model | **money** if personal-finance framed; **none** if abstract |

---

## Adding a New Community

To add a community to the registry:

1. Verify the community exists and is publicly joinable on X
2. Confirm it allows external links in posts (so our CTA gumroad link won't be removed)
3. Test post engagement before adding to the rotation
4. Update the registry table above with the community ID, size, topics, and notes
5. Commit and push — cloud routines will pick up the new entry on next run

---

*Version 1.0 — April 2026*
