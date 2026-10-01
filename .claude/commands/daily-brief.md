---
description: Collect today's news, write the brief, validate it, and publish it
allowed-tools: Bash(.venv/bin/python fetcher/prepare.py:*), Bash(.venv/bin/python fetcher/validate.py), Bash(git add data/latest.json), Bash(git commit:*), Bash(git push), Read, Write, Edit
---

Write today's Daily Brief. Work without asking questions: this may run unattended
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
Every item appears exactly once: `section: "listen"` → `episodes`,
`section: "laughs"` → `laughs`, everything else → `headlines`. Copy `id`, `source`, `published` and `link` (as `url`)
exactly. Top level: `date` (today, YYYY-MM-DD), `generated_at` (now, ISO 8601 with
timezone), `since` (from brief_input.json), `failed_sources` (the `source` names in
brief_input.json's `failed_sources`).

**Episodes** (`summarize: true`):
- `cards`: 2–4 cards, each 2–3 sentences (max 70 words), covering the main points in
  the order they come up. Attribute views to the speaker ("Richardson argues…").
- `takeaway`: one line, the single thing worth remembering.
- `quotes`: 0–2 of the most striking or informative lines. Each is one unbroken passage
  copied **word for word** from the transcript (no ellipses, max 40 words). Fix only
  capitalization and punctuation. Never quote ads or sponsor reads (podcast transcripts
  start with ads). `speaker`: the name if the transcript makes it clear, else null.
  `timestamp`: the `[m:ss]` stamp of the line where the quote starts. `url`: for YouTube,
  the video url plus `&t=<seconds>s`; for podcasts, the episode url (timestamps there
  are approximate because ads vary per listener).
- `title`: the item title.
- Episodes with `summarize: false`: `cards: []`, `quotes: []`, `takeaway: null`.

**Headlines**:
- `headline`: the item title (drop a trailing " - Reuters").
- `summary`: `summarize: true` → 1–2 sentences, max 60 words, your own words.
  `summarize: false` → `null`.

**Laughs** (`section: "laughs"`): copy `id`, `source`, `title`, `show`, `platform`,
`published` and `link` (as `url`). No summary, nothing else.

**For every summary, card and takeaway:** use only facts in the source text. Write in your
own words: never copy 12 or more words in a row from the source (quotes are the only
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
git commit -m "Daily brief YYYY-MM-DD"
git push
.venv/bin/python fetcher/prepare.py --mark-done
```
Never add anything from `data/raw/`. If `git push` fails, say so and don't run `--mark-done`.

## 6. Report
A short summary for the owner: the number of episodes, headlines and laughs, how many are tagged
Black Life, anything skipped or held for retry, and any failed sources.
