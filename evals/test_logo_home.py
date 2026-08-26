#!/usr/bin/env python3
"""CHI-67 / AFFL-044: AFFL logo clicks through to home (index.html, no query)."""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []

PAGES = ("index.html", "teams.html", "wrapped.html", "players.html", "history.html")
ALL_HTML = (
    "index.html", "teams.html", "wrapped.html", "players.html", "history.html",
    "scoreboard.html", "draft.html", "trades.html", "roto.html", "awards.html",
    "dictionary.html",
)


def fail(msg):
    fails.append(msg)


def header_logo_href(html):
    """Return href of the <a> wrapping the header AFFL mark, or None."""
    header = re.search(r"<header\b[^>]*>(.*?)</header>", html, re.S | re.I)
    block = header.group(1) if header else html
    m = re.search(
        r'<a\b([^>]*href=["\']([^"\']+)["\'][^>]*)>\s*'
        r'<img\b[^>]*class=["\'][^"\']*brand-logo[^"\']*["\']',
        block,
        re.S | re.I,
    )
    if m:
        return m.group(2)
    m = re.search(
        r'<a\b([^>]*)>\s*<img\b[^>]*src=["\'][^"\']*affl-mark',
        block,
        re.S | re.I,
    )
    if m:
        hm = re.search(r'href=["\']([^"\']+)["\']', m.group(1))
        return hm.group(1) if hm else ""
    return None


def main():
    for page in ALL_HTML:
        html = (SITE / page).read_text()
        href = header_logo_href(html)
        if href is None:
            fail(f"{page}: header logo is not inside an <a>")
        elif href.split("?")[0] != "index.html":
            fail(f"{page}: header logo href is {href!r}, expected index.html")
        elif "?" in href or href != "index.html":
            fail(f"{page}: home link must be relative index.html with no query (got {href!r})")

    # required five
    for page in PAGES:
        html = (SITE / page).read_text()
        if header_logo_href(html) != "index.html":
            fail(f"{page}: required page missing index.html logo link")

    common = (SITE / "common.js").read_text()
    if "function mountHistoricToggle" not in common:
        fail("historic toggle mount missing from common.js")
    if "Historic teams" not in common:
        fail("historic toggle label missing")
    if "function stampNav" not in common:
        fail("stampNav missing")
    # stampNav must not rewrite the brand-home link
    if 'querySelectorAll(".site-nav a")' not in common:
        fail("stampNav no longer scoped to .site-nav a (would clobber brand-home)")

    css = (SITE / "styles.css").read_text()
    if ".former-toggle" not in css:
        fail("historic toggle styles missing")

    for page in PAGES:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8765/" + page, timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            if code != 200:
                fail(f"{page} HTTP {code}")
            else:
                print(f"{page} HTTP 200")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{page} not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
