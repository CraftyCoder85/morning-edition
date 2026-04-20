# Morning Edition · Daily Runbook

This is the playbook the 07:00 scheduled task follows. It is also the manual fallback if the schedule fails.

## One-liner

1. Fetch feeds → 2. Curate 10 stories → 3. Write magazine HTML → 4. Rebuild index → 5. Commit + push.

## Working directory
`C:\Users\Kavi\OneDrive\Desktop\AI Experimentation folder\morning-edition`

## Step 1 · Fetch the feeds

```bash
cd "C:/Users/Kavi/OneDrive/Desktop/AI Experimentation folder/morning-edition"
py fetch_feeds.py > feeds_today.json 2> fetch_err.log
```

Sources pulled: Hacker News top 30, Lobste.rs hottest, 12 subreddits (r/artificial, r/OpenAI, r/LocalLLaMA, r/singularity, r/politics, r/wallstreetbets, r/stocks, r/Superstonk, r/GME, r/science, r/Futurology, r/technology), plus 9 RSS feeds (BBC US politics/business/science, NYT politics/business/science, Ars Technica, The Verge AI, MarketWatch top).

If Reddit is 403-blocking, the fetcher falls through silently — proceed with whatever sources responded. Never fail the run because one source is down.

## Step 2 · Curate the ten stories

**Before you curate, read Kavi.** Load `~/.claude/CLAUDE.md` and, if they exist, `~/.claude/rules/identity.md`, `~/.claude/rules/projects.md`, `~/.claude/rules/content-voice.md`, and `~/.claude/rules/patterns.md`. These tell you who Kavi is (founder, Tolani Group + ShelfBuddy, 17y FMCG, ADHD, ships > polishes), what he's working on right now, and how he writes. The prose you write in this magazine should sound like something he'd send, not a Substack.

Specifically: UK English, no em-dashes, short sentences, commercial over academic, tie stories to revenue / consulting / shipping where honest. Never hedge. If a story is boring, don't include it.

Read `feeds_today.json`. Pick the top 10 that match Kavi's taste:

- **AI tools** — high priority. Model releases, Claude/Anthropic news, workflow-changing tools, OSS models.
- **US politics** — market-moving stories, not just noise. Iran, Trump, SCOTUS, macro-level.
- **Wall Street top picks** — earnings, flows, big moves, ASTS, MSTR, tech stocks.
- **GameStop / GME** — any material news, product launches, Power Packs updates.
- **Weird science** — the one-or-two pieces that make Kavi pause and grin.
- **Anything actionable** — items where Kavi can do something today.

### Flag the ones that directly apply to Kavi

Use the `FOR YOU` stamp on stories where Kavi can take concrete action in the next 24 hours. Typical examples:
- Claude/Anthropic behaviour changes (he uses Claude Code daily)
- Security incidents on tools he uses (Vercel, Netlify, GitHub, Cloudflare)
- FMCG consulting signals (ShelfBuddy, Tolani Group)
- Anything about content ops / AI-driven layoffs (direct consulting pitch)

### Rank rules of thumb

- Lead with the biggest market/political story (page 01)
- AI tool of the day goes to page 02
- Keep one "weird science" palate-cleanser in the middle
- Close with an actionable think-piece (page 10)

## Step 3 · Write the magazine HTML

File: `magazines/YYYY-MM-DD.html` (today's date, zero-padded).

### Design spec (non-negotiable)

- Google Fonts: Fraunces + Inter (+ JetBrains Mono for the terminal spread)
- Every spread full-bleed (`min-height: 100vh`)
- No font smaller than ~15px anywhere. Body copy ≥ 20px.
- 10 distinct spreads — each has its own background, numeral treatment, and layout
- Display headlines use Fraunces at `clamp(48px, 6-9vw, 100-160px)`
- `FOR YOU` stamp on every flagged story

### Spread template library (vary order daily)

| # | Name | Background | Numeral style | Notes |
|---|------|-----------|---------------|-------|
| HERO | Saturated colour | Massive corner numeral (opacity 0.18) | Fraunces 240-540px | Lead story. |
| MIDNIGHT | `#0a0e1a` | Outlined stroke numeral | Half-page grid | Deep calm. |
| TERMINAL | `#0d1b0d` | Mono green numeral | JetBrains Mono body | Stats strip. |
| ACADEMIC | `#eee4c8` | Roman italic numeral (IV.) | Drop-cap body | Report feel. |
| ROSE ALERT | `#f7c9c0` | Rotated stamp + red numeral | Action checklist | Security / alerts. |
| BAUHAUS | 4-colour block grid | Black+yellow numeral cell | Geometric | Graphic. |
| NEON ARCADE | `#0a0a15` | Gradient-fill numeral | Ticker strip | Markets/GME. |
| NATURALIST | `#e8ecd9` | Olive italic numeral | Factoid trio | Weird science. |
| BIG STAT | `#111214` | Page-dominating stat | Four-column finish | Macro/numbers. |
| MANIFESTO | `#f5f1e8` | Single enormous italic numeral | Highlighted quotes | Closing think-piece. |

Use today's file `magazines/2026-04-20.html` as the canonical reference — copy its structure and swap the content. All 10 spread classes (`#s01`…`#s10`) are defined there.

### Cover spread (before #s01)

- Volume/date/masthead flag
- `Morning Edition.` wordmark (huge italic Fraunces)
- One-sentence italic subtitle
- 3-column "on the agenda / for your inbox / and because you asked" lede row
- Assembly timestamp

### Colophon (after #s10)

- "— fin. —" wordmark
- 2 short paragraphs
- Source list

## Step 4 · Rebuild the archive index

```bash
py update_index.py
```

This regenerates `index.html` listing every file in `magazines/`, newest first.

## Step 5 · Commit and push

```bash
cd "C:/Users/Kavi/OneDrive/Desktop/AI Experimentation folder/morning-edition"
git add magazines/YYYY-MM-DD.html index.html
git commit -m "Issue: YYYY-MM-DD"
git push
```

GitHub Pages will serve the new issue at:
- Archive: `https://craftycoder85.github.io/morning-edition/`
- Today's issue: `https://craftycoder85.github.io/morning-edition/magazines/YYYY-MM-DD.html`

## Guardrails

- **Never** commit `feeds_today.json` or `fetch_err.log` — they're gitignored.
- **Never** skip the `FOR YOU` flag just because today's feed is light on direct-action items; find at least 2 flagged stories per issue.
- **Never** use em-dashes in prose (per Kavi's global rules). Use commas, semicolons, or full stops.
- **Always** UK English spelling.
- If `git push` fails (auth), stop and leave a note in `fetch_err.log`. The file is still saved locally.
