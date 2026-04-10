# 2T1C LLC — Autonomous Content Operations
## Master Project Summary & Claude Code Handoff Document

---

## PART 1 — THE VISION

### What We Are Building

An autonomous digital content operation for the GeniusThinking brand (and related creators) that runs on a team of specialized AI agents. The goal is to take a human operator (Toản) from being the person who does the work to being the person who approves the work. The agents handle production. Toản handles judgment, taste, and final direction.

The first production line we are building is the **Content Repurposing Pipeline** — specifically the ability to take any topic or raw facts and produce high-performing social media hooks and threads, primarily for X (Twitter), with extensions to Instagram, LinkedIn, and TikTok.

### The Operating Philosophy

Every agent in this system runs on the **Autoresearch (Karpathy) Methodology:**

1. **Baseline** — Run the current iteration against a strict binary grading rubric
2. **Mutate** — Make ONE atomic change to the prompt, skill, or output
3. **Evaluate** — Re-test. Measure against the baseline
4. **Evolve** — Keep the change if success rate increases. Revert if it decreases
5. **Log** — Document every mutation and its outcome in a changelog

Agents are not static — they improve through iteration. The human's feedback downloads into the system as confirmed rules that persist across sessions.

### The Infrastructure Environment

- **IDE:** VS Code
- **Agent Interface:** Pixel Agents (VS Code extension — a visual "office" where each agent has a desk and can be communicated with directly)
- **Audience Testing:** MiroFish (open source multi-agent simulation engine — feeds hooks to thousands of AI personas to simulate audience engagement before posting)
- **Central Brain:** Notion (guidelines document + hook swipe file database)
- **Skill Files:** `.skill` folders with `SKILL.md` as the core instruction file
- **Version Control:** Claude Code for building, testing, and deploying

---

## PART 2 — WHAT WE HAVE BUILT SO FAR

### 2A — The GeniusThinking Hook Writing System

**Status: Built. Skill files ready. Deployed to Notion.**

A complete system for identifying angles and writing high-performing social media hooks. This is the foundational skill that all content agents will use.

**Files built:**
```
hook-writing-system/
├── SKILL.md                        ← brain + process + Autoresearch loop
└── references/
    ├── swipe-file.md               ← 70+ original viral hooks organized by type
    ├── angle-finding.md            ← 5-step angle finding process + angles bank
    ├── hook-anatomy.md             ← all opener/closer/escalation types with examples
    ├── thread-types.md             ← 6 thread types with pre-built structures
    └── language-bank.md            ← word bank, verb bank, fixed phrases, narrator voice
```

**The system covers:**

**Layer 1 — Angle Finding (pre-writing)**
The most important step. Before writing a word, the agent identifies:
- The unexpected association (person + person, person + institution, person + country)
- The visualization test (can you picture it in one sentence?)
- The primal trigger (betrayal, survival, loyalty, vulnerability, sacrifice, injustice)

Angle strength spectrum:
- Level 4: Double authority + primal trigger (strongest)
- Level 3: Single authority + reader implication
- Level 2: Single authority, no implication
- Level 1: No authority yet — run expansion move

**Layer 2 — Thread Type Selection**
6 thread types, each with distinct logic, pre-built structures, and canonical examples:
1. Concept/Idea — the concept is the hero
2. Historical/Geopolitical — the system is the hero
3. Biographical — the person's paradox is the hero
4. Business/Strategy — the strategy is the hero
5. Podcast/Interview Recap — curation is the job
6. Personal Authority — the writer's skin in the game is the credibility

**Layer 3 — Hook Anatomy**
- 13 opener types (A through M)
- 4 escalation types (negation staircase, dismissal before reversal, stacked micro-facts, contrast jump)
- 7 closer types (plain delivery, numbered delivery, benefit-framed, personal reaction CTA, personal admission, the introduction, suspended tension)
- Stakes injector rules
- Pivot phrase rules
- Middle section rule (raise tension, anchor scale — don't explain)

**Layer 4 — Language Components**
- 5 emotional triggers with proven pairings
- High-frequency word bank (30+ proven words)
- Loaded verb bank (approved vs. never-use)
- Credibility rules (exact numbers, unexpected comparisons, parenthetical anchors, "just" for speed)
- Fixed phrases bank (transplant verbatim)
- Narrator voice phrases (5 jobs: pacing reset, anticipation builder, credibility through vulnerability, permission to feel, stakes elevation)

**Layer 5 — The Baseline Rubric (4 layers)**
Every hook is scored before output:
- Layer 1: Scroll-stop test — does first line match a proven opening move?
- Layer 2: Emotion pair test — are the 2 emotions a proven pairing?
- Layer 3: Word justification test — verb bank, intensifier bank, number rule, possessive rule
- Layer 4: Personal stake test — can reader complete "I need to read this because [personal reason]"?

Automatic disqualifiers:
- Hedged superlative ("one of the greatest" instead of "the greatest")
- Closer that summarizes instead of promises
- No named entity anywhere in the hook
- More than one pivot sentence
- Em dashes used anywhere (must be split into new sentences)

**The Toản Filter (taste layer)**
The final approval gate. Three things must be true simultaneously:
1. The idea makes you think "damn that's interesting" — conceptual surprise
2. The wording is sharp enough to visualize — concrete and vivid
3. The phrase or structure is reusable — elegance that compounds

**The Swipe File**
70+ original viral hooks organized by thread type and sub-structure. Includes 4 negative examples with full diagnoses. This is the highest-certainty reference material — proven performers that Jordan references when selecting structures and transplanting phrases.

**Notion Infrastructure**
- **Guidelines Brain:** https://www.notion.so/32e04fca1794816ba49bf4b6235f27c1
- **Hook Swipe File Database:** https://www.notion.so/876bb4489b41454cb97b848399c11767
  - Views: By Thread Type (board), By Performance (board), ⭐ Original Viral Hooks (priority table), ✅ Proven Performers, ❌ Negative Examples

---

### 2B — The Feedback Loop System

**Status: Designed. To be implemented in Claude Code.**

**The 3-stage async loop:**

Stage 1 — Jordan Writes
Jordan produces 3 hooks per topic, runs the internal baseline rubric (Autoresearch loop: write → score → mutate → re-score → present best 3).

Stage 2 — MiroFish Tests
Jordan feeds the top hook into MiroFish against a persona set calibrated to GeniusThinking's audience. MiroFish simulates thousands of AI agents with unique personalities reacting on social media.
- Decision A: Strong simulation → post autonomously
- Decision B: Weak but Jordan knows why → fix, retest, post if passes
- Decision C: Weak and Jordan doesn't know why → escalate to Toản

Stage 3 — Escalation to Toản (rare)
Jordan only escalates when:
- MiroFish failed twice and diagnosis is unclear
- Topic has no swipe file precedent
- Structural rule conflict exists for this specific topic
- Unexpected strong performance needs confirmation before logging as new rule

**Escalation format:**
```
ESCALATION — [Topic] — [Date]
Hook: [text]
MiroFish result: [summary]
What Jordan tried: [mutations applied]
Specific question: [one question only]
Optional: Two alternatives to choose between
```

**Mutation log format:**
```
MUTATION LOG — [Date]
Topic: [X]
Original line: [what was written]
Your feedback: [exact words]
Rule extracted: [new guideline]
Applied to: [which section]
Status: CONFIRMED / TESTING
```
A rule becomes CONFIRMED after the same pattern is approved 3 times across different topics.

---

### 2C — The Negative Examples System

**Status: Partially built. 4 negative examples diagnosed.**

We analyzed hooks that underperformed and identified 2 universal failure patterns:

**Pattern 1:** The most interesting detail is almost never leading. It's buried in the middle or the closer. The fix is almost always the same — move the single most surprising fact to line 1 or 2.

**Pattern 2:** Vague pivot lines ("changed science forever," "mysteriously disappeared," "what happened next") signal the angle hasn't been fully found yet. Replace with specific physical details.

**3 failure categories:**
1. Prioritization failure — wrong insight leading, or best detail buried
2. Structural failure — breaks an established rule (hedged superlative, em dash, no named entity, etc.)
3. Visual/Active failure — abstract instead of concrete, reader thinks instead of sees

---

## PART 3 — THE AGENTS WE ARE BUILDING

### Agent 1: Jordan (Hook Writing Agent)

**Role:** Lead hook writer for GeniusThinking content pipeline.

**What Jordan does:**
- Receives a topic + raw facts
- Fetches the Notion guidelines doc and swipe file
- Runs the 5-step angle finding process
- Selects the right thread type and pre-built structure
- Assembles 3 hook candidates using the hook anatomy system
- Scores each against the 4-layer baseline rubric (Autoresearch loop)
- Runs top candidate through MiroFish audience simulation
- Posts autonomously if simulation passes
- Escalates to Toản only when genuinely stuck

**Voice calibration (The Toản Filter):**
Jordan needs to sound like a specific person. The Toản Filter captures Toản's taste:
- Prefers comparison and authority association over raw information
- Uses narrator voice phrases naturally ("I swear this has to be...", "I genuinely don't know how this ends...")
- Avoids em dashes — splits into new sentences instead
- Uses exact numbers with unexpected comparisons
- Leads with the scene, not the concept
- Deprioritizes voice failure as a failure category (nice to have, not must have)

**Status:** Skill files complete. Needs to be wired into Pixel Agents environment.

---

### Agent 2: [Thread Body Writer — Name TBD]

**Role:** Takes an approved hook and writes the full thread body.

**Status:** Not yet built. Next skill to develop after Jordan is deployed.

**What this agent will need:**
- The approved hook as the anchor
- The raw facts/research as input
- Rules for thread body structure (numbered tweets, transition lines, visual details)
- The GeniusThinking voice guidelines
- Rules for the thread closer and CTA

---

### Agent 3: [Content Repurposing Agent — Name TBD]

**Role:** Takes a long-form transcript (YouTube, podcast) and extracts multiple content pieces using the Scout-and-Shout methodology.

**Status:** Previously designed (Scout-and-Shout system with Section Extractor, Golden Moment Extractor, Micro-Nugget Extractor). Needs to be built as a formal skill.

**What this agent will need:**
- The transcript as input
- The 3-tier extraction prompts (already designed)
- The Golden Moment to Atomic Essay Translator
- Output organized by platform (X, Instagram, LinkedIn, TikTok)

---

### Agent 4: [Quality Control Agent — Name TBD]

**Role:** QC layer between production agents and final output. Reviews hooks and threads before they go live, enforcing the baseline rubric and the Toản filter.

**Status:** Conceptual. Not yet designed as a skill.

---

## PART 4 — THE CONTENT SYSTEM CONTEXT

### The Brand: GeniusThinking

**Content territory:**
- Ancient civilizations and suppressed history
- Systemic shifts — nations, empires, geopolitical forces
- Hidden figures behind major events
- Cognitive science and learning frameworks
- Business strategy and market disruptions

**The angle formula for GeniusThinking:**
The brand consistently chooses the systemic angle even when a personal angle is available. Systems over people, civilizations over individuals, forces over personalities.

**The dominant emotion pairs for this brand:**
- Institutional Betrayal + Awe at Scale (most common)
- Fear of Being Left Behind + Curiosity Gap (second most common)
- Awe at Scale + Identity Mirror (for transformation arc content)



---

## PART 5 — WHAT TO BUILD IN CLAUDE CODE

### Immediate Priorities

**1. Wire Jordan into Pixel Agents**
Jordan needs to:
- Read the Notion guidelines doc at session start (via Notion MCP)
- Query the Notion hook swipe file database for relevant examples
- Write 3 hooks with certainty maps
- Run the Autoresearch self-improvement loop internally
- Output the top 3 with feedback prompt attached
- Log mutations back to Notion when feedback is received

**2. MiroFish Integration**
- Set up MiroFish locally (repo: github.com/parety/Miro-Fish)
- Build the GeniusThinking audience persona set (seed with top performing content, audience demographics, X/Twitter platform parameters)
- Connect Jordan's output to MiroFish simulation
- Parse MiroFish results back into Jordan's decision logic

**3. The Feedback Loop Infrastructure**
- Build the mutation log as a persistent file
- Build the escalation trigger logic (when does Jordan reach out vs. self-correct)
- Build the rule confirmation system (TESTING → CONFIRMED after 3 approvals)
- Build the Notion update trigger (confirmed rules write back to guidelines doc)

**4. Next Skill: Thread Body Writer**
After Jordan is deployed and running, build the thread body agent that takes Jordan's approved hook and writes the full thread.

### File Structure for Claude Code

```
2t1c-content-ops/
├── agents/
│   ├── jordan/                     ← hook writing agent
│   │   ├── agent.py               ← main agent logic
│   │   ├── mirofish_connector.py  ← audience simulation
│   │   └── mutation_log.md        ← running changelog
│   └── [future agents]/
├── skills/
│   └── hook-writing-system/       ← built and ready
│       ├── SKILL.md
│       └── references/
│           ├── swipe-file.md
│           ├── angle-finding.md
│           ├── hook-anatomy.md
│           ├── thread-types.md
│           └── language-bank.md
├── tools/
│   ├── notion_sync.py             ← reads/writes to Notion brain
│   └── mirofish_runner.py        ← runs audience simulation
└── README.md
```

---

## PART 6 — KEY DECISIONS AND RULES ESTABLISHED

### On Hook Writing

1. Every word must be justifiable by pointing to a proven example from the swipe file
2. Fixed slots (proven phrases) are transplanted verbatim. Changeable slots (subject, facts, numbers) are filled with best available material
3. The angle finding step is mandatory before hook assembly — never skip it
4. The Visualization Test is the gate. If you can't picture it in one sentence, the angle isn't ready
5. The middle section raises tension and anchors scale — it does NOT explain or justify
6. No em dashes — ever. Split into new sentences
7. 200-300 characters for the scroll-stop moment. The closer can run past 280
8. One sentence per line
9. The closer never summarizes. It only opens the door
10. Concept thread rule: stay 90%+ close to original structure — swap subject, keep phrasing

### On the Feedback System

11. Jordan escalates only when genuinely stuck — not for every hook
12. Feedback must extract a rule, not just apply a fix
13. Rules become CONFIRMED only after 3 approvals across different topics
14. MiroFish results are directional signal, not absolute truth — herd behavior bias in LLM agents means a hook can score strongly on baseline but weakly in simulation. Flag, don't automatically revert
15. The swipe file original viral hooks are always higher priority than session-generated hooks

### On Agent Architecture

16. The Autoresearch loop runs internally — never show the loop to the user, only show final output
17. Every agent reads its skill file fresh at session start — no reliance on memory
18. The Notion guidelines doc is the single source of truth — agent edits and session discoveries write back to it
19. Feedback from Toản is the Toản filter layer — it can't be derived from the swipe file alone

---

## PART 7 — REFERENCE LINKS

**Notion:**
- Guidelines Brain: https://www.notion.so/32e04fca1794816ba49bf4b6235f27c1
- Hook Swipe File Database: https://www.notion.so/876bb4489b41454cb97b848399c11767

**MiroFish:**
- Original repo: https://github.com/parety/Miro-Fish
- English offline fork: https://github.com/nikmcfly/MiroFish-Offline
- Claude/Codex CLI fork: https://github.com/amadad/mirofish

**Pixel Agents:**
- VS Code extension for visual agent office interface

---

## PART 8 — WHAT STILL NEEDS TO BE DONE

### Not Yet Built

- [ ] Thread body writer skill
- [ ] Content repurposing skill (Scout-and-Shout formalized)
- [ ] QC agent skill
- [ ] Jordan wired into Pixel Agents
- [ ] MiroFish audience persona set for GeniusThinking
- [ ] Mutation log persistence layer
- [ ] Rule confirmation system (TESTING → CONFIRMED)
- [ ] Notion sync automation (confirmed rules write back automatically)
- [ ] Toản filter population (need 5-10 of Toản's own hooks that performed well)

### Still Needed From Toản

- [ ] 5-10 hooks Toản personally wrote that performed well (for voice calibration)
- [ ] Negative examples with known underperformance data (same account, similar timing)
- [ ] More swipe file examples from learning science / cognitive performance niche (current file is thin here)
- [ ] Platform confirmation — which platforms does GeniusThinking actively post on right now?

---

*Document compiled: March 2026*
*Next step: Move to Claude Code and begin wiring Jordan into Pixel Agents*
