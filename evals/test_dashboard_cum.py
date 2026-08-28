#!/usr/bin/env python3
"""CHI-46 / AFFL-026: dashboard defaults to Cumulative / all-time."""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def main():
    js = (SITE / "app.js").read_text()
    html = (SITE / "index.html").read_text()

    if ">All</button>" not in js and "data-y=\"all\">All" not in js:
        fail("app.js missing All chip")
    if "years.includes(qsYear) ? qsYear : null" not in js:
        fail("default curYear is not null when no year query")
    if "DATA.latest" in js.split("let curYear")[1][:80]:
        fail("curYear still defaults to DATA.latest")
    if 'id="season-pane"' not in html:
        fail("index.html missing #season-pane")
    if 'id="cum-pane"' not in html:
        fail("index.html missing #cum-pane")
    if "function renderCumHome" not in js:
        fail("app.js missing renderCumHome")
    extra = "id=\"draft-note\"></div>\n    </div>\n  </section>"
    if extra in html:
        fail("index.html still has extra close-div after #draft-note")
    bust = re.search(r"app\.js\?v=(\d+)", html)
    if not bust:
        fail("index.html app.js not cache-busted")
    elif int(bust.group(1)) < 21:
        fail(f"app.js cache still v={bust.group(1)}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/index.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"index.html HTTP {code}")
        else:
            print("index.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"index.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
