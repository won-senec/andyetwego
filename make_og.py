#!/usr/bin/env python3
"""
make_og.py — build 1200x630 link-preview images for entries that have a photo.

LinkedIn (and most other platforms) only render the large preview card when the
image is at least 1200x627. The site's hero photos are 1100px wide, just under,
so each entry's own picture is cover-cropped onto a 1200x630 canvas and written
to images/og/<entry file, lowercased>.jpg.

generate.py prefers that file when it exists, falls back to the entry's hero
photo, then to images/og-default.png.

Run after adding an entry that has a hero photo:   python3 make_og.py
Needs Pillow.  Entries that open on a topic placeholder are skipped on purpose —
they keep the default share card.
"""
import re, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "images" / "og"
TARGET = (1200, 630)
MIN_SOURCE = 800          # below this, centre on slate instead of cropping

# Same marker generate.py reads, so the hero photo is the one the page opens with.
IMAGE_RE = re.compile(
    r'<!--\s*\*\*\*\s*Image Link\s*-->.*?<img\s+src="([^"]*)"',
    re.IGNORECASE | re.DOTALL)


def hero(entry: Path):
    m = IMAGE_RE.search(entry.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else ""


def build(src: Path, dest: Path) -> str:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if max(w, h) < MIN_SOURCE:
        # Too small to fill the frame without going soft. Sit it on the site's
        # slate instead, so the card still shows the real picture at its own size.
        scale = min(TARGET[0] / w, TARGET[1] / h)       # contain
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        canvas = Image.new("RGB", TARGET, (40, 50, 61))
        canvas.paste(im, ((TARGET[0] - im.width) // 2, (TARGET[1] - im.height) // 2))
        canvas.save(dest, "JPEG", quality=88, optimize=True, progressive=True)
        return f"{w}x{h} -> 1200x630, centred on slate"
    scale = max(TARGET[0] / w, TARGET[1] / h)           # cover
    im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    left = (im.width - TARGET[0]) // 2
    top = (im.height - TARGET[1]) // 2
    im.crop((left, top, left + TARGET[0], top + TARGET[1])).save(
        dest, "JPEG", quality=88, optimize=True, progressive=True)
    return f"{w}x{h} -> 1200x630"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made = skipped = 0
    for entry in sorted(HERE.glob("entry_*.html")):
        if entry.name == "entry_TEMPLATE.html":
            continue
        rel = hero(entry)
        if not rel:
            print(f"  - {entry.name}: no hero photo, keeps the share card")
            skipped += 1
            continue
        src = HERE / rel
        if not src.exists():
            print(f"  ! {entry.name}: {rel} not found")
            skipped += 1
            continue
        dest = OUT_DIR / f"{entry.stem.lower()}.jpg"
        note = build(src, dest)
        print(f"  + {dest.relative_to(HERE)}  ({note})")
        made += 1
    print(f"\nDone. {made} preview image(s) written, {skipped} left on the share card.")


if __name__ == "__main__":
    sys.exit(main())
