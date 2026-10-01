#!/usr/bin/env python3
"""The Black Brief Stage 2: collect what's new since the last brief and get transcripts.

  1. Fetch every source (fetch.py).
  2. Keep items published since the last brief that haven't been briefed before.
  3. Skip YouTube Shorts. Hold back videos without captions yet (live events that
     haven't aired, streams still processing) and retry them next run.
  4. YouTube: download captions. Podcasts: transcribe the audio locally with Whisper.
  5. Drop duplicates (same link, or same title as an episode, e.g. Heather Cox
     Richardson's Substack post that only links to her video).

Outputs (all in data/raw/, gitignored, never published):
  brief_input.json   the items for /black-brief to summarize
  text/<source>/     full transcripts and article text, one .txt per item
  state.json         when the last brief ran, links already briefed, items on hold

Usage:
  python fetcher/prepare.py               collect new items
  python fetcher/prepare.py --mark-done   after a brief is published: remember these items
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

RAW = fetch.ROOT / "data" / "raw"
STATE = RAW / "state.json"
OUT = RAW / "brief_input.json"
TEXT_DIR = RAW / "text"
AUDIO_DIR = RAW / "audio"

FIRST_RUN_HOURS = 36    # window when there's no previous brief
MAX_DAYS = 3            # never reach back further than this
OVERLAP_HOURS = 6       # re-check a little before the last brief; seen links stop repeats
CAPTION_WAIT_DAYS = 2   # retry missing captions for this long before giving up
PENDING_DAYS = 7        # drop held-back items after this long
SEEN_DAYS = 30          # forget briefed links after this long
ONLY_WHEN_NEW_DAYS = 14  # look-back for sources with "cadence": "only_when_new"
MIN_TEXT_CHARS = 200    # less text than this is "headline only": never summarized
DEFAULT_MAX_ITEMS = 10  # per source, unless sources.json sets "max_items"


def now():
    return datetime.now(timezone.utc)


def parse(ts):
    return datetime.fromisoformat(ts) if ts else None


def key(link):
    return hashlib.sha1(link.encode()).hexdigest()[:12]


def norm_title(title):
    title = re.sub(r"\s+-\s+Reuters$", "", title or "")
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"last_brief_at": None, "seen": {}, "pending": {}}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def stamp(seconds):
    s = int(seconds)
    return f"[{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}]" if s >= 3600 else f"[{s // 60}:{s % 60:02d}]"


def write_text(item, text):
    path = TEXT_DIR / item["source_id"] / f"{item['id']}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    item["text_file"] = str(path.relative_to(fetch.ROOT))
    item["text_chars"] = len(text)


# ---------- transcripts ----------

_whisper = None


def whisper_model(name):
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        print(f"  loading Whisper model {name!r} (first time downloads it, ~500 MB)…", flush=True)
        _whisper = WhisperModel(name, device="cpu", compute_type="int8",
                                cpu_threads=os.cpu_count() or 4)
    return _whisper


def decode_audio(path):
    """16 kHz mono float samples via ffmpeg (faster-whisper's own PyAV decoder breaks on PyAV 15+)."""
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path),
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def transcribe(item, model_name):
    """Download the episode audio, transcribe it locally, then delete the audio."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio = AUDIO_DIR / f"{item['id']}.mp3"
    try:
        with fetch.session.get(item["audio_url"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(audio, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        started = time.time()
        segments, info = whisper_model(model_name).transcribe(
            decode_audio(audio), language="en", vad_filter=True)
        lines = []
        for seg in segments:
            lines.append(f"{stamp(seg.start)} {seg.text.strip()}")
            print(f"\r  transcribing… {stamp(seg.end)} of {stamp(info.duration)}", end="", flush=True)
        print(f"\r  transcribed {stamp(info.duration)} of audio in {(time.time() - started) / 60:.1f} min")
        return "\n".join(lines)
    finally:
        audio.unlink(missing_ok=True)


# ---------- collect ----------

def collect(args):
    state = load_state()
    t0 = now()
    last = parse(state["last_brief_at"])
    since = (last - timedelta(hours=OVERLAP_HOURS)) if last else t0 - timedelta(hours=FIRST_RUN_HOURS)
    since = max(since, t0 - timedelta(days=MAX_DAYS))
    if args.since:  # manual override, may reach further back than MAX_DAYS
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    print(f"Collecting items published since {since:%Y-%m-%d %H:%M} UTC\n")

    sources = json.loads(fetch.CONFIG.read_text())["sources"]
    items, skipped, failed = [], [], []
    seen_titles = {}

    # Listen sources first, so a headline that repeats an episode is the one dropped.
    for src in sorted(sources, key=lambda s: s["section"] != "listen"):
        print(f"- {src['name']}", flush=True)
        if src["kind"] == "people_search":  # don't repeat appearances already shown
            src["_already_shown"] = list(state.get("shown_titles", {}))
        res = fetch.fetch_source(src, 50, captions=False)
        if not res["ok"]:
            failed.append({"source": src["name"], "notes": res["notes"]})
            print("  FAILED: " + "; ".join(res["notes"][-2:]))
            continue
        src_since = since
        if src.get("cadence") == "only_when_new":  # rare writers: don't miss a piece on a skipped day
            src_since = min(since, t0 - timedelta(days=ONLY_WHEN_NEW_DAYS))
        if src["kind"] == "people_search":  # its own 7-day rule; shown titles stop repeats
            src_since = t0 - timedelta(days=7)
        fresh = []
        for it in res["items"]:
            link, pub = it["link"], parse(it["published"])
            if link in state["seen"]:
                continue
            if link in state["pending"] or pub is None or pub >= src_since:
                fresh.append(it)
        fresh.sort(key=lambda it: it["published"] or "", reverse=True)
        cap = src.get("max_items", DEFAULT_MAX_ITEMS)
        if len(fresh) > cap:
            print(f"  {len(fresh)} new, keeping the newest {cap}")
            skipped += [{"source": src["name"], "title": it["title"], "link": it["link"],
                         "reason": "over the per-source limit", "quiet": True} for it in fresh[cap:]]
            fresh = fresh[:cap]

        for it in fresh:
            item = {"id": key(it["link"]), "source_id": src["id"], "source": src["name"],
                    "section": it.get("section", src["section"]), "title": it["title"],
                    "link": it["link"], "published": it["published"]}
            if src.get("black_life") == "always":
                item["black_life"] = True
            skip = lambda reason: skipped.append({**item, "reason": reason})  # noqa: E731

            if re.fullmatch(r"https?://\S+", it["title"].strip()):
                skip("post is only a link")
                continue

            dup = seen_titles.get(norm_title(it["title"]))
            if dup:
                skip(f"duplicate of {dup}")
                continue

            if src["kind"] == "youtube":
                if "/shorts/" in it["link"]:
                    skip("YouTube Short")
                    continue
                status, text = fetch.youtube_captions(it["video_id"])
                time.sleep(1)
                if not text:
                    pub = parse(it["published"])
                    upcoming = "live event will begin" in status or "Premieres" in status
                    if upcoming or (pub and t0 - pub < timedelta(days=CAPTION_WAIT_DAYS)):
                        state["pending"].setdefault(it["link"], t0.isoformat())
                        skip("live event hasn't aired yet; will retry" if upcoming
                             else "no captions yet; will retry")
                        continue
                    item["status"] = "no_transcript"
                    item["note"] = status
                else:
                    write_text(item, text)

            elif src["kind"] == "people_search":
                item.update(show=it["show"], platform=it["platform"], status="link_only")

            elif it.get("paid_only"):
                item.update(status="headline_only", note="paid subscribers only")

            elif src["kind"] == "podcast" or it.get("audio_url"):
                item.update(audio_url=it.get("audio_url"), duration=it.get("duration"))
                cached = TEXT_DIR / src["id"] / f"{item['id']}.txt"
                if cached.exists():
                    write_text(item, cached.read_text())
                elif args.no_whisper or not item["audio_url"]:
                    item["status"] = "no_transcript"
                    item["note"] = "Whisper skipped (--no-whisper)" if args.no_whisper else "no audio link"
                else:
                    print(f"  {it['title']}")
                    try:
                        write_text(item, transcribe(item, args.whisper_model))
                    except Exception as e:  # noqa: BLE001
                        item["status"] = "no_transcript"
                        item["note"] = f"Whisper failed: {type(e).__name__}: {e}"

            else:
                text = it.get("content") or it.get("summary") or ""
                if src.get("fetch_full_text"):
                    full = fetch.article_text(it["link"])
                    if len(full) > len(text):
                        text = full
                    else:
                        item["note"] = "full article unavailable; using feed excerpt"
                write_text(item, text)

            item.setdefault("status", "ok")
            item["summarize"] = bool(src.get("summarize", True) and item["status"] == "ok"
                                     and item.get("text_chars", 0) >= MIN_TEXT_CHARS)
            if item["status"] == "ok" and not item["summarize"]:
                item["status"] = "headline_only"
            state["pending"].pop(it["link"], None)
            seen_titles[norm_title(it["title"])] = f"{src['name']}: {it['title']}"
            items.append(item)

    for old in TEXT_DIR.glob("*/*.txt"):  # transcripts are cached; drop month-old ones
        if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < t0 - timedelta(days=SEEN_DAYS):
            old.unlink()

    cutoff = t0 - timedelta(days=PENDING_DAYS)
    state["pending"] = {k: v for k, v in state["pending"].items() if parse(v) > cutoff}
    save_state(state)

    OUT.write_text(json.dumps({"collected_at": t0.isoformat(), "since": since.isoformat(),
                               "items": items, "skipped": skipped, "failed_sources": failed},
                              indent=2, ensure_ascii=False))
    print(report(items, skipped, failed))
    return 0 if not failed else 1


def report(items, skipped, failed):
    lines = ["", "=" * 72, f"NEW SINCE LAST BRIEF: {len(items)} items", "=" * 72]
    for src in dict.fromkeys(it["source"] for it in items):
        lines.append(f"\n{src}")
        for it in (i for i in items if i["source"] == src):
            size = f"{it['text_chars']:,} chars" if it.get("text_chars") else ""
            lines.append(f"  [{it['status']}] {(it['published'] or '?')[:16]}  {it['title'][:70]}  {size}")
            if it.get("note"):
                lines.append(f"      {it['note'][:120]}")
    skipped = [s for s in skipped if not s.get("quiet")]
    if skipped:
        lines.append(f"\nSkipped ({len(skipped)}):")
        lines += [f"  {s['source']}: {s['title'][:60]}  ({s['reason'][:80]})" for s in skipped]
    if failed:
        lines.append("\nFAILED SOURCES: " + ", ".join(f["source"] for f in failed))
    lines.append(f"\nWrote {OUT.relative_to(fetch.ROOT)}")
    return "\n".join(lines)


def mark_done():
    """Run after a brief is published: remember these items so they don't repeat."""
    data = json.loads(OUT.read_text())
    state = load_state()
    done = data["items"] + [s for s in data["skipped"] if "will retry" not in s["reason"]]
    for it in done:
        state["seen"][it["link"]] = data["collected_at"]
        state["pending"].pop(it["link"], None)
    shown = state.setdefault("shown_titles", {})  # Levity: catch the same episode under a new link
    for it in data["items"]:
        if it["section"] == "levity":
            shown[it["title"]] = data["collected_at"]
    state["last_brief_at"] = data["collected_at"]
    cutoff = now() - timedelta(days=SEEN_DAYS)
    state["seen"] = {k: v for k, v in state["seen"].items() if parse(v) > cutoff}
    state["shown_titles"] = {k: v for k, v in shown.items() if parse(v) > cutoff}
    save_state(state)
    print(f"Marked {len(done)} items as briefed. Next brief starts from {data['collected_at'][:16]} UTC.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark-done", action="store_true", help="remember the last collected items")
    ap.add_argument("--since", help="override the window start, e.g. 2026-09-30")
    ap.add_argument("--no-whisper", action="store_true", help="skip podcast transcription")
    ap.add_argument("--whisper-model", default="small.en",
                    help="small.en (default), base.en (faster), medium.en (better, slower)")
    args = ap.parse_args()
    return mark_done() if args.mark_done else collect(args)


if __name__ == "__main__":
    sys.exit(main())
