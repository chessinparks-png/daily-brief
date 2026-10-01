#!/usr/bin/env python3
"""Find new appearances by a comedian (Karlous Miller) for the "Laughs" section.

Free sources only: YouTube's public search page and Apple's iTunes Search API.
Keeps uploads from the last 7 days with the name in the title or description, and
skips clips, compilations, reaction videos, reuploads and repeats. Output is title,
channel/show and link only: no summary.

Usage (sample): python fetcher/laughs.py
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

DAYS = 7
MIN_MINUTES = 15  # guest spots, interviews, podcast episodes and sets run long; clips don't
JUNK = re.compile(r"compilation|funniest|funny moments|best moments|iconic moments|best of|"
                  r"\bclips?\b|react|reaction|remix|theme song|\bhours? of\b|marathon|"
                  r"\bcut\)|reupload|re-upload|#shorts", re.I)
YT_CONSENT = {"CONSENT": "YES+1", "SOCS": "CAI"}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {"the", "w", "with", "and", "a", "of", "in", "85", "south", "show"}


def similar(a, b):
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.7


def _text(x):
    x = x or {}
    return "".join(r.get("text", "") for r in x.get("runs", [])) or x.get("simpleText", "")


def _age_days(published):
    m = re.match(r"(?:Streamed )?(\d+)\s*(\w+)", published or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    per = {"s": 0, "m": 1 / 1440, "h": 1 / 24, "d": 1, "w": 7, "mo": 30, "y": 365}
    for k in ("mo", "s", "m", "h", "d", "w", "y"):  # "mo" before "m"
        if unit.startswith(k) and not (k == "m" and unit.startswith("mo")):
            return n * per[k]
    return None


def _minutes(length):
    parts = [int(p) for p in (length or "0").split(":") if p.isdigit()]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts))) / 60


def youtube_search(query, sp=None):
    params = {"search_query": query}
    if sp:
        params["sp"] = sp
    r = fetch.get("https://www.youtube.com/results", params=params, cookies=YT_CONSENT)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text)
    if not m:
        return []

    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                yield o["videoRenderer"]
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    out = []
    for v in walk(json.loads(m.group(1))):
        desc = "".join(r.get("text", "") for s in v.get("detailedMetadataSnippets", [])
                       for r in s.get("snippetText", {}).get("runs", []))
        badges = json.dumps(v.get("ownerBadges", []))
        out.append({"title": _text(v.get("title")), "show": _text(v.get("ownerText")),
                    "link": f"https://www.youtube.com/watch?v={v['videoId']}",
                    "age_days": _age_days(_text(v.get("publishedTimeText"))),
                    "minutes": _minutes(_text(v.get("lengthText"))), "description": desc,
                    "verified": "VERIFIED" in badges or "OFFICIAL_ARTIST" in badges,
                    "platform": "YouTube"})
    return out


def apple_episodes(query):
    r = fetch.get("https://itunes.apple.com/search",
                  params={"term": query, "entity": "podcastEpisode", "limit": 200, "country": "US"})
    now = datetime.now(timezone.utc)
    out = []
    for e in r.json().get("results", []) if r.ok else []:
        released = datetime.fromisoformat(e["releaseDate"].replace("Z", "+00:00"))
        out.append({"title": e.get("trackName", ""), "show": e.get("collectionName", ""),
                    "link": e.get("trackViewUrl"), "age_days": (now - released).total_seconds() / 86400,
                    "minutes": (e.get("trackTimeMillis") or 0) / 60000,
                    "description": e.get("description") or "", "verified": True,
                    "platform": "Apple Podcasts"})
    return out


def find(person, own_shows=(), already_shown=(), limit=2, verbose=False):
    """Return up to `limit` new appearances, plus every rejected candidate with the reason."""
    name = person.lower()
    surname = name.split()[-1]
    recent = youtube_search(f'"{person}"', sp="EgQIAxAB") + apple_episodes(person)  # this week, videos
    older = youtube_search(f'"{person}"')  # relevance-ranked, all ages: used to spot reuploads
    picked, rejected = [], []
    # Newest first by day; on the same day, YouTube before Apple so a cross-posted episode links to video.
    for c in sorted(recent, key=lambda c: (round(c["age_days"]) if c["age_days"] is not None else 99,
                                           c["platform"] != "YouTube")):
        own = any(s.lower() in c["show"].lower() for s in own_shows)
        reason = None
        if c["age_days"] is None or c["age_days"] > DAYS:
            reason = "older than 7 days"
        elif name not in f"{c['title']} {c['description']}".lower() and \
                not (own and surname in f"{c['title']} {c['description']}".lower()):
            reason = "name not in title/description"
        elif JUNK.search(f"{c['title']} {c['show']}"):
            reason = "clip / compilation / reaction"
        elif c["minutes"] < MIN_MINUTES:
            reason = f"too short ({c['minutes']:.0f} min)"
        elif not (c["verified"] or own):
            reason = "unverified channel (likely a reupload or clip channel)"
        elif any(similar(c["title"], p["title"]) or p["link"] == c["link"] for p in picked):
            reason = "same episode on another platform"
        elif c["platform"] == "YouTube" and any(
                similar(c["title"], o["title"]) and o["show"] != c["show"]
                and (o["age_days"] or 0) > (c["age_days"] or 0) for o in older):
            reason = "reupload of an older video"
        elif any(similar(c["title"], t) for t in already_shown):
            reason = "already shown"
        elif len(picked) >= limit:
            reason = f"over the daily limit of {limit}"
        if reason:
            rejected.append({**c, "reason": reason})
        else:
            picked.append(c)
    return picked, rejected


if __name__ == "__main__":
    src = next(s for s in json.loads(fetch.CONFIG.read_text())["sources"] if s["kind"] == "people_search")
    picked, rejected = find(src["person"], src.get("own_shows", []), limit=src.get("max_items", 2))
    print(f"PICKED ({len(picked)}):")
    for c in picked:
        print(f"  {c['title']}\n    {c['show']} · {c['platform']} · {c['age_days']:.0f}d ago · {c['minutes']:.0f} min\n    {c['link']}")
    print(f"\nREJECTED ({len(rejected)}), last 7 days only:")
    for c in rejected:
        if c["reason"] != "older than 7 days":
            print(f"  [{c['reason']}] {c['title'][:70]} — {c['show'][:30]} ({c['platform']})")
