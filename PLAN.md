# Daily Brief — Plan

A free, personal, mobile-first morning news app. $0: GitHub, GitHub Pages,
GitHub Actions, open-source libraries, local Whisper.

## Architecture

```
 GitHub Actions (cron ~5:00 AM ET, free runner, open internet)
   fetcher/fetch.py      RSS / YouTube RSS / Bluesky RSS / Google News RSS
   captions              youtube-transcript-api (fallback: yt-dlp subtitles)
   podcast audio         faster-whisper (open-source, runs on the runner CPU)
        │  raw inputs (incl. transcripts) → NOT published, NOT on Pages
        ▼
 You run /daily-brief in Claude Code each morning
   reads the raw inputs → writes data/brief-YYYY-MM-DD.json + latest.json
   (summaries, cards, ≤2 short quotes w/ timestamps, takeaway, black_life tag)
   commits + pushes
        ▼
 GitHub Pages (static site in site/, deployed by Actions)
   PWA: add to home screen, works offline for the last brief
   Tabs: Listen · Headlines · Black Life · Quotes
```

## Stages (each waits for your approval)

1. **Feed fetcher** — `config/sources.json`, `fetcher/fetch.py`, test workflow.
   Test every source, report results, flag failures + free fixes. ← *current*
2. **Transcripts** — YouTube captions with fallback, Whisper for Native Land Pod,
   daily scheduled Action, 24–36h "new since last brief" window, dedupe.
3. **/daily-brief command** — `.claude/commands/daily-brief.md` + JSON schema
   + validator; Black Life tagging + `config/black_life_keywords.txt` (editable).
4. **Web app** — static HTML/CSS/JS (no build step), 4 tabs, mobile-first,
   PWA manifest + service worker, dark mode, deployed to GitHub Pages.
5. **Polish** — archive of past briefs, failure banner when a source is down.

## Data shape (draft, finalized in Stage 3)

```json
{
  "date": "2026-10-02",
  "episodes": [{ "source": "...", "title": "...", "url": "...",
    "cards": ["2–3 sentences", "..."],
    "quotes": [{ "text": "...", "timestamp": "12:34", "url": "...&t=754" }],
    "takeaway": "one line", "black_life": true }],
  "headlines": [{ "source": "...", "headline": "...", "summary": "2 sentences",
    "url": "...", "black_life": false }]
}
```

## Rules baked in
- Only summaries + ≤2 short quotes per episode are ever committed/published.
  Full transcripts live only in short-lived Actions artifacts / local temp files.
- No paid APIs, no API keys. Summaries are written by Claude Code when you run the command.

## Open questions for you
1. **Where will you run `/daily-brief`?** On your own computer (Claude Code CLI) or
   in Claude Code on the web? The web sandbox can't reach news sites, so in that
   case Actions must pre-fetch everything into the repo first (planned either way).
2. **Public or private repo?** GitHub Pages is free only for public repos on a free
   plan, which means your briefs are publicly viewable (unlisted, but public).

## Stage 1 results (GitHub Actions run, 2026-10-01)

| Source | Feed | Status |
|---|---|---|
| Native Land Pod | Omny RSS (found via iTunes) | OK, audio MP3 links present |
| Jemele Hill | YouTube `UC25GHmlU1I-zbNcZe7a-aiQ` (SPOLITICS) | Feed OK, captions blocked |
| Heather Cox Richardson | YouTube `UCnbKOlm6H9njgmN-Yil90Rg` | Feed OK, captions blocked; mostly Shorts |
| Letters from an American | Substack `/feed` returns 403 → Google News fallback | Partial (titles + links only) |
| Capital B | `capitalbnews.org/feed/` | OK |
| Reuters | Google News `site:reuters.com when:1d` | OK (headline only, Google redirect links) |
| Philip Lewis | Bluesky `@phillewis.bsky.social` RSS | OK |
| The Atlantic | `/feed/all/` | OK |
| Washington Informer | `/feed/` | OK |

**Blocker for Stage 2:** YouTube blocks caption fetches from GitHub's datacenter IPs
("Sign in to confirm you're not a bot") for both youtube-transcript-api and yt-dlp.
Substack 403s the same IPs. Both work from a home internet connection.
