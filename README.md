# Morning Edition

A daily personal magazine for Kavi. Ten stories curated from Hacker News, Reddit, Lobsters, and selected news wires, rendered as an editorial-style HTML magazine with ten distinct spreads (hero, midnight, terminal, academic, rose alert, bauhaus, neon arcade, naturalist, big-stat, manifesto).

## Daily flow

1. **07:00** — scheduled Claude task wakes up and runs `DAILY_RUNBOOK.md`
2. Fetcher pulls ~200 candidate stories
3. Claude curates down to the top 10 and writes `magazines/YYYY-MM-DD.html`
4. `update_index.py` rebuilds the archive page
5. Commit + push → GitHub Pages serves the fresh issue

## Running manually

```bash
py fetch_feeds.py > feeds_today.json
# then: read feeds_today.json, write magazines/YYYY-MM-DD.html
py update_index.py
git add -A && git commit -m "Issue: YYYY-MM-DD" && git push
```

## Files

- `fetch_feeds.py` — pulls HN + Lobsters + Reddit + RSS, emits JSON
- `update_index.py` — regenerates the archive page
- `DAILY_RUNBOOK.md` — instructions for the daily Claude task
- `magazines/` — published HTML issues
- `index.html` — GitHub Pages landing / archive

## Hosting

Published via GitHub Pages from the `main` branch, root. Live at:
**https://craftycoder85.github.io/morning-edition/**
