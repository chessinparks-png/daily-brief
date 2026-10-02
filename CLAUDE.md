# The Black Brief

Personal, free, mobile-first morning news app. Read `PLAN.md` first: it has the
architecture, the stages, the decisions made so far, and the Stage 1 test results.

## How we work
- Build in stages. Finish one stage, show the results, and wait for approval before
  starting the next.
- The owner is a beginner. Explain steps plainly and give exact commands to copy.
- Everything must cost $0: free tools and open-source libraries only, no paid APIs or
  API keys. Summaries are written by Claude Code itself during `/black-brief`.

## Hard rules
- Publish only summaries and short quotes (up to 5 per episode, 1-2 per long read, each one or
  two sentences, word for word, with 1-2 sentences of context). Never commit or
  publish full transcripts or article text. Raw inputs go in `data/raw/` (gitignored).
- Sources with `"summarize": false` in `config/sources.json` (Reuters, Bluesky) get headline +
  link only, and so do paid-only Substack posts. Never write a summary from a headline alone.
- Levity items are title, show and link only. Black Perspectives (`"black_life": "always"`)
  is always tagged Black Life.
- The repo is private. The app is hosted on Cloudflare Pages behind Cloudflare Access
  (owner's email only). Don't add GitHub Pages.

## Layout
- `config/sources.json`: sources and their pinned feed IDs
- `fetcher/fetch.py`: fetches all sources → `data/raw/feeds.json` plus a printed report.
  Kinds: rss, podcast, youtube, bluesky, substack (archive API: author filter, paid-only
  posts are headline + link, free podcasts go to Whisper), newyorker (contributor page),
  people_search (`fetcher/levity.py`)
- `fetcher/levity.py`: Karlous Miller tracker for the Levity section (YouTube search page +
  iTunes Search API; last 7 days, no clips/compilations/reuploads/repeats, max 2)
- `fetcher/prepare.py`: Stage 2. New items since the last brief, captions + Whisper
  transcripts, dedupe → `data/raw/brief_input.json` and `data/raw/text/` (full text, never published)
- `fetcher/validate.py`: Stage 3. Checks `data/latest.json` against `config/brief.schema.json`
  plus the publishing rules (quotes word-for-word with correct timestamps, no summaries for
  headline-only items, no copied passages); warns on Black Life keyword matches left untagged
- `.claude/commands/black-brief.md`: the `/black-brief` command (collect → write → validate → publish)
- `config/black_life_keywords.txt`: backup keyword list for Black Life tagging (owner edits it)
- App (repo root, no build step): `index.html`, `app.css`, `app.js`, `sw.js`, `manifest.webmanifest`,
  `icons/`. Preview on a Mac: `python fetcher/preview.py` (never serves `data/raw/`).
- `photos/` + `photos/photos.json`: 30 public-domain NPS hero photos (one per day) from
  `fetcher/get_photos.py` and `config/photo_titles.txt`; credit line shown in the app
- `site/`: the app (static `index.html`, `styles.css`, `app.js`; reads `data/latest.json`).
  One scrolling home screen in the style of the Particle news app; design notes in PLAN.md.
  Opening photos come only from the owner's NPS park set in `site/parks/` (list them with
  `python fetcher/parks.py`, which also orders them so a park never shows two days running).
  Preview on a Mac: `python fetcher/preview.py` → http://localhost:8765/site/ (never serves `data/raw/`).
- `site/tips.txt`: grounding tips, one per line, written once and edited by the owner; the daily run never touches it
- Card images: only the item's own (YouTube thumbnail for videos, og:image for stories).
  Podcasts and anything else get a gradient card. Never use stock or unrelated photos.
- `.github/workflows/fetch-feeds.yml`: Stage 1 test workflow (cloud check only)

## Commands
- Setup: see `SETUP.md`
- Test the fetcher: `python fetcher/fetch.py --limit 2`
- Sample the Levity tracker: `python fetcher/levity.py`
- Collect today's items: `python fetcher/prepare.py` (`--no-whisper` to skip podcast transcription)
- After a brief is published: `python fetcher/prepare.py --mark-done`
- Check a brief: `python fetcher/validate.py`
- List park photos after adding them to `site/parks/`: `python fetcher/parks.py`
- Black Life: tag by judgment of what the story is about; the keyword list is only a backup check.
- At most 12 headlines per brief: Black Life stories first, then the rest by importance.
