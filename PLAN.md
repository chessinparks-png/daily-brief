# Daily Brief — Plan

A free, personal, mobile-first morning news app. $0: GitHub (private repo), Cloudflare
Pages + Access (free plans), open-source libraries, local Whisper.

## Architecture

```
 Your computer — you run /daily-brief in Claude Code each morning
   1. fetcher/fetch.py   RSS / YouTube RSS / Bluesky RSS / Google News RSS
                         YouTube captions + Substack work from a home connection
   2. Whisper            faster-whisper transcribes new Native Land Pod episodes locally
   3. Claude Code        reads the raw inputs (data/raw/, never committed) and writes
                         data/latest.json: cards, ≤2 short quotes w/ timestamps,
                         takeaway, black_life tag
   4. git push           only the summary JSON goes to GitHub
        ▼
 Private GitHub repo  ──►  Cloudflare Pages (free) builds the static site on push
                           Cloudflare Access (free Zero Trust plan): only your
                           email can sign in (one-time code sent to your inbox)
   PWA: add to home screen · Tabs: Listen · Headlines · Black Life · Quotes
```

## Stages (each waits for your approval)

1. **Feed fetcher** — `config/sources.json`, `fetcher/fetch.py`, test workflow.
   Test every source, report results, flag failures + free fixes. ✅ approved
2. **Transcripts** (runs locally) — YouTube captions, Whisper for Native Land Pod,
   skip Shorts and not-yet-aired live events, "new since last brief" window, dedupe. ← *next*
3. **/daily-brief command** — `.claude/commands/daily-brief.md` + JSON schema
   + validator; Black Life tagging + `config/black_life_keywords.txt` (editable).
4. **Web app** — static HTML/CSS/JS (no build step), 4 tabs, mobile-first,
   PWA manifest + service worker, dark mode, deployed to Cloudflare Pages
   and locked to your email with Cloudflare Access.
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
  Full transcripts stay in data/raw/ on your computer (gitignored).
- No paid APIs, no API keys. Summaries are written by Claude Code when you run the command.

## Decisions (Stage 1 review)
- `/daily-brief` runs locally on your computer (fixes YouTube captions and Substack).
- The repo stays private. The app is hosted on Cloudflare Pages and locked to your email
  with Cloudflare Access.
- Reuters: headline + link only, no summary (`"summarize": false` in sources.json).

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
