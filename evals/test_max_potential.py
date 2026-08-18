#!/usr/bin/env python3
"""CHI-48 / AFFL-027: Maximum Potential formatted like FantasyGenius.

Static + data checks. Does not require a browser. Hits :8765 if up.
"""
import json
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
    html = (SITE / "index.html").read_text()
    js = (SITE / "app.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years" / "2025.json").read_text())

    for needle in (
        'id="max-potential"',
        'id="maxpot-award"',
        'id="maxpot-bars"',
        "Maximum Potential",
        "Highest ideal lineup points scored",
        "Actual points scored",
        "Points left on table",
    ):
        if needle not in html:
            fail(f"index.html missing {needle!r}")

    award_at = html.find('id="maxpot-award"')
    bars_at = html.find('id="maxpot-bars"')
    if award_at < 0 or bars_at < 0 or award_at > bars_at:
        fail("award card is not above the stacked bars")

    season_at = html.find('id="season-pane"')
    cum_at = html.find('id="cum-pane"')
    max_at = html.find('id="max-potential"')
    if not (0 <= season_at < max_at < cum_at):
        fail("#max-potential is not inside #season-pane (hidden/missing pane)")

    if "function renderMaxPotential" not in js:
        fail("app.js missing renderMaxPotential")
    fn = js.split("function renderMaxPotential", 1)[-1].split("function ", 1)[0]
    for needle in ("NG.lineupIQ", "optimal", "actual", "wasted", "Gifted Kid Maximum Potential Award"):
        if needle not in fn:
            fail(f"renderMaxPotential missing {needle!r}")
    if "b.opt - a.opt" not in fn and "b.opt-a.opt" not in fn:
        fail("renderMaxPotential does not sort by optimal desc")
    if "maxpot-act" not in fn or "maxpot-left" not in fn:
        fail("renderMaxPotential missing stacked actual/leftover bars")
    if "if (document.getElementById('max-potential')) renderMaxPotential()" not in js:
        fail("renderSeason does not call renderMaxPotential")

    if ".maxpot-act" not in css or ".maxpot-left" not in css:
        fail("styles.css missing stacked bar colors")

    teams = {t["id"]: t for t in (data.get("seasons") or {}).get("2025", {}).get("teams") or []}
    iq = y2025.get("lineupIQ") or []
    if len(iq) != 12:
        fail(f"2025 lineupIQ {len(iq)} != 12")
    ranked = sorted(iq, key=lambda r: (-(r.get("optimal") or 0), -(r.get("actual") or 0)))
    if not ranked:
        fail("2025 lineupIQ empty")
    else:
        top = ranked[0]
        tid = top.get("teamId")
        name = (teams.get(tid) or {}).get("name")
        opt = float(top.get("optimal") or 0)
        act = float(top.get("actual") or 0)
        pct = round(100 * act / opt) if opt else 0
        print(f"2025 Gifted Kid: {name} tid={tid} opt={opt} act={act} {pct}% of ideal")
        if name != "San Diego Shadowcöcks":
            fail(f"top optimal team is {name!r}, expected San Diego Shadowcöcks")
        if abs(opt - 1682.5) > 0.05:
            fail(f"Shadowcöcks optimal {opt} != 1682.5")
        if pct != 92:
            fail(f"Shadowcöcks % of ideal {pct} != 92")
        if ranked[0] is not max(iq, key=lambda r: r.get("optimal") or 0):
            fail("first bar is not highest optimal")

    franchises = {f.get("owner"): f.get("currentName") for f in data.get("franchises") or []}
    for t in teams.values():
        cur = franchises.get(t.get("owner"))
        if cur and t.get("name") != cur:
            fail(f"2025 season name {t.get('name')!r} != current franchise {cur!r}")

    if "T25[r.teamId]" not in fn and "currentFranchise" not in fn:
        fail("renderMaxPotential does not resolve franchise/season names")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/index.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        body = r.read().decode()
        if code != 200:
            fail(f"index.html HTTP {code}")
        else:
            print("index.html HTTP 200")
        for needle in ('id="max-potential"', 'id="maxpot-award"', 'id="maxpot-bars"'):
            if needle not in body:
                fail(f"served index.html missing {needle}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"index.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-48: Gifted Kid + stacked actual/leftover bars live on dashboard season pane")
    return 0


if __name__ == "__main__":
    sys.exit(main())
