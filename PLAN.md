# The Black Brief — Plan

A free, personal, mobile-first morning news app. $0: GitHub (private repo), Cloudflare
Pages + Access (free plans), open-source libraries, local Whisper.

## Architecture

```
 Your computer — you run /black-brief in Claude Code each morning
   1. fetcher/fetch.py   RSS / YouTube RSS / Bluesky RSS / Google News RSS
                         YouTube captions + Substack work from a home connection
   2. Whisper            faster-whisper transcribes new Native Land Pod episodes locally
   3. Claude Code        reads the raw inputs (data/raw/, never committed) and writes
                         data/latest.json: cards, short quotes w/ timestamps + context,
                         takeaway, black_life tag
   4. git push           only the summary JSON goes to GitHub
        ▼
 Private GitHub repo  ──►  Cloudflare Pages (free) builds the static site on push
                           Cloudflare Access (free Zero Trust plan): only your
                           email can sign in (one-time code sent to your inbox)
   PWA: add to home screen · one scrolling home screen (Particle style): Listen, Black Life,
   Read, Headlines, Quotes, Levity as swipe rows
```

## Stages (each waits for your approval)

1. **Feed fetcher** — `config/sources.json`, `fetcher/fetch.py`, test workflow.
   Test every source, report results, flag failures + free fixes. ✅ approved
2. **Transcripts** (runs locally) ✅ approved — — YouTube captions, Whisper for Native Land Pod,
   skip Shorts and not-yet-aired live events, "new since last brief" window, dedupe.
3. **/black-brief command** ← *in review* — `.claude/commands/black-brief.md` + JSON schema
   + validator; Black Life tagging + `config/black_life_keywords.txt` (editable).
4. **Web app** ← *in progress* — static HTML/CSS/JS in `site/` (no build step), one scrolling home screen, mobile-first,
   PWA manifest + service worker, dark mode, deployed to Cloudflare Pages
   and locked to your email with Cloudflare Access.
5. **Polish** — archive of past briefs, failure banner when a source is down.

## Data shape (`data/latest.json`, schema in `config/brief.schema.json`)

```json
{
  "date": "2026-10-01", "generated_at": "…", "since": "…", "failed_sources": [],
  "episodes": [{ "id": "…", "source": "…", "title": "…", "url": "…", "published": "…",
    "cards": ["2–3 sentences", "…"],
    "quotes": [{ "text": "word-for-word", "speaker": "…", "timestamp": "12:15",
                 "url": "…&t=735s" }],
    "takeaway": "one line", "black_life": true }],
  "headlines": [{ "id": "…", "source": "…", "headline": "…", "url": "…", "published": "…",
    "summary": "1–2 sentences, or null for headline-only", "black_life": false }]
}
```
Podcast quote links go to the episode page (no time jump); podcast timestamps are
approximate because ads are inserted per listener.

## Rules baked in
- Only summaries + short quotes are ever committed/published (≤5 per episode, ≤2 per long read).
  Full transcripts stay in data/raw/ on your computer (gitignored).
- No paid APIs, no API keys. Summaries are written by Claude Code when you run the command.

## Decisions (Stage 1 review)
- `/black-brief` runs locally on your computer (fixes YouTube captions and Substack).
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

## Stage 2 design (`fetcher/prepare.py`)
- **Window:** items published since the last brief (minus 6 h overlap); 36 h on the
  first run; never more than 3 days back. Links already briefed are remembered for
  30 days in `data/raw/state.json`, so nothing repeats.
- **Cap:** newest 10 items per source (set `"max_items"` in sources.json to change).
- **YouTube:** Shorts skipped. Videos with no captions yet (upcoming live events,
  streams still processing) are held and retried on later runs for up to 2 days.
- **Native Land Pod:** audio downloaded, transcribed locally with faster-whisper
  (`small.en`, CPU), audio deleted; transcripts cached so reruns are instant.
- **Dedupe:** same link, or same title as an earlier item (listen sources win, so
  HCR's "click here" Substack post is dropped in favor of her video).
- **Headline-only:** Reuters, and any item with under 200 characters of text, is
  marked `summarize: false`; Stage 3 shows headline + link only.
- **Output:** `data/raw/brief_input.json` (item list) + `data/raw/text/<source>/<id>.txt`
  (full text with `[m:ss]` timestamps). All gitignored.
- `--mark-done` is run after a brief is published; it advances the window.

## Decisions (Stage 2 review)
- Whisper stays on `small.en` (accuracy over speed; quotes must be exact). ~20 min per hour of audio.
- Philip Lewis: headline + link only (`"summarize": false`).
- Washington Informer: feed has excerpts only, so full articles are downloaded
  (`"fetch_full_text": true`, extracted with trafilatura; kept in data/raw/ only).

## Decisions (Stage 3)
- Black Life is tagged by judgment of what a story is about; `config/black_life_keywords.txt`
  is a backup that makes the validator flag untagged matches for a second look.

## Source changes (Oct 1, 2026, before Stage 3 approval)
Removed The Atlantic and Heather Cox Richardson's YouTube channel (Letters from an American stays).
Posting counts, Aug 2 – Oct 1, 2026 (60 days):

| Writer | Where | Pieces | Treatment |
|---|---|---|---|
| Michael Harriot | ContrabandCamp (Substack): 9 newsletters + 10 podcasts | 19 | regular; 13 of 19 paid-only → headline + link |
| Jelani Cobb | The New Yorker | 1 | only when new (14-day look-back) |
| Tiffany Cross | Substack (last post July 9); ACross Generations podcast ended Jan 2025 | 0 | only when new |

Bluesky: Harriot and Jemele Hill active (added, headline + link, max 5/day). Cobb last
posted May 21, Cross Aug 9: not added. Black Perspectives (AAIHS): ~weekly, full article
text downloaded, always Black Life. Levity: Karlous Miller tracker, max 2/day.

## Decisions (Stage 3 review)
- App name: The Black Brief (folder and repo stay `daily-brief`); command is `/black-brief`.
- The "Laughs" section is called Levity.
- At most 12 headlines per brief: Black Life stories first, then the rest by importance.
  Headlines left out are still marked as covered, so they don't come back the next day.

## Decisions (Stage 4 review: quotes)
- Quotes: up to 5 per podcast episode, 1-2 per long read (sources with `"long_read": true`:
  Cobb, Harriot, Letters from an American, Black Perspectives, Capital B, Tiffany Cross). One or
  two sentences each, word for word, each with 1-2 sentences of context. Unsure of the wording
  means leave it out. Long-read items form the Read tab (`long_read` in the data).
- Native Land Pod is on YouTube (channel `UCPwDm9ID1xdHlHnkYDizCCA`; captions are off). When the
  matching video exists, `prepare.py` transcribes the video's own audio, so quote timestamps link
  to YouTube with `&t=`. The video premieres in the afternoon (4 pm ET), after the podcast drops
  at 7 am: a morning run falls back to the podcast audio and episode link (no time jump).

## Decisions (Stage 4 review: hero photo and tips)
- Top of the app: a muted public-domain NPS photo (30 in `photos/`, one per day, in order) behind the
  wordmark and date, fading into the page background; credit "NPS Photo". Photos come from
  Wikimedia Commons files marked Public domain and credited to the National Park Service
  (`fetcher/get_photos.py`, list in `config/photo_titles.txt`). Rock Creek Park and Anacostia have
  few good public-domain scenic photos (one each); the rest are other green parks.
- A grounding tip from `tips.txt` shows under the date, a new random one on each open and on tap.
  The daily run never changes it.

## Decisions (Stage 4 review: redesign)
- Inspired by Particle (principles only): section names as a large bold heading row, tiny letter-spaced
  source labels, bold titles with summaries clamped to 2 lines, open rows with hairlines instead of boxed
  cards, big serif quotes. Black Life is a small green label; unread dots are small and faded.
## Design (Stage 4, Oct 2 redesign after Particle)
- Opening (Oct 2 update): a full-screen park photo with the date and the grounding tip large and
  centered. Tap the tip for another. Scrolling slides the news up over it while the photo fades.
- One scrolling home screen, no tabs. Order: the opening, then
  Listen, Black Life, Read, Headlines, Quotes, Levity. Each is a bold title with ">" and a
  one-line subtitle over a horizontal swipe row (next card peeks in). Tapping the title opens
  the full list (`#listen`, `#black`, `#read`, `#headlines`, `#quotes`, `#levity`).
- Which row an item lands in: episodes → Listen; Black Life → every item tagged
  `black_life` (episodes also stay in Listen); Read → other headlines with a summary;
  Headlines → other headline-only items (Reuters, Bluesky); Quotes → every episode quote.
- Cards: tall, rounded, full-bleed preview image with a tinted wash by section (Listen
  purple, Black Life gold, Read blue, Headlines red, Levity green), tiny uppercase
  "SOURCE · 3H AGO", bold white headline with an optional `highlight` word in the section color.
  Images load from the source URL; nothing is downloaded or committed.
- Images (Oct 2 rule): only an image that belongs to the item. Videos get their own YouTube
  thumbnail (hq720, falling back to hqdefault); stories get their own og:image
  (`fetcher/fetch.py:item_image`). Podcast episodes, Levity podcast links, Reuters, Bluesky
  and anything without its own image get a bold gradient card in the section's color. Never
  stock, Wikimedia, feed artwork or other unrelated pictures.
- Opening photos: only the owner's NPS park photo set in `site/parks/`, listed in
  `site/parks/parks.json` by `python fetcher/parks.py`; one per day. With no photos it shows
  plain deep green, never a substitute. Grounding tips: `site/tips.txt` (owner's 109 tips; a random one
  on each open and on tap).
- Park photos (Oct 1): 24 of the original 30, about 1600 px wide and under 1.5 MB each, re-downloaded from
  Wikimedia Commons (public domain, NPS). Dropped 6 that weren't nature scenes (picnic area, camp
  road, porch, canal road, two canoe shots). `parks.py` spreads each park evenly through the cycle and
  never puts the same park on back-to-back days (last → first included); the app counts days
  continuously so New Year doesn't break the order.
