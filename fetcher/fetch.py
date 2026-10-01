#!/usr/bin/env python3
"""Daily Brief feed fetcher (Stage 1).

Reads config/sources.json, resolves each source to a feed URL, fetches the
latest items, and (for YouTube) checks that captions are available.

Outputs:
  data/raw/feeds.json   full fetched data incl. caption text (gitignored, never published)
  stdout                a human-readable report of what each source returned

Usage: python fetcher/fetch.py [--limit N] [--no-captions]
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
RESOLVED = ROOT / "config" / "resolved.json"
OUT = ROOT / "data" / "raw" / "feeds.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 DailyBrief/0.1")
# Some hosts (e.g. Substack) 403 browser-like UAs from datacenter IPs but allow feed readers.
ALT_UAS = ["Feedly/1.0 (+http://www.feedly.com/fetcher.html; like FeedFetcher-Google)",
           "feedparser/6.0 +https://github.com/kurtmckee/feedparser",
           "curl/8.5.0"]
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def get(url, **kw):
    kw.setdefault("timeout", 20)
    for attempt in range(3):
        try:
            r = session.get(url, **kw)
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 ** attempt * 2)
                continue
            return r
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt * 2)


def clean(html, n=300):
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n] + ("…" if len(text) > n else "")


def iso(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc).isoformat() if t else None


# ---------- resolvers: turn a config entry into a feed URL ----------

def resolve_podcast(src, notes):
    if src.get("feed_url"):
        return [src["feed_url"]]
    r = get("https://itunes.apple.com/search",
            params={"term": src["itunes_search"], "entity": "podcast", "limit": 5})
    r.raise_for_status()
    results = r.json().get("results", [])
    for res in results:
        notes.append(f"iTunes match: {res.get('collectionName')!r} by {res.get('artistName')!r}")
    return [res["feedUrl"] for res in results if res.get("feedUrl")][:1]


def channel_id_from_html(html):
    for pat in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                r'"externalId":"(UC[\w-]{22})"',
                r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def resolve_youtube(src, notes):
    """Return feed URLs for every candidate channel; fetch loop keeps the first with videos."""
    feed = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
    if src.get("channel_id"):
        return [feed.format(src["channel_id"])]
    cookies = {"CONSENT": "YES+1", "SOCS": "CAI"}
    ids = []
    for h in src.get("handles", []):
        try:
            r = get(f"https://www.youtube.com/@{h}", cookies=cookies)
        except requests.RequestException as e:
            notes.append(f"handle @{h}: {type(e).__name__}")
            continue
        cid = channel_id_from_html(r.text) if r.status_code == 200 else None
        notes.append(f"handle @{h} -> {cid or f'HTTP {r.status_code}'}")
        if cid:
            ids.append(cid)
    if src.get("search"):
        r = get("https://www.youtube.com/results",
                params={"search_query": src["search"], "sp": "EgIQAg=="}, cookies=cookies)
        found = list(dict.fromkeys(re.findall(r'"channelId":"(UC[\w-]{22})"', r.text)))[:3]
        notes.append(f"search {src['search']!r} -> {', '.join(found) or 'nothing'}")
        ids += found
    return [feed.format(i) for i in dict.fromkeys(ids)]


def resolve_bluesky(src, notes):
    api = "https://public.api.bsky.app/xrpc"
    cands = list(src.get("handles", []))
    searches = src.get("search") or []
    for q in [searches] if isinstance(searches, str) else searches:
        r = get(f"{api}/app.bsky.actor.searchActors", params={"q": q, "limit": 10})
        if r.ok:
            cands += [a["handle"] for a in r.json().get("actors", [])]
    cands = list(dict.fromkeys(cands))
    profiles = []
    if cands:
        r = get(f"{api}/app.bsky.actor.getProfiles", params=[("actors", c) for c in cands[:25]])
        if r.ok:
            profiles = r.json().get("profiles", [])
    if not profiles:
        return []
    hints = [h.lower() for h in src.get("bio_hint", [])]

    def score(p):
        bio = f"{p.get('description', '')} {p.get('displayName', '')}".lower()
        return (any(h in bio for h in hints), p.get("followersCount", 0))
    profiles.sort(key=score, reverse=True)
    for p in profiles[:4]:
        notes.append(f"candidate @{p['handle']} {p.get('displayName')!r} "
                     f"followers={p.get('followersCount')} bio={clean(p.get('description'), 80)!r}")
    best = next((p for p in profiles if p["handle"] in src.get("handles", [])), profiles[0])
    if hints and not score(best)[0]:
        notes.append("WARNING: no candidate bio matched bio_hint; set an exact handle in sources.json")
    notes.append(f"using @{best['handle']} ({best['did']})")
    return [f"https://bsky.app/profile/{best['did']}/rss"]


RESOLVERS = {
    "podcast": resolve_podcast,
    "youtube": resolve_youtube,
    "bluesky": resolve_bluesky,
    "rss": lambda src, notes: src["urls"],
}


# ---------- captions ----------

def youtube_captions(video_id):
    """Return (status, text). Text stays in data/raw only (never published).
    Tries youtube-transcript-api first, then yt-dlp's caption tracks."""
    errors = []
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        snippets = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US"])
        return "ok (youtube-transcript-api)", "\n".join(
            f"[{int(s.start)//60}:{int(s.start)%60:02d}] {s.text}" for s in snippets)
    except Exception as e:  # noqa: BLE001
        errors.append(f"transcript-api {type(e).__name__}")
    try:
        import yt_dlp
        opts = {"skip_download": True, "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        tracks = (info.get("subtitles") or {}).get("en") or \
                 (info.get("automatic_captions") or {}).get("en") or []
        url = next((t["url"] for t in tracks if t.get("ext") == "json3"), None)
        if not url:
            errors.append("yt-dlp: no English caption track")
        else:
            events = get(url).json().get("events", [])
            lines = [f"[{e['tStartMs']//60000}:{e['tStartMs']//1000%60:02d}] "
                     + "".join(seg.get("utf8", "") for seg in e["segs"]).strip()
                     for e in events if e.get("segs")]
            text = "\n".join(l for l in lines if not l.endswith("] "))
            if text:
                return "ok (yt-dlp)", text
            errors.append("yt-dlp: empty caption track")
    except Exception as e:  # noqa: BLE001
        errors.append(f"yt-dlp {type(e).__name__}: {clean(str(e), 120)}")
    return "fail: " + " | ".join(errors), None


# ---------- main ----------

def fetch_source(src, limit, captions):
    notes = []
    result = {"id": src["id"], "name": src["name"], "kind": src["kind"],
              "section": src["section"], "ok": False, "items": [], "notes": notes}
    try:
        urls = RESOLVERS[src["kind"]](src, notes)
    except Exception as e:  # noqa: BLE001
        notes.append(f"resolve error: {type(e).__name__}: {e}")
        urls = []
    if not urls:
        notes.append("could not resolve a feed URL")
        return result

    for url in urls:
        try:
            r = get(url)
            for ua in ALT_UAS:
                if r.status_code != 403:
                    break
                notes.append(f"{url}: HTTP 403, retrying as {ua.split('/')[0]!r}")
                r = get(url, headers={"User-Agent": ua})
        except Exception as e:  # noqa: BLE001
            notes.append(f"{url}: {type(e).__name__}")
            continue
        feed = feedparser.parse(r.content)
        if r.status_code != 200 or not feed.entries:
            notes.append(f"{url}: HTTP {r.status_code}, {len(feed.entries)} entries")
            continue
        result.update(ok=True, feed_url=url, feed_title=feed.feed.get("title"),
                      total_entries=len(feed.entries))
        for e in feed.entries[:limit]:
            summary = clean(e.get("summary") or e.get("description"), 400)
            item = {"title": e.get("title") or clean(summary, 90), "link": e.get("link"), "published": iso(e),
                    "summary": summary}
            if src["kind"] == "podcast":
                enc = next((l for l in e.get("links", []) if l.get("rel") == "enclosure"), None)
                item["audio_url"] = enc.get("href") if enc else None
                item["duration"] = e.get("itunes_duration")
            if src["kind"] == "youtube":
                item["video_id"] = e.get("yt_videoid")
            result["items"].append(item)
        if url != urls[0]:
            notes.append(f"using fallback feed ({url[:60]}…)")
        break

    if result["ok"] and src["kind"] == "youtube" and captions:
        for item in result["items"][:2]:
            status, text = youtube_captions(item["video_id"])
            item["captions_status"] = status
            if text:
                item["captions_chars"] = len(text)
                item["captions"] = text
            time.sleep(1)
    return result


def report(results):
    lines = ["=" * 72, "DAILY BRIEF — FEED FETCH REPORT  " +
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "=" * 72]
    for r in results:
        flag = "OK  " if r["ok"] else "FAIL"
        lines.append(f"\n[{flag}] {r['name']}  ({r['kind']})")
        if r["ok"]:
            lines.append(f"  feed: {r['feed_url']}")
            lines.append(f"  title: {r.get('feed_title')!r}  entries in feed: {r['total_entries']}")
        for n in r["notes"]:
            lines.append(f"  · {n}")
        for it in r["items"]:
            lines.append(f"  - {(it['published'] or '?')[:16]}  {it['title']}")
            lines.append(f"      {it['link']}")
            if it.get("summary"):
                lines.append(f"      summary: {it['summary'][:160]}")
            if "audio_url" in it:
                lines.append(f"      audio: {it['audio_url']}  duration: {it.get('duration')}")
            if "captions_status" in it:
                extra = f" ({it['captions_chars']} chars)" if it.get("captions_chars") else ""
                lines.append(f"      captions: {it['captions_status']}{extra}")
                if it.get("captions"):
                    lines.append(f"      first line: {it['captions'].splitlines()[0][:120]}")
    ok = sum(r["ok"] for r in results)
    lines.append(f"\nSUMMARY: {ok}/{len(results)} sources OK")
    failed = [r["name"] for r in results if not r["ok"]]
    if failed:
        lines.append("FAILED: " + ", ".join(failed))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--no-captions", action="store_true")
    args = ap.parse_args()

    sources = json.loads(CONFIG.read_text())["sources"]
    results = [fetch_source(s, args.limit, not args.no_captions) for s in sources]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
                               "sources": results}, indent=2, ensure_ascii=False))
    print(report(results))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
