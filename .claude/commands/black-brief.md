---
description: Collect today's news, write the brief, validate it, and publish it
allowed-tools: Bash(.venv/bin/python fetcher/prepare.py:*), Bash(.venv/bin/python fetcher/validate.py), Bash(git add data/latest.json), Bash(git commit:*), Bash(git push), Read, Write, Edit
---

Write today's edition of The Black Brief. Work without asking questions: this may run unattended
before the owner wakes up. Follow every step in order.

## 1. Collect
Run `.venv/bin/python fetcher/prepare.py`. It can take 20+ minutes when there's a new
podcast episode (Whisper), so allow up to 60 minutes. If it reports 0 new items, say
"Nothing new since the last brief" and stop.

## 2. Read
Read `data/raw/brief_input.json`. For every item with `"summarize": true`, read its
`text_file` **in full** (use offset/limit to page through long transcripts). Items with
`"summarize": false` get headline + link only: don't read them for a summary, and
never write a summary from a headline alone.

## 3. Write `data/latest.json`
It must match `config/brief.schema.json`. Keep the items in `brief_input.json` order.
Every episode and Levity item appears exactly once: `section: "listen"` → `episodes`,
`section: "levity"` → `levity`. Everything else is a headline, and **at most 12 headlines**
make the brief: first every Black Life story, then the rest in order of importance (how
much the news matters to the owner and how many people it affects, not how recent it is).
If more than 12 are Black Life, keep the 12 most important. Copy `id`, `source`, `published`, `image` and `link` (as `url`)
exactly (`image` may be null; the app shows a colored tile instead). Top level: `date` (today, YYYY-MM-DD), `generated_at` (now, ISO 8601 with
timezone), `since` (from brief_input.json), `failed_sources` (the `source` names in
brief_input.json's `failed_sources`).

**Episodes** (`summarize: true`):
- `cards`: 2–4 cards, each 2–3 sentences (max 70 words), covering the main points in
  the order they come up. Attribute views to the speaker ("Richardson argues…").
- `takeaway`: one line, the single thing worth remembering.
- `quotes`: 0–5 of the most striking or informative lines (fewer if the episode has
  fewer; never pad). See **Quotes** below.
- `title`: the item title.
- Episodes with `summarize: false`: `cards: []`, `quotes: []`, `takeaway: null`.

**Headlines** (the 12 you picked, in that order):
- `headline`: the item title (drop a trailing " - Reuters").
- `summary`: `summarize: true` → 1–2 sentences, max 60 words, your own words.
  `summarize: false` → `null`.
- `long_read`: copy `long_read` from brief_input.json (`true` or `false`; missing = `false`).
- `quotes`: `[]`, except for a long read with `summarize: true` (Cobb, Harriot, Letters from an
  American, Black Perspectives, Capital B): 1–2 quotes. See **Quotes** below.

**Levity** (`section: "levity"`): copy `id`, `source`, `title`, `show`, `platform`,
`published`, `image` and `link` (as `url`). No summary, nothing else.

**Highlight** (`highlight`, episodes and headlines): on about one item in three, pick the
single word or short name in the title that carries the story (a person, place or
institution, e.g. "Cornell", "USDA", "Andrew Young") and copy it exactly as it appears in the
title. The app colors it. Otherwise `null`. Never a generic word ("new", "says").

**Quotes** (episodes: up to 5; long reads: 1–2). Real, word-for-word quotes only:
- `text`: one unbroken passage copied **exactly** from the transcript or article text file:
  one or two sentences, max 50 words, no ellipses, no joining of separate passages. Fix only
  capitalization and punctuation. **If you are not sure of the exact wording, leave the quote
  out.** Never paraphrase, never tidy up grammar, never quote ads or sponsor reads (podcast
  transcripts start with ads). Pick lines that make sense on their own and are worth remembering:
  spread them across the episode, no two from the same moment.
- `context`: 1–2 sentences (max 60 words) in your own words: what topic or moment was being
  discussed that led to the quote, so it makes sense on its own. Use only facts in the source.
- `speaker`: the person's name if the text makes it clear (add who they're recalling if they're
  quoting someone), else null. For an article, the author's name if clear, else null.
- Episodes: `timestamp` is the `[m:ss]` stamp of the line where the quote starts. `url` is the
  item's `quote_link` plus `&t=<seconds>s` when brief_input.json has `quote_link` (the YouTube
  video of that episode); otherwise (no YouTube video) it is the item `link`, with timestamps
  only approximate because ads vary per listener.
- Long reads: `timestamp` is `null` and `url` is the item `link`.

**For every summary, card, takeaway and quote context:** use only facts in the source text. Write in your
own words: never copy 12 or more words in a row from the source (quote `text` is the only
exception). Be neutral and plain; no hype.

**Black Life** (`black_life`): decide by what the story is actually about. Tag it `true`
when Black people, communities, culture, history or institutions are central to the
story, or it's about an issue (voting rights, civil rights, policing, HBCUs, Black
farmers, the racial wealth gap…) told through its effect on Black Americans. Don't tag
a story just because a Black person appears in it, or because a single passing sentence
mentions race. Items with `"black_life": true` in brief_input.json come from a source that
always counts (Black Perspectives): tag them `true`. `config/black_life_keywords.txt` is a
backup check (step 4).

## 4. Validate
Run `.venv/bin/python fetcher/validate.py`.
- **ERROR** lines: fix every one in `data/latest.json` and run it again until it prints `OK`.
  A quote that isn't found must be re-copied exactly from the transcript or replaced.
- **WARNING** lines are keyword matches on stories you didn't tag Black Life. Look at
  each one again. Tag it if the story is really about Black life. Leave it untagged if
  the keyword only comes up in passing.

## 5. Publish
Only after validate prints `OK`:
```
git add data/latest.json
git commit -m "The Black Brief YYYY-MM-DD"
git push
.venv/bin/python fetcher/prepare.py --mark-done
```
Never add anything from `data/raw/`. If `git push` fails, say so and don't run `--mark-done`.

## 6. Report
A short summary for the owner: the number of episodes, headlines and Levity items, how many are tagged
Black Life, anything skipped or held for retry, and any failed sources.
