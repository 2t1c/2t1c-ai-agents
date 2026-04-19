# 2t1c-ai-agents

A monorepo of autonomous agent systems run by **[2T1C LLC](https://x.com/toantruong2t1c)**.

Everything here is orchestrated through scheduled cloud routines, Telegram bots, or local research loops — the common thread is "write the rules once in git, let agents do the rest."

---

## Projects

### [`2t1c-content-ops/`](./2t1c-content-ops) — GeniusGTX content pipeline
Autonomous content pipeline behind **[@GeniusGTX_2](https://x.com/GeniusGTX_2)**. Cloud routines fetch the writing rules (`docs/`) and orchestration specs (`cloud-tasks/`) from this repo at runtime, then pick ideas from Notion → research → write → draft in Typefully → attach media → schedule.

**Stack:** Claude Code cloud tasks · Notion MCP · Typefully MCP · WebFetch runtime sync
**Cadence:** content-generator (6h) · media-attacher (6h) · schedule-approved-posts (3h) · pipeline-qa (daily)

See [`2t1c-content-ops/README.md`](./2t1c-content-ops/README.md) for the architecture diagram and update workflow.

### [`fitness-coach-bot/`](./fitness-coach-bot) — Personal fitness coach on Telegram
Telegram bot with a morning briefing (7am), evening check-in (10:30pm), and weekly measurement reminder. Habits + workouts logged to Notion.

### [`autoresearch-mlx/`](./autoresearch-mlx) — Apple Silicon port of Karpathy's autoresearch
Fixed-time autonomous research loops controlled through `program.md`. Native MLX — no PyTorch, no CUDA. Credit to [@karpathy](https://github.com/karpathy) for the original.

### `skills/` + `.<tool>/skills/`
Shared agent skills (char-counter, clip-extractor, autoresearch, review, ship, etc.) mirrored across every AI coding tool's config directory (`.claude/`, `.codebuddy/`, `.continue/`, `.crush/`, `.goose/`, `.kiro/`, `.roo/`, `.windsurf/`, …) so any tool we pick up can load them.

---

## Repo conventions

- **Rules live in git, not in cloud task prompts.** Cloud routines are thin WebFetch wrappers that pull their spec from `main` at runtime. To update behavior: edit the markdown, push, done.
- **Notion state is encoded in title prefixes** (`🆕 `, `📺 `) because `notion-search` is semantic-only. See [2t1c-content-ops README](./2t1c-content-ops/README.md#title-marker-convention-state-machine-encoding).
- **Secrets never committed.** `.env`, logs, and local-only state are in `.gitignore`.

---

## License

Open source — published as a reference. The GeniusGTX voice, brand, and product (gumroad toolkit) are 2T1C LLC.

---

*Maintained by [@toantruong2t1c](https://x.com/toantruong2t1c) — 2T1C LLC*
