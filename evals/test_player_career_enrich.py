#!/usr/bin/env python3
"""Full NFL career log + NGS overlay on player pages.

If a player ever appeared on an AFFL roster they get every nflverse REG
week, not just AFFL-rostered weeks. Jalen Nailor 2025 is the gate:
week-16 FA add / benched, but the profile must show his Vikings season.
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
fail = lambda m: fails.append(m)

NAILOR = "4382466"


def main():
    nfl_path = SITE / "nfl_weeks.json"
    ngs_path = SITE / "ngs.json"
    if not nfl_path.exists():
        fail("site/nfl_weeks.json missing")
    if not ngs_path.exists():
        fail("site/ngs.json missing")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    nfl = json.loads(nfl_path.read_text())
    ngs = json.loads(ngs_path.read_text())
    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()

    rec = (nfl.get(NAILOR) or {}).get("2025") or {}
    weeks = [k for k in rec if k.isdigit() and int(k) > 0]
    pts = sum((rec[k].get("pts") or 0) for k in weeks)
    print(f"Nailor 2025 overlay weeks={len(weeks)} pts={pts:.1f}")
    if len(weeks) < 14:
        fail(f"Nailor 2025 log/overlay has {len(weeks)} NFL weeks (need >= 14, not 1)")
    if abs(pts - 71.7) > 2:
        fail(f"Nailor 2025 season pts {pts} not ≈ 71.7 (tol 2)")

    ngs25 = (ngs.get(NAILOR) or {}).get("2025") or {}
    ngs_w = [k for k in ngs25 if k.isdigit() and int(k) > 0]
    print(f"Nailor 2025 NGS weekly rows={len(ngs_w)} week0={'0' in ngs25}")
    if not ngs_w and "0" not in ngs25:
        # honest empty is allowed (NGS minimums) — Nailor should have some
        print("Nailor 2025 NGS empty (allowed if below attempt minimums)")
    elif ngs_w:
        sample = ngs25[ngs_w[0]]
        if sample.get("sep") is None and sample.get("kind") != "receiving":
            fail("Nailor 2025 NGS week is not a receiving row")

    if "rowState" not in js and "three-state" not in js:
        fail("players.js missing three-state styling")
    if "nfl-only" not in js:
        fail("players.js missing nfl-only (third) style")
    if "#2a9d8c" not in js and "muted teal" not in js:
        fail("players.js missing teal NFL-not-rostered style")
    if "nfl_weeks.json" not in js:
        fail("players.js does not fetch nfl_weeks.json")
    if "ngs.json" not in js:
        fail("players.js does not fetch ngs.json")
    if "gatherLogs" not in js:
        fail("players.js missing gatherLogs")
    if "weekProj" not in js:
        fail("players.js lost weekProj (ESPN proj overlay)")
    if "label: \"ESPN proj\"" not in js and "label: 'ESPN proj'" not in js:
        fail("players.js lost ESPN proj dataset")
    if "affl started pts" not in js:
        fail("players.js missing AFFL-started pts secondary tile")
    if "players.js?v=" not in html:
        fail("players.html did not cache-bust players.js")
    if "ESPN weekly projection" not in html:
        fail("players.html lost ESPN weekly projection subtitle")
    if "not on an AFFL roster" not in html and "not on an AFFL roster" not in js:
        fail("three-state copy missing from players page")
    if "pl-ngs-chart" not in html:
        fail("players.html missing NGS strip canvas")

    # HTTP 200
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
