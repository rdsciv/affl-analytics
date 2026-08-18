#!/usr/bin/env python3
"""CHI-51: FantasyGenius player extras added; existing sections kept; Peterson path intact."""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []

EXISTING = [
    "pl-hero", "player-year-picker", "pl-chart", "pl-journey", "pl-college",
    "pl-ngs-profile", "pl-season-tbl", "pl-franchise-tbl", "pl-log",
    "pl-money", "pl-compare", "wopr-persist",
]
NEW = [
    "pl-fg-strip", "pl-custody", "pl-custody-tbl", "pl-achievements",
    "pl-avg-line", "pl-swarm", "pl-owner-range", "pl-log-filters",
]


def fail(msg):
    fails.append(msg)


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()

    for i in EXISTING:
        if f'id="{i}"' not in html:
            fail(f"existing section #{i} missing from players.html")
    for i in NEW:
        if f'id="{i}"' not in html:
            fail(f"new id #{i} missing from players.html")

    for fn in ("function renderFgStrip", "function renderCustody", "function renderAchievements",
               "function renderFgCharts", "function rosterStints", "function yearHome"):
        if fn not in js:
            fail(f"players.js missing {fn}")

    if "Traded" not in js or "Finished with" not in js:
        fail("Peterson journey labels Traded / Finished with missing")
    if "One-team stretch" in js:
        fail("journey still uses One-team stretch")
    if "before W1" not in js:
        fail("draft-before-W1 stint missing")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html missing players.js cache")
    elif int(bust.group(1)) < 25:
        fail(f"players.js cache still v={bust.group(1)}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("existing player sections kept; FG ids present; journey still Traded / Finished with")
    return 0


if __name__ == "__main__":
    sys.exit(main())
