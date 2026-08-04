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

Every run also refreshes the search-engine metadata, regardless of which pages
were passed on the command line:

  * a unique <title>, <meta name="description"> and absolute <link rel="canonical">
    in every page's <head> — entry pages read theirs from the <!--*** Title -->
    and <!--*** Tagline: --> markers, the rest come from STATIC_META below;
  * sitemap.xml, listing every indexable page;
  * robots.txt, pointing crawlers at that sitemap.

No server, no dependencies. Works on double-clicked file:// pages.
"""

import re
import sys
import html
from datetime import datetime
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
# Bare flag marker:  <!--*** New -->  anywhere in the entry marks it as new.
NEW_RE     = re.compile(r'<!--\s*\*\*\*\s*New\s*-->', re.IGNORECASE)


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
        "new":         bool(NEW_RE.search(text)),
    }


def _new_badge(d: dict) -> str:
    """Optional 'New' pill, shown when the entry carries a <!--*** New --> marker."""
    return ' <span class="badge badge-new ml-2">New</span>' if d.get("new") else ""


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

# badge class -> topic listing page the badge links to
TOPIC_PAGE = {
    "badge-thoughts":  "entries_thoughts.html",
    "badge-creations": "entries_creations.html",
    "badge-reviews":   "entries_films.html",
}


def _topic_badge(d: dict) -> str:
    """Render the topic badge as a link to its listing page, falling back to a
    plain span if the badge class has no known topic page."""
    badge_class = d["badge_class"]
    label = _esc(d["topic"])
    for key, page in TOPIC_PAGE.items():
        if key in badge_class:
            return f'<a href="{page}" class="{_esc(badge_class)}">{label}</a>'
    return f'<span class="{_esc(badge_class)}">{label}</span>'


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
            {_topic_badge(d)}{_new_badge(d)}
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
                {_topic_badge(d)}{_new_badge(d)}
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


# ----------------------------------------------------------------------
# Search-engine metadata: per-page head tags, sitemap.xml, robots.txt
# ----------------------------------------------------------------------
SITE_URL = "https://andyetwego.com"     # apex; www and http both 301 here
BRAND = "and yet we go"

# Pages with no <!--*** --> markers to read from, so their metadata lives here.
#   filename -> (title, description)
# Keep descriptions roughly 120-160 characters — Google rewrites ones that are
# too thin to be useful as a snippet.
STATIC_META = {
    "index.html": (
        f"{BRAND} — essays and film writing by Won Kyun Koh",
        "The world doesn’t pause for us, and what’s broken doesn’t mend on its own. "
        "And yet we go — one thought, one thing made, one story at a time.",
    ),
    "home.html": (
        f"{BRAND} — essays and film writing by Won Kyun Koh",
        "The world doesn’t pause for us, and what’s broken doesn’t mend on its own. "
        "And yet we go — one thought, one thing made, one story at a time.",
    ),
    "entries_all.html": (
        f"All entries — {BRAND}",
        "Every entry in one place: thoughts on living and working, things made, "
        "and writing about the films and shows worth sitting with.",
    ),
    "entries_thoughts.html": (
        f"Thoughts — {BRAND}",
        "Essays on parenting, work, money, AI, war, and belonging — the turn from "
        "what went wrong to what comes next.",
    ),
    "entries_films.html": (
        f"Reviews — {BRAND}",
        "Writing about films and shows: what they are really about underneath the "
        "plot, and why the good ones stay with you long after the credits.",
    ),
    "entries_creations.html": (
        f"Creations — {BRAND}",
        "Things made — projects, experiments, and work in progress from Won Kyun Koh.",
    ),
    "about.html": (
        f"About Won Kyun Koh — {BRAND}",
        "Molecular cell biology scientist, writer, and parent. “And yet” is the pivot "
        "from what went wrong to what comes next — this site is named after it.",
    ),
    "services.html": (
        f"Services — {BRAND}",
        "Services from Won Kyun Koh — currently under construction.",
    ),
    "contact.html": (
        f"Contact — {BRAND}",
        "Say hello. The world doesn’t pause for any of us — and yet we go, and the "
        "going is better in good company than alone.",
    ),
}

# Committed and publicly reachable, but deliberately kept out of sitemap.xml:
#   entry_TEMPLATE.html — scaffolding, not a real entry
#   index.html          — redirects to home.html, which is listed instead
#   services.html       — an "under construction" stub; add it once it has content
#   entry_Thoughts_love.html — withdrawn and deleted from the repo; see NOINDEX below
# Applies to entries and static pages alike. Naming a file that no longer
# exists is harmless — nothing matches it — and is deliberate here.
SITEMAP_SKIP = {
    "entry_TEMPLATE.html",
    "index.html",
    "services.html",
    "entry_Thoughts_love.html",
}

# index.html is a redirect stub, so it points at the page it redirects to.
CANONICAL_OVERRIDE = {"index.html": "home.html"}

# Pages that must stay out of search results entirely. Leaving a page out of
# sitemap.xml only declines to volunteer it — services.html is linked from the
# nav on every page, so Google would still crawl and index it, and an "under
# construction" stub is not what should come up under the site's own name.
# Drop a page from here and from SITEMAP_SKIP together, once it has content.
#
# entry_Thoughts_love.html is withdrawn — unlinked, then deleted outright, so
# its URL now 404s. It stays named here on purpose: restoring the file from git
# history would otherwise republish it silently on the next run, and quietly
# making private writing public again is the worse failure. Delete the name from
# both sets only when the intent really is to publish — as was done for
# entry_Thoughts_senseofbelonging.html, restored and republished on purpose.
# Applies to entries and static pages alike.
NOINDEX = {
    "services.html",
    "entry_Thoughts_love.html",
}

# Whole-line matches, so a replaced tag doesn't leave a blank line behind.
TITLE_TAG_RE = re.compile(r'([ \t]*)<title>.*?</title>', re.IGNORECASE | re.DOTALL)
DESC_TAG_RE  = re.compile(r'[ \t]*<meta\s+name=["\']description["\'][^>]*>[ \t]*\n?',
                          re.IGNORECASE)
CANON_TAG_RE = re.compile(r'[ \t]*<link\s+rel=["\']canonical["\'][^>]*>[ \t]*\n?',
                          re.IGNORECASE)
ROBOTS_TAG_RE = re.compile(r'[ \t]*<meta\s+name=["\']robots["\'][^>]*>[ \t]*\n?',
                           re.IGNORECASE)

# "June 24th, 2026" -> "June 24, 2026"
ORDINAL_RE = re.compile(r'\b(\d{1,2})(st|nd|rd|th)\b', re.IGNORECASE)


def iso_date(raw: str):
    """Entry date -> 'YYYY-MM-DD' for <lastmod>, or None if it won't parse."""
    cleaned = ORDINAL_RE.sub(r'\1', raw or "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def apply_head_meta(page: Path, title: str, description: str, canonical: str,
                    noindex: bool = False) -> bool:
    """Rewrite the page's <title> and re-emit its description/canonical directly
    beneath it. Idempotent: old tags are stripped first, so re-runs replace
    rather than accumulate — and dropping a page from NOINDEX removes the tag
    again rather than leaving it stranded."""
    text = page.read_text(encoding="utf-8")
    original = text

    m = TITLE_TAG_RE.search(text)
    if not m:
        print(f"  ! {page.name}: no <title> in <head> — metadata skipped")
        return False

    indent = m.group(1)
    text = text[:m.start()] + "\x00" + text[m.end():]   # placeholder, so removing
    text = DESC_TAG_RE.sub("", text)                    # the old description,
    text = CANON_TAG_RE.sub("", text)                   # canonical and robots
    text = ROBOTS_TAG_RE.sub("", text)                  # tags can't disturb it
    text = text.replace(
        "\x00",
        f'{indent}<title>{_esc(title)}</title>\n'
        f'{indent}<meta name="description" content="{_esc(description)}">\n'
        f'{indent}<link rel="canonical" href="{_esc(canonical)}">'
        + (f'\n{indent}<meta name="robots" content="noindex, follow">'
           if noindex else ""),
        1,
    )

    if text == original:
        return False
    page.write_text(text, encoding="utf-8")
    return True


def write_sitemap(urls) -> None:
    """urls: sequence of (absolute_url, lastmod_or_None), in the order to emit."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        lines.append('  <url>')
        lines.append(f'    <loc>{loc}</loc>')
        if lastmod:
            lines.append(f'    <lastmod>{lastmod}</lastmod>')
        lines.append('  </url>')
    lines.append('</urlset>')
    (HERE / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots() -> None:
    (HERE / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "# Scaffolding for new entries, not real content.\n"
        "Disallow: /entry_TEMPLATE.html\n"
        "\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def seo_pass() -> None:
    """Refresh head metadata on every page, then rewrite sitemap.xml/robots.txt."""
    entry_urls = []
    newest = None
    touched = 0

    for page in sorted(HERE.glob("entry_*.html")):
        if page.name == "entry_TEMPLATE.html":
            continue
        d = extract(page)
        if not d["title"]:
            # No <!--*** Title --> marker to read, so any title we invent would
            # be a duplicate of the brand. Leave the page alone and say so
            # rather than shipping a meaningless one to Google.
            print(f"  ! {page.name}: no <!--*** Title --> marker — "
                  f"no metadata written, left out of sitemap.xml")
            continue
        title = d["title"]
        description = d["tagline"] or f"{title} — an entry on {BRAND}."
        url = f"{SITE_URL}/{page.name}"
        if apply_head_meta(page, f"{title} — {BRAND}", description, url,
                           noindex=page.name in NOINDEX):
            touched += 1
        if page.name in SITEMAP_SKIP:
            # Withdrawn: keep it out of the sitemap, and out of the newest-entry
            # date that home and the listing pages advertise as their lastmod.
            continue
        lastmod = iso_date(d["date"])
        if lastmod and (newest is None or lastmod > newest):
            newest = lastmod
        entry_urls.append((url, lastmod))

    static_urls = []
    for name, (title, description) in STATIC_META.items():
        page = HERE / name
        if not page.exists():
            continue
        target = CANONICAL_OVERRIDE.get(name, name)
        url = f"{SITE_URL}/{target}"
        if apply_head_meta(page, title, description, url, noindex=name in NOINDEX):
            touched += 1
        if name not in SITEMAP_SKIP:
            # Home and the listing pages change whenever an entry lands; the
            # standing pages have no meaningful date to claim.
            static_urls.append((url, newest if name in DEFAULT_PAGES else None))

    write_sitemap(static_urls + entry_urls)
    write_robots()
    print(f"  + head metadata: {touched} page(s) updated")
    print(f"  + sitemap.xml: {len(static_urls) + len(entry_urls)} URL(s)")
    print("  + robots.txt")


def main(argv):
    pages = argv[1:] if len(argv) > 1 else DEFAULT_PAGES
    total = 0
    for name in pages:
        page = HERE / name
        if not page.exists():
            continue
        total += process_page(page)
    seo_pass()
    print(f"Done. {total} card(s) generated.")


if __name__ == "__main__":
    main(sys.argv)
