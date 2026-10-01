#!/usr/bin/env python3
"""List the owner's NPS park photos for the app's opening screen.

Put the photos in site/parks/ (jpg, jpeg, png or webp), then run:
    python fetcher/parks.py
It writes site/parks/parks.json. The app shows one photo per day, in this order.
Park names come from the file names ("great-smoky-mountains.jpg" → "Great Smoky Mountains");
edit "park" or "credit" in parks.json to change them. Your edits are kept on the next run.
Only photos in this folder are ever shown; with none, the opening is plain green.
"""
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "site" / "parks"
OUT = DIR / "parks.json"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
BIG = 1_500_000  # bytes; bigger photos make the opening slow on a phone


def name_from(path):
    words = re.sub(r"[-_]+", " ", path.stem)
    words = re.sub(r"\s*\d+$", "", words).strip()  # "zion-2" → "zion"
    return words.title() or path.stem


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    old = {}
    if OUT.exists():
        try:
            old = {p["file"]: p for p in json.loads(OUT.read_text()) if isinstance(p, dict) and p.get("file")}
        except (ValueError, TypeError):
            old = {}
    photos = sorted(p for p in DIR.iterdir() if p.suffix.lower() in EXTS)
    out = []
    for p in photos:
        entry = {"file": p.name, "park": name_from(p), "credit": "NPS"}
        entry.update({k: v for k, v in old.get(p.name, {}).items() if k in ("park", "credit")})
        out.append(entry)
        size = p.stat().st_size
        flag = f"  (large: {size / 1e6:.1f} MB, consider resizing to ~2000 px wide)" if size > BIG else ""
        print(f"  {p.name}  →  {entry['park']}{flag}")
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {OUT.relative_to(DIR.parent.parent)} with {len(out)} photo(s).")
    if not out:
        print(f"No photos found. Copy your NPS park photos into {DIR} and run this again.")


if __name__ == "__main__":
    main()
