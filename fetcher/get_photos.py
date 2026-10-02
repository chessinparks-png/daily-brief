#!/usr/bin/env python3
"""Download the hero photos listed in config/photo_titles.txt into photos/.

Only files that Wikimedia Commons marks "Public domain" AND credits to the National Park
Service are kept. Each is resized to 800 px wide (small for phones) and saved as a JPEG,
and photos/photos.json lists them with a credit line. Run once, or again after editing the list:

    python fetcher/get_photos.py
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TITLES = ROOT / "config" / "photo_titles.txt"
OUT = ROOT / "photos"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "TheBlackBrief/1.0 (personal news app)"}
WIDTH, QUALITY = 800, 62


def get(url, **kw):
    for attempt in range(6):
        r = requests.get(url, headers=HEADERS, timeout=60, **kw)
        if r.status_code == 200:
            return r
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def main():
    titles = [t.strip() for t in TITLES.read_text().splitlines() if t.strip() and not t.startswith("#")]
    OUT.mkdir(exist_ok=True)
    manifest = []
    for n, title in enumerate(titles, 1):
        info = get(API, params={
            "action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": WIDTH, "iiextmetadatafilter": "LicenseShortName|Artist|Credit|ImageDescription",
        }).json()
        page = next(iter(info["query"]["pages"].values()))
        ii = (page.get("imageinfo") or [None])[0]
        if not ii:
            print(f"SKIP {title}: not found")
            continue
        meta = ii["extmetadata"]
        lic = plain(meta.get("LicenseShortName", {}).get("value"))
        artist = plain(meta.get("Artist", {}).get("value"))
        credit = plain(meta.get("Credit", {}).get("value"))
        if "ublic domain" not in lic or not re.search(r"National Park Service|NPS", f"{artist} {credit}"):
            print(f"SKIP {title}: license {lic!r}, credit {credit[:50]!r}")
            continue
        img = Image.open(io.BytesIO(get(ii["thumburl"]).content)).convert("RGB")
        if img.width > WIDTH:
            img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        name = f"park-{n:02d}.jpg"
        img.save(OUT / name, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        person = "" if re.search(r"NPS|National Park Service|^unknown$", artist, re.I) or len(artist) > 40 else artist
        manifest.append({
            "file": name,
            "credit": "NPS Photo" + (f" / {person}" if person else ""),
            "title": plain(title.removeprefix("File:").rsplit(".", 1)[0])[:90],
            "source": ii["descriptionurl"],
            "license": lic,
        })
        print(f"ok {name}  {(OUT / name).stat().st_size // 1024} KB  {manifest[-1]['credit']}  {manifest[-1]['title'][:50]}")
        time.sleep(1)
    (OUT / "photos.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"\n{len(manifest)} photos, {sum(p.stat().st_size for p in OUT.glob('*.jpg')) // 1024} KB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
