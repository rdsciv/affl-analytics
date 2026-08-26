#!/usr/bin/env python3
"""CHI-89: Dashboard Milestones + Elo (Leagology-style, AFFL verified matchups)."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def main():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    js = (SITE / "app.js").read_text(encoding="utf-8")
    css = (SITE / "styles.css").read_text(encoding="utf-8")

    for i in ("elo-card", "elo-tbl", "elo-chart", "milestones-card", "ms-board", "ms-chase"):
        if f'id="{i}"' not in html:
            fail(f"index.html missing #{i}")

    for fn in (
        "function renderEloAndMilestones",
        "function renderEloTable",
        "function renderMsBoard",
        "elo.json",
        "milestones.json",
    ):
        if fn not in js:
            fail(f"app.js missing {fn}")

    if ".ms-row" not in css or "#elo-card" not in css:
        fail("styles.css missing milestone/elo rules")

    bust = re.search(r"app\.js\?v=(\d+)", html)
    if not bust or int(bust.group(1)) < 18:
        fail("index.html app.js cache pin need v>=18")

    elo_path = SITE / "elo.json"
    ms_path = SITE / "milestones.json"
    if not elo_path.is_file():
        fail("missing site/elo.json — run scripts/compute_milestones_elo.py")
    if not ms_path.is_file():
        fail("missing site/milestones.json")

    elo = json.loads(elo_path.read_text(encoding="utf-8"))
    ms = json.loads(ms_path.read_text(encoding="utf-8"))

    if elo.get("evidence") != "verified":
        fail("elo.json evidence must be verified")
    if elo.get("ratedGames", 0) < 500:
        fail(f"elo ratedGames {elo.get('ratedGames')} too low")
    table = elo.get("table") or []
    if len(table) < 10:
        fail(f"elo table only {len(table)} managers")
    top = table[0]
    if not (1400 <= float(top.get("rating", 0)) <= 2000):
        fail(f"top elo out of band: {top}")
    # Newton should be competitive given 2025 dominance
    names = " ".join(r.get("name", "") for r in table[:5])
    print(f"elo_top5={names} rated={elo['ratedGames']}")

    boards = ms.get("boards") or []
    if len(boards) < 6:
        fail(f"milestones boards {len(boards)} < 6")
    wins25 = next((b for b in boards if b.get("id") == "wins-25"), None)
    if not wins25 or not (wins25.get("rows") or []):
        fail("wins-25 board empty")
        fastest = {}
    else:
        fastest = wins25["rows"][0]
    if fastest and fastest.get("games", 999) > 80:
        fail(f"fastest to 25 wins looks wrong: {fastest}")
    if ms.get("evidence") != "verified":
        fail("milestones evidence must be verified")
    if fastest:
        print(
            f"ms_wins25={fastest.get('name')} in {fastest.get('games')}g "
            f"boards={len(boards)} chase={len(ms.get('chase') or [])}"
        )

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/index.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"index.html HTTP {code}")
        body = r.read().decode("utf-8", errors="ignore")
        if 'id="elo-card"' not in body:
            fail("served index.html missing elo-card")
        print("index.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"index not reachable: {e}")

    for path in ("elo.json", "milestones.json"):
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:8765/{path}", timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            if code != 200:
                fail(f"{path} HTTP {code}")
            else:
                print(f"{path} HTTP 200")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{path} not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-89: Elo + Milestones on dashboard all-time pane")
    return 0


if __name__ == "__main__":
    sys.exit(main())
