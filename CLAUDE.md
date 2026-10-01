# Daily Brief

Personal, free, mobile-first morning news app. Read `PLAN.md` first: it has the
architecture, the stages, the decisions made so far, and the Stage 1 test results.

## How we work
- Build in stages. Finish one stage, show the results, and wait for approval before
  starting the next.
- The owner is a beginner. Explain steps plainly and give exact commands to copy.
- Everything must cost $0: free tools and open-source libraries only, no paid APIs or
  API keys. Summaries are written by Claude Code itself during `/daily-brief`.

## Hard rules
- Publish only summaries and short quotes (at most 2 per episode). Never commit or
  publish full transcripts or article text. Raw inputs go in `data/raw/` (gitignored).
- Sources with `"summarize": false` in `config/sources.json` (Reuters) get headline +
  link only. Never write a summary from a headline alone.
- The repo is private. The app is hosted on Cloudflare Pages behind Cloudflare Access
  (owner's email only). Don't add GitHub Pages.

## Layout
- `config/sources.json`: sources and their pinned feed IDs
- `fetcher/fetch.py`: fetches all sources → `data/raw/feeds.json` plus a printed report
- `fetcher/prepare.py`: Stage 2. New items since the last brief, captions + Whisper
  transcripts, dedupe → `data/raw/brief_input.json` and `data/raw/text/` (full text, never published)
- `fetcher/validate.py`: Stage 3. Checks `data/latest.json` against `config/brief.schema.json`
  plus the publishing rules (quotes word-for-word with correct timestamps, no summaries for
  headline-only items, no copied passages); warns on Black Life keyword matches left untagged
- `.claude/commands/daily-brief.md`: the `/daily-brief` command (collect → write → validate → publish)
- `config/black_life_keywords.txt`: backup keyword list for Black Life tagging (owner edits it)
- `.github/workflows/fetch-feeds.yml`: Stage 1 test workflow (cloud check only)

## Commands
- Setup: see `SETUP.md`
- Test the fetcher: `python fetcher/fetch.py --limit 2`
- Collect today's items: `python fetcher/prepare.py` (`--no-whisper` to skip podcast transcription)
- After a brief is published: `python fetcher/prepare.py --mark-done`
- Check a brief: `python fetcher/validate.py`
- Black Life: tag by judgment of what the story is about; the keyword list is only a backup check.
