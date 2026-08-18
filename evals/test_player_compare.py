#!/usr/bin/env python3
"""Players landing: Flock-style compare cards.

Gates:
- compare card + per-game toggle on the landing
- AFFL / non-PPR labels, never PPR
- no Tittsburgh
- no invented juke / inside-5
- Gibbs 4429795 and Bijan 4430807 are the default pair and exist in compare_adv
- ranks are position ranks
- HTTP 200 on players.html if the local server is up
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

GIBBS = 4429795
BIJAN = 4430807


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()
    css = (SITE / "styles.css").read_text()
    adv_path = SITE / "compare_adv.json"
    if not adv_path.exists():
        fail("site/compare_adv.json missing")
        _done()
        return 1
    adv = json.loads(adv_path.read_text())

    if 'id="pl-compare"' not in html:
        fail("players.html missing #pl-compare")
    if 'id="pl-compare-grid"' not in html:
        fail("players.html missing #pl-compare-grid")
    if 'id="pl-compare-mode"' not in html:
        fail("players.html missing per-game toggle")
    if "Per game" not in html:
        fail("players.html missing Per game label")
    if html.find('id="pl-compare"') > html.find('id="pp-grid"'):
        fail("compare card sits after the player grid, not on the landing")
    if 'id="pp-search"' not in html or 'id="pp-grid"' not in html:
        fail("player search/grid was removed")

    if "function initCompare" not in js:
        fail("players.js missing initCompare")
    if "function renderCompare" not in js:
        fail("players.js missing renderCompare")
    if "4429795" not in js or "4430807" not in js:
        fail("default pair is not Gibbs/Bijan")
    if "AFFL FPpG" not in js:
        fail("players.js missing AFFL FPpG")
    if "AFFL non-PPR" not in js and "non-PPR" not in js:
        fail("compare does not say non-PPR")
    if "PPR Points" in js or "PPR pts" in js:
        fail("compare still says PPR")
    if "juke" in js.lower():
        fail("compare invents juke rate")
    if "inside 5" in js.lower() or "inside_5" in js:
        fail("compare invents rush-inside-5")
    if "Tittsburgh" in js or "Tittsburgh" in html:
        fail("Tittsburgh in compare UI")
    if "franchiseName" not in js[js.find("function cmpBundle"):js.find("function cmpMetricDefs")]:
        fail("compare cards do not use franchiseName")
    if "cmpRank" not in js:
        fail("players.js missing cmpRank")
    if "cmpPosPool" not in js:
        fail("ranks are not computed in a position pool")
    if ".cmp-grid" not in css or ".cmp-box.hi" not in css:
        fail("styles.css missing compare card / tier boxes")

    players = adv.get("players") or {}
    if str(GIBBS) not in players:
        fail("compare_adv missing Gibbs")
    else:
        g = players[str(GIBBS)]
        if g.get("rush_att") != 243:
            fail("Gibbs rush_att %s != 243" % g.get("rush_att"))
        if g.get("ypc") != 5.0:
            fail("Gibbs ypc %s != 5.0" % g.get("ypc"))
    if str(BIJAN) not in players:
        fail("compare_adv missing Bijan")
    else:
        b = players[str(BIJAN)]
        if b.get("rush_att") != 287:
            fail("Bijan rush_att %s != 287" % b.get("rush_att"))
        if b.get("ypc") != 5.1:
            fail("Bijan ypc %s != 5.1" % b.get("ypc"))
    if adv.get("season") != 2025:
        fail("compare_adv season %s != 2025" % adv.get("season"))
    blob = adv_path.read_text()
    if "Tittsburgh" in blob:
        fail("Tittsburgh in compare_adv.json")
    if "PPR" in blob and "non-PPR" not in blob and "non PPR" not in blob:
        fail("PPR in compare_adv.json")

    src = ROOT / "data" / "compare-2025"
    for name in ("wr-receiving.csv", "rb-rushing.csv", "qb-passing.csv", "te-receiving.csv", "snap-util.csv", "quality-games.csv"):
        if not (src / name).exists():
            fail("missing " + name)

    try:
        req = urllib.request.Request("http://127.0.0.1:8765/players.html", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            if r.status != 200:
                fail("players.html HTTP %s" % r.status)
            body = r.read().decode("utf-8", "replace")
            if 'id="pl-compare"' not in body:
                fail("served players.html missing compare card")
    except Exception as e:
        fail("players.html not reachable on 8765: %s" % e)

    _done()
    return 1 if fails else 0


def _done():
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
    else:
        print("PASS")


if __name__ == "__main__":
    sys.exit(main())
