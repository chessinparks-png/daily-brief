#!/usr/bin/env python3
"""Check data/latest.json before it's published.

Errors (exit 1, must be fixed):
  - doesn't match config/brief.schema.json
  - an episode or Levity item from data/raw/brief_input.json is missing, or any item is
    repeated or has the wrong link
  - fewer than 12 headlines while some were left out, or Black Life headlines not listed first
  - a summary written for a headline-only item, or a summarizable item left empty
  - a quote (up to 5 per episode, up to 2 per long read) that isn't word-for-word in the
    transcript or article, is longer than 2 sentences, has no 1-2 sentence context, or has
    the wrong timestamp / link
  - a summary, card or quote context that copies 12+ words in a row from the source
Warnings (review, then decide):
  - an item not tagged Black Life (or a headline left out) whose text matches
    config/black_life_keywords.txt

Usage: python fetcher/validate.py [path, default data/latest.json]
"""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "data" / "latest.json"
INPUT = ROOT / "data" / "raw" / "brief_input.json"
SCHEMA = ROOT / "config" / "brief.schema.json"
KEYWORDS = ROOT / "config" / "black_life_keywords.txt"

QUOTE_MAX_WORDS = 50      # and at most 2 sentences
QUOTE_MAX_SENTENCES = 2
CONTEXT_MAX_WORDS = 60    # 1-2 sentences saying what was being discussed
COPY_RUN = 12             # this many words in a row copied from the source = too close
TIMESTAMP_SLACK = 5       # seconds
SUMMARY_MAX_WORDS = 60
CARD_MAX_WORDS = 70
KEYWORD_SCAN_CHARS = 3000
MAX_HEADLINES = 12        # per brief; Black Life first, then the rest by importance


def words(text):
    return re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("’", "'")).split()


def seconds(ts):
    parts = [int(p) for p in ts.split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "sen", "rep", "gov", "gen", "lt", "col", "sgt", "st", "sr",
                 "jr", "jan", "feb", "mar", "apr", "aug", "sep", "sept", "oct", "nov", "dec", "no",
                 "vs", "inc", "co", "corp", "ltd", "mt", "ft", "ave", "blvd", "prof", "rev", "gens"}


def sentences(text):
    """Count sentences, not counting abbreviations like "D.C.", "Rep." or "Oct." as endings."""
    text = text.strip()
    n = 1 if text else 0
    for m in re.finditer(r"(\S+?)([.!?])[\"'”’)]*\s+(?=[\"“A-Z0-9])", text):
        word, mark = m.group(1).lstrip("\"“("), m.group(2)
        if mark == "." and (word.lower() in ABBREVIATIONS or "." in word or len(word) == 1):
            continue
        n += 1
    return n


def stamp(s):
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def transcript_index(text):
    """Word list of a [m:ss]-stamped transcript plus the start time of each word's line."""
    toks, times = [], []
    for line in text.splitlines():
        m = re.match(r"\[([\d:]+)\]\s*(.*)", line)
        if m:
            w = words(m.group(2))
            toks += w
            times += [seconds(m.group(1))] * len(w)
    return toks, times


def find(needle, hay):
    n = len(needle)
    return next((i for i in range(len(hay) - n + 1) if hay[i:i + n] == needle), None)


def check_quote(q, item, toks, times, err):
    """toks/times come from transcript_index (stamped transcript, times is a list), or
    toks is the plain word list of an article (times is None)."""
    qw = words(q["text"])
    if len(qw) > QUOTE_MAX_WORDS:
        err(f"quote is {len(qw)} words (max {QUOTE_MAX_WORDS}): {q['text'][:60]!r}")
    if sentences(q["text"]) > QUOTE_MAX_SENTENCES:
        err(f"quote is more than {QUOTE_MAX_SENTENCES} sentences: {q['text'][:60]!r}")
    cw = words(q["context"])
    if len(cw) > CONTEXT_MAX_WORDS or sentences(q["context"]) > 2:
        err(f"quote context must be 1-2 sentences, max {CONTEXT_MAX_WORDS} words: {q['context'][:60]!r}")
    if "..." in q["text"] or "…" in q["text"]:
        err(f"quote must be one unbroken passage, no ellipses: {q['text'][:60]!r}")
        return
    pos = find(qw, toks)
    if pos is None:
        err(f"quote not found word-for-word in the source text: {q['text'][:60]!r}")
        return
    if times is None:  # article: no timestamp, links to the article
        if q["timestamp"] is not None:
            err("article quotes have no timestamp (set it to null)")
        if q["url"] != item["link"]:
            err(f"quote url should be {item['link']}")
        return
    if q["timestamp"] is None:
        err(f"quote needs a timestamp: {q['text'][:60]!r}")
        return
    start = times[pos]
    if abs(seconds(q["timestamp"]) - start) > TIMESTAMP_SLACK:
        err(f"quote timestamp {q['timestamp']} should be {stamp(start)}")
    base = item.get("quote_link") or item["link"]
    if "youtube.com" in base:
        want = f"{base}&t={seconds(q['timestamp'])}s"
    else:  # podcast links can't jump to a time; ads also shift timestamps per listener
        want = base
    if q["url"] != want:
        err(f"quote url should be {want}")


def check_quotes(quotes, item, src, limit, err):
    if len(quotes) > limit:
        err(f"{len(quotes)} quotes (max {limit})")
    if len({tuple(words(q["text"])) for q in quotes}) < len(quotes):
        err("the same quote is listed twice")
    toks, times = transcript_index(src)
    if not toks:  # an article, not a [m:ss] transcript
        toks, times = words(src), None
    for q in quotes:
        check_quote(q, item, toks, times, err)


def copied_run(text, src_grams):
    w = words(text)
    for i in range(len(w) - COPY_RUN + 1):
        if tuple(w[i:i + COPY_RUN]) in src_grams:
            return " ".join(w[i:i + COPY_RUN])
    return None


def text_of(item):
    return (ROOT / item["text_file"]).read_text() if item.get("text_file") else ""


def keyword_hits(text, keywords):
    text = text.lower()
    return [k for k in keywords if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", text)]


def main():
    brief = json.loads((Path(sys.argv[1]) if len(sys.argv) > 1 else BRIEF).read_text())
    inp = json.loads(INPUT.read_text())
    errors, warnings = [], []

    for e in Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(brief):
        errors.append(f"schema: {'/'.join(map(str, e.absolute_path)) or '(top)'}: {e.message[:150]}")
    if errors:
        return report(errors, warnings)

    keywords = [k.strip().lower() for k in KEYWORDS.read_text().splitlines()
                if k.strip() and not k.lstrip().startswith("#")]
    wanted = {it["id"]: it for it in inp["items"]}
    placed = {}
    for section in ("episodes", "headlines", "levity"):
        for out in brief[section]:
            placed.setdefault(out["id"], []).append(section)

    for iid, where in placed.items():
        if iid not in wanted:
            errors.append(f"{iid}: not in brief_input.json")
        elif len(where) > 1:
            errors.append(f"{iid}: appears {len(where)} times")
    headlines = brief["headlines"]
    has_other = any(not h["black_life"] for h in headlines)
    for iid, it in wanted.items():
        if iid in placed:
            continue
        label = f"{it['source']}: {it['title'][:60]!r}"
        if it["section"] in ("listen", "levity"):
            errors.append(f"{label}: missing ({iid})")
        elif len(headlines) < MAX_HEADLINES:
            errors.append(f"{label}: left out, but the brief has only {len(headlines)} of "
                          f"{MAX_HEADLINES} headlines ({iid})")
        elif it.get("black_life") and has_other:
            errors.append(f"{label}: always Black Life, so it goes ahead of non-Black Life headlines")
        elif has_other:
            hits = keyword_hits(f"{it['title']} {text_of(it)[:KEYWORD_SCAN_CHARS]}", keywords)
            if hits:
                warnings.append(f"{label}: left out but mentions {', '.join(hits[:4])}. If it's a Black "
                                f"Life story, it goes ahead of the non-Black Life headlines.")
    first_other = next((i for i, h in enumerate(headlines) if not h["black_life"]), len(headlines))
    if any(h["black_life"] for h in headlines[first_other:]):
        errors.append("headlines: put every Black Life headline before the others")

    for section in ("episodes", "headlines", "levity"):
        for out in brief[section]:
            it = wanted.get(out["id"])
            if not it:
                continue
            label = f"{it['source']}: {it['title'][:50]!r}"
            err = lambda msg: errors.append(f"{label}: {msg}")  # noqa: E731
            expected = {"listen": "episodes", "levity": "levity"}.get(it["section"], "headlines")
            if section != expected:
                err(f"belongs in {expected}")
            if out["url"] != it["link"]:
                err(f"url should be {it['link']}")
            if out.get("image") != it.get("image"):
                err(f"image should be copied exactly from brief_input.json: {it.get('image')}")
            if out.get("highlight"):
                title = out.get("headline") or out.get("title") or ""
                if not re.search(rf"(?<!\w){re.escape(out['highlight'])}(?!\w)", title, re.I):
                    err(f"highlight {out['highlight']!r} must be a word or phrase from the title")
            src = text_of(it)
            if section == "levity":
                continue  # title, show and link only; the schema allows nothing else
            if it.get("black_life") and not out["black_life"]:
                err("this source always counts as Black Life: set black_life to true")

            if section == "episodes":
                written = (out["cards"] + ([out["takeaway"]] if out["takeaway"] else [])
                           + [q["context"] for q in out["quotes"]])
                if it["summarize"]:
                    if len(out["cards"]) < 2 or not out["takeaway"]:
                        err("needs 2-4 cards and a takeaway")
                    check_quotes(out["quotes"], it, src, 5, err)
                elif written or out["quotes"]:
                    err(f"status is {it['status']}: no cards, quotes or takeaway allowed")
                for c in out["cards"]:
                    if len(words(c)) > CARD_MAX_WORDS:
                        err(f"card is {len(words(c))} words (max {CARD_MAX_WORDS})")
            else:
                written = ([out["summary"]] if out["summary"] else []) + [q["context"] for q in out["quotes"]]
                if out["long_read"] != bool(it.get("long_read")):
                    err(f"long_read should be {str(bool(it.get('long_read'))).lower()}")
                if out["quotes"] and not (it.get("long_read") and it["summarize"]):
                    err("only summarized long reads can have quotes")
                elif out["quotes"]:
                    check_quotes(out["quotes"], it, src, 2, err)
                if it["summarize"] and not out["summary"]:
                    err("needs a summary")
                if not it["summarize"] and out["summary"]:
                    err(f"status is {it['status']}: headline + link only, no summary")
                if out["summary"]:
                    n = len(words(out["summary"]))
                    if n > SUMMARY_MAX_WORDS:
                        err(f"summary is {n} words (max {SUMMARY_MAX_WORDS})")
                    if sentences(out["summary"]) > 2:
                        err("summary is more than 2 sentences")

            if src and written:
                sw = words(src)
                grams = {tuple(sw[i:i + COPY_RUN]) for i in range(len(sw) - COPY_RUN + 1)}
                for text in written:
                    run = copied_run(text, grams)
                    if run:
                        err(f"copies the source word-for-word ({run!r}); put it in your own words")

            if not out["black_life"]:
                hits = keyword_hits(f"{it['title']} {src[:KEYWORD_SCAN_CHARS]}", keywords)
                if hits:
                    warnings.append(f"{label}: not tagged Black Life but mentions "
                                    f"{', '.join(hits[:4])}. Tag it if that's what the story is about.")

    return report(errors, warnings, brief)


def report(errors, warnings, brief=None):
    for w in warnings:
        print(f"WARNING  {w}")
    for e in errors:
        print(f"ERROR    {e}")
    if brief and not errors:
        eps, hls = brief["episodes"], brief["headlines"]
        bl = sum(x["black_life"] for x in eps + hls)
        print(f"OK: {len(eps)} episodes, {len(hls)} headlines, {bl} tagged Black Life, "
              f"{sum(len(x['quotes']) for x in eps + hls)} quotes")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
