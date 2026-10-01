#!/usr/bin/env python3
"""Check data/latest.json before it's published.

Errors (exit 1, must be fixed):
  - doesn't match config/brief.schema.json
  - an item from data/raw/brief_input.json is missing, repeated, or has the wrong link
  - a summary written for a headline-only item, or a summarizable item left empty
  - a quote that isn't word-for-word in the transcript, is too long, or has the wrong
    timestamp / link
  - a summary that copies 12+ words in a row from the source (quotes aside)
Warnings (review, then decide):
  - an item not tagged Black Life whose text matches config/black_life_keywords.txt

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

QUOTE_MAX_WORDS = 40
COPY_RUN = 12             # this many words in a row copied from the source = too close
TIMESTAMP_SLACK = 5       # seconds
SUMMARY_MAX_WORDS = 60
CARD_MAX_WORDS = 70
KEYWORD_SCAN_CHARS = 3000


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
    qw = words(q["text"])
    if len(qw) > QUOTE_MAX_WORDS:
        err(f"quote is {len(qw)} words (max {QUOTE_MAX_WORDS}): {q['text'][:60]!r}")
    if "..." in q["text"] or "…" in q["text"]:
        err(f"quote must be one unbroken passage, no ellipses: {q['text'][:60]!r}")
        return
    pos = find(qw, toks)
    if pos is None:
        err(f"quote not found word-for-word in the transcript: {q['text'][:60]!r}")
        return
    start = times[pos]
    if abs(seconds(q["timestamp"]) - start) > TIMESTAMP_SLACK:
        err(f"quote timestamp {q['timestamp']} should be {stamp(start)}")
    if "youtube.com" in item["link"]:
        want = f"{item['link']}&t={seconds(q['timestamp'])}s"
    else:  # podcast links can't jump to a time; ads also shift timestamps per listener
        want = item["link"]
    if q["url"] != want:
        err(f"quote url should be {want}")


def copied_run(text, src_grams):
    w = words(text)
    for i in range(len(w) - COPY_RUN + 1):
        if tuple(w[i:i + COPY_RUN]) in src_grams:
            return " ".join(w[i:i + COPY_RUN])
    return None


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
    for section in ("episodes", "headlines"):
        for out in brief[section]:
            placed.setdefault(out["id"], []).append(section)

    for iid, where in placed.items():
        if iid not in wanted:
            errors.append(f"{iid}: not in brief_input.json")
        elif len(where) > 1:
            errors.append(f"{iid}: appears {len(where)} times")
    for iid, it in wanted.items():
        if iid not in placed:
            errors.append(f"{it['source']}: missing item {it['title'][:60]!r} ({iid})")

    for section in ("episodes", "headlines"):
        for out in brief[section]:
            it = wanted.get(out["id"])
            if not it:
                continue
            label = f"{it['source']}: {it['title'][:50]!r}"
            err = lambda msg: errors.append(f"{label}: {msg}")  # noqa: E731
            expected = "episodes" if it["section"] == "listen" else "headlines"
            if section != expected:
                err(f"belongs in {expected}")
            if out["url"] != it["link"]:
                err(f"url should be {it['link']}")
            src = (ROOT / it["text_file"]).read_text() if it.get("text_file") else ""

            if section == "episodes":
                written = out["cards"] + ([out["takeaway"]] if out["takeaway"] else [])
                if it["summarize"]:
                    if len(out["cards"]) < 2 or not out["takeaway"]:
                        err("needs 2-4 cards and a takeaway")
                    toks, times = transcript_index(src)
                    for q in out["quotes"]:
                        check_quote(q, it, toks, times, err)
                elif written or out["quotes"]:
                    err(f"status is {it['status']}: no cards, quotes or takeaway allowed")
                for c in out["cards"]:
                    if len(words(c)) > CARD_MAX_WORDS:
                        err(f"card is {len(words(c))} words (max {CARD_MAX_WORDS})")
            else:
                written = [out["summary"]] if out["summary"] else []
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
                scan = f"{it['title']} {src[:KEYWORD_SCAN_CHARS]}".lower()
                hits = [k for k in keywords if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", scan)]
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
              f"{sum(len(e['quotes']) for e in eps)} quotes")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
