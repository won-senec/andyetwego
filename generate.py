#!/usr/bin/env python3
"""
generate.py  —  Thumbnail/featured card generator for "and yet we go".

HOW TO USE
----------
1. In any page (home.html, entries_films.html, ...) drop a one-line placeholder
   where you want a card to appear:

       <!-- thumbnail-entry_Films_Sinners.html -->   small card (Latest Entries scale)
       <!-- featured-entry_Films_Sinners.html -->    big card  (Featured Entry scale)

   Both refer to the file  entry_Films_Sinners.html  in the same folder.

2. Run:   python3 generate.py
   The script reads each referenced entry file, pulls the fields marked with
   <!--*** Topic -->, <!--*** Date -->, etc., and writes the card right after
   the placeholder, closed with a matching tag, e.g.
   <!-- /thumbnail-entry_Films_Sinners.html -->.

3. Edit an entry and run again any time — cards are regenerated in place.

No server, no dependencies. Works on double-clicked file:// pages.
"""

import re
import sys
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Pages to scan by default (any .html that can hold placeholders).
DEFAULT_PAGES = [
    "home.html",
    "entries_all.html",
    "entries_films.html",
    "entries_thoughts.html",
    "entries_creations.html",
]

# Placeholder:  <!-- thumbnail-entry_Films_Sinners.html -->
#           or  <!-- featured-entry_Films_Sinners.html -->
OPEN_RE = re.compile(
    r'<!--\s*(featured|thumbnail)-(entry_[^\s]+?\.html)\s*-->',
    re.IGNORECASE,
)


# ----------------------------------------------------------------------
# Field extraction from an entry_*.html file
# ----------------------------------------------------------------------
def _marker(label, after):
    """Regex: a <!--*** label --> comment followed somewhere by `after`."""
    return re.compile(
        r'<!--\s*\*\*\*\s*' + label + r'\s*-->\s*' + after,
        re.IGNORECASE | re.DOTALL,
    )

IMAGE_RE   = _marker(r'Image Link', r'<img\s+src="([^"]*)"(?:\s+alt="([^"]*)")?')
TOPIC_RE   = _marker(r'Topic',      r'.*?<span\s+class="(badge[^"]*)">\s*([^<]+?)\s*</span>')
DATE_RE    = _marker(r'Date',       r'.*?<span[^>]*>\s*([^<]+?)\s*</span>')
TITLE_RE   = _marker(r'Title',      r'.*?<h[1-3][^>]*>\s*([^<]+?)\s*</h[1-3]>')
LIKES_RE   = _marker(r'Likes\s*#?', r'.*?<span\s+class="like-count">\s*([^<]+?)\s*</span>')
# Tagline value lives *inside* the comment:  <!--*** Tagline: ... -->
TAGLINE_RE = re.compile(r'<!--\s*\*\*\*\s*Tagline:\s*(.*?)\s*-->', re.IGNORECASE | re.DOTALL)


def extract(entry_path: Path) -> dict:
    text = entry_path.read_text(encoding="utf-8")

    def first(rx, *groups, default=""):
        m = rx.search(text)
        if not m:
            return default if len(groups) == 1 else (default,) * len(groups)
        if len(groups) == 1:
            return (m.group(groups[0]) or "").strip()
        return tuple((m.group(g) or "").strip() for g in groups)

    img_src, img_alt = first(IMAGE_RE, 1, 2, default="")
    badge_class, topic = first(TOPIC_RE, 1, 2, default="")
    tagline_raw = first(TAGLINE_RE, 1)
    # Collapse internal whitespace/newlines in the tagline.
    tagline = re.sub(r'\s+', ' ', tagline_raw).strip()

    return {
        "img_src":     img_src or "",
        "img_alt":     img_alt or topic or "",
        "badge_class": badge_class or "badge",
        "topic":       topic or "",
        "date":        first(DATE_RE, 1),
        "title":       first(TITLE_RE, 1),
        "tagline":     tagline,
        "likes":       first(LIKES_RE, 1) or "0",
        "href":        entry_path.name,
    }


# ----------------------------------------------------------------------
# Card templates
# ----------------------------------------------------------------------
def _esc(s):
    return html.escape(s, quote=True)


# badge class -> (placeholder modifier, Font Awesome icon, fallback label)
PILLAR = {
    "badge-thoughts":  ("ph-thoughts",  "fa-lightbulb", "Thoughts"),
    "badge-creations": ("ph-creations", "fa-code",      "Creations"),
    "badge-reviews":   ("ph-reviews",   "fa-film",      "Reviews"),
}


def _image_block(d: dict, img_classes: str, placeholder_classes: str) -> str:
    """Return an <img> when the entry has an image, else a branded,
    topic-tinted placeholder tile so the card never shows a blank box
    or a broken-image icon."""
    if d["img_src"]:
        return (f'<img src="{_esc(d["img_src"])}" alt="{_esc(d["img_alt"])}" '
                f'class="{img_classes}">')
    mod, icon, fallback = ("ph-creations", "fa-feather-pointed", "")
    for key, spec in PILLAR.items():
        if key in d["badge_class"]:        # badge_class is e.g. "badge badge-thoughts"
            mod, icon, fallback = spec
            break
    label = d["topic"] or fallback
    return (f'<div class="thumb-placeholder {mod} {placeholder_classes}">'
            f'<span class="ph-icon"><i class="fas {icon}"></i></span>'
            f'<span class="ph-label">{_esc(label)}</span></div>')


def thumbnail_card(d: dict, indent: str) -> str:
    image = _image_block(d, "w-full h-48 object-cover", "w-full h-48")
    card = f'''<article class="post-card bg-white rounded-xl overflow-hidden shadow-md animate-fade-in">
    {image}
    <div class="p-6">
        <div class="flex items-center mb-4">
            <span class="{_esc(d["badge_class"])}">{_esc(d["topic"])}</span>
            <span class="text-gray-400 text-sm ml-4">{_esc(d["date"])}</span>
        </div>
        <h3 class="text-lg font-bold mb-3 text-gray-900">{_esc(d["title"])}</h3>
        <p class="text-gray-600 mb-4">{_esc(d["tagline"])}</p>
        <a href="{_esc(d["href"])}" class="read-more-link text-indigo-600 font-semibold inline-flex items-center">
            Read More
            <i class="fas fa-arrow-right ml-2 text-sm"></i>
        </a>
        <div class="flex items-center mt-5 space-x-6 text-sm">
            <button class="like-button flex items-center text-gray-500 hover:text-red-500 transition" data-liked="false">
                <i class="far fa-heart mr-2"></i>
                <span class="like-count">{_esc(d["likes"])}</span>
            </button>
            <button class="share-button flex items-center text-gray-500 hover:text-indigo-600 transition">
                <i class="fas fa-share-alt mr-2"></i> Share
            </button>
        </div>
    </div>
</article>'''
    return "\n".join(indent + line for line in card.splitlines())


def featured_card(d: dict, indent: str) -> str:
    image = _image_block(d, "w-full h-full object-cover", "w-full h-full")
    card = f'''<article class="post-card featured-card bg-white rounded-xl overflow-hidden animate-fade-in max-w-5xl w-full">
    <div class="flex flex-col md:flex-row">
        <div class="md:w-1/2 p-8 flex flex-col justify-center">
            <div class="flex items-center mb-4">
                <span class="{_esc(d["badge_class"])}">{_esc(d["topic"])}</span>
                <span class="text-gray-400 text-sm ml-4">{_esc(d["date"])}</span>
            </div>
            <h3 class="text-2xl font-bold mb-4 text-gray-900">{_esc(d["title"])}</h3>
            <p class="text-gray-600 mb-6">{_esc(d["tagline"])}</p>
            <a href="{_esc(d["href"])}" class="read-more-link text-indigo-600 font-semibold inline-flex items-center">
                Read More
                <i class="fas fa-arrow-right ml-2 text-sm"></i>
            </a>
            <div class="flex items-center mt-6 space-x-6 text-sm">
                <button class="like-button flex items-center text-gray-500 hover:text-red-500 transition" data-liked="false">
                    <i class="far fa-heart mr-2"></i>
                    <span class="like-count">{_esc(d["likes"])}</span>
                </button>
                <button class="share-button flex items-center text-gray-500 hover:text-indigo-600 transition">
                    <i class="fas fa-share-alt mr-2"></i> Share
                </button>
            </div>
        </div>
        <div class="md:w-1/2 h-64 md:h-auto">
            {image}
        </div>
    </div>
</article>'''
    return "\n".join(indent + line for line in card.splitlines())


# ----------------------------------------------------------------------
# Page processing
# ----------------------------------------------------------------------
def process_page(page: Path) -> int:
    text = page.read_text(encoding="utf-8")
    count = 0

    out = []
    pos = 0
    for m in OPEN_RE.finditer(text):
        open_tag = m.group(0)
        variant = m.group(1).lower()
        entry_name = m.group(2)
        is_featured = (variant == "featured")

        # Indentation of the placeholder line, reused for the generated card.
        line_start = text.rfind("\n", 0, m.start()) + 1
        indent = re.match(r'[ \t]*', text[line_start:m.start()]).group(0)

        close_tag = f'<!-- /{variant}-{entry_name} -->'

        entry_path = HERE / entry_name
        if not entry_path.exists():
            print(f"  ! {page.name}: missing {entry_name} — skipped")
            # Keep text up to and including the placeholder untouched.
            out.append(text[pos:m.end()])
            pos = m.end()
            continue

        data = extract(entry_path)
        card = featured_card(data, indent) if is_featured else thumbnail_card(data, indent)

        # Emit everything before the placeholder, then open tag + card + close tag.
        out.append(text[pos:m.start()])
        out.append(f'{open_tag}\n{card}\n{indent}{close_tag}')

        # Swallow any previously generated block for this entry that follows the
        # placeholder, whatever prefix it used (featured/thumbnail/post), so re-runs
        # and renames replace in place. Bound the search to before the next
        # placeholder so we never reach into a different block.
        next_open = OPEN_RE.search(text, m.end())
        limit = next_open.start() if next_open else len(text)
        close_re = re.compile(
            r'<!--\s*/(?:featured|thumbnail|post)-' + re.escape(entry_name) + r'\s*-->',
            re.IGNORECASE,
        )
        existing = close_re.search(text, m.end(), limit)
        pos = existing.end() if existing else m.end()

        count += 1
        print(f"  + {page.name}: {entry_name} ({variant})")

    out.append(text[pos:])
    new_text = "".join(out)

    if new_text != text:
        page.write_text(new_text, encoding="utf-8")
    return count


def main(argv):
    pages = argv[1:] if len(argv) > 1 else DEFAULT_PAGES
    total = 0
    for name in pages:
        page = HERE / name
        if not page.exists():
            continue
        total += process_page(page)
    print(f"Done. {total} card(s) generated.")


if __name__ == "__main__":
    main(sys.argv)
