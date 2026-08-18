#!/usr/bin/env python3
"""CHI-53 / AFFL-034: FantasyGenius-style Data Dictionary.

Static file checks. Does not require a browser.
"""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []

REQUIRED_NAMES = (
    "PAR",
    "Luck Index",
    "All-Play",
    "Handcuff",
    "Homer",
    "Draft Stack",
    "WOPR",
    "FAAB",
    "Sacko",
    "Point Title",
    "Maximum Potential",
)

BANNED = (
    "FG Start %",
    "Correct Decision Rate",
    "CDR",
)


def fail(msg):
    fails.append(msg)


def main():
    html_path = SITE / "dictionary.html"
    js_path = SITE / "dictionary.js"
    css_path = SITE / "styles.css"

    if not html_path.exists():
        fail("dictionary.html missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    html = html_path.read_text()
    js = js_path.read_text() if js_path.exists() else ""
    css = css_path.read_text() if css_path.exists() else ""

    if 'id="dict-search"' not in html and 'type="search"' not in html:
        fail("dictionary.html missing search input")
    for chip in ("ALL", "DRAFT", "LEAGUE", "PLAYERS"):
        if chip not in html:
            fail(f"dictionary.html missing {chip} chip")
    if not re.search(r'<a[^>]+href="dictionary.html"[^>]*class="on"', html):
        fail("dictionary.html nav Dictionary link missing class=on")

    for path in sorted(SITE.glob("*.html")):
        text = path.read_text()
        if 'class="site-nav"' not in text:
            continue
        if path.name == "dictionary.html":
            continue
        if "dictionary.html" not in text:
            fail(f"{path.name} site-nav missing dictionary.html")

    if not js_path.exists():
        fail("dictionary.js missing")
    else:
        for name in REQUIRED_NAMES:
            if name not in js:
                fail(f"dictionary.js missing required term {name}")
        for bad in BANNED:
            if bad in js:
                fail(f"dictionary.js must not contain {bad!r}")
        low = js.lower()
        if "bottom half" not in low:
            fail("definitions missing 'bottom half'")
        if "allplay" not in low:
            fail("definitions missing 'allplay'")
        if "replacement" not in low:
            fail("definitions missing 'replacement'")
        if "scored spend" not in js and "PAR /" not in js:
            fail("definitions missing 'scored spend' or 'PAR /'")

    if ".dict-" not in css:
        fail("styles.css missing .dict- classes")
    nav = re.search(r"\.site-nav\s*\{[^}]+\}", css)
    if not nav or "flex-wrap" not in nav.group(0):
        fail("styles.css .site-nav missing flex-wrap")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/dictionary.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"dictionary.html HTTP {code}")
        else:
            print("dictionary.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
