#!/usr/bin/env python3
"""NGS 2025 profiles: JSON + UI, not new sqlite tables."""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(m):
    fails.append(m)


def main():
    jpath = SITE / "ngs_profiles.json"
    if not jpath.exists():
        fail("site/ngs_profiles.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    data = json.loads(jpath.read_text())
    if data.get("join_key") != "gsis_id":
        fail("join_key is not gsis_id")
    players = data.get("players") or {}
    franchises = data.get("franchises") or []
    if len(players) < 800:
        fail("too few joined players: %s" % len(players))
    if len(franchises) != 12:
        fail("expected 12 franchises, got %s" % len(franchises))

    feel = next((f for f in franchises if f.get("owner") == "m18"), None)
    if not feel:
        fail("Feelers m18 missing from franchises")
    else:
        if feel.get("tid") != 7:
            fail("Feelers tid %s != 7" % feel.get("tid"))
        if "Feelers" not in str(feel.get("name") or ""):
            fail("Feelers name drifted: %s" % feel.get("name"))
        if not feel.get("routes"):
            fail("Feelers routes empty")
        if not feel.get("holes"):
            fail("Feelers holes empty")
        if not (feel.get("topRoute") or {}).get("route"):
            fail("Feelers topRoute missing")
        if not (feel.get("topHole") or {}).get("hole"):
            fail("Feelers topHole missing")

    blob = jpath.read_text()
    if "Tittsburgh" in blob:
        fail("Tittsburgh in ngs_profiles.json")

    pjs = (SITE / "players.js").read_text()
    phtml = (SITE / "players.html").read_text()
    hjs = (SITE / "history.js").read_text()
    hhtml = (SITE / "history.html").read_text()
    tjs = (SITE / "teams.js").read_text()
    thtml = (SITE / "teams.html").read_text()
    script = (ROOT / "scripts" / "load_ngs_profiles.py").read_text()

    if "top_routes_json" not in pjs:
        fail("players.js missing top_routes_json")
    if "top_holes_json" not in pjs:
        fail("players.js missing top_holes_json")
    if "function renderNgsProfile" not in pjs:
        fail("players.js missing renderNgsProfile")
    if 'id="pl-ngs-profile"' not in phtml:
        fail("players.html missing pl-ngs-profile")
    if "ngs_profiles.json" not in pjs:
        fail("players.js does not fetch ngs_profiles.json")

    if 'id="ngs-block"' not in hhtml:
        fail("history.html missing ngs-block")
    if 'id="ngs-tbl"' not in hhtml:
        fail("history.html missing ngs-tbl")
    if "function renderNgs" not in hjs:
        fail("history.js missing renderNgs")
    if "A.franchiseName" not in hjs:
        fail("history.js does not use franchiseName")
    if "ngs_profiles.json" not in hjs:
        fail("history.js does not fetch ngs_profiles.json")

    if 'id="ngs-block"' not in thtml:
        fail("teams.html missing ngs-block")
    if '"ngs-block"' not in tjs:
        fail("teams.js does not wire ngs-block")
    if "function renderNgs" not in tjs:
        fail("teams.js missing renderNgs")
    if "ngs_profiles.json" not in tjs:
        fail("teams.js does not fetch ngs_profiles.json")

    for name, body in (
        ("history.js", hjs),
        ("teams.js", tjs),
        ("players.js", pjs),
        ("history.html", hhtml),
        ("teams.html", thtml),
        ("players.html", phtml),
    ):
        if "Tittsburgh" in body:
            fail("Tittsburgh in %s" % name)

    if "mode=ro" not in script:
        fail("load_ngs_profiles.py is not read-only")
    if "UPDATE fact_roster_week" in script or "UPDATE fact_matchup" in script or "UPDATE fact_draft_pick" in script:
        fail("load script updates protected facts")

    con = sqlite3.connect("file:%s?mode=ro" % (ROOT / "affl.db"), uri=True)
    n = con.execute("SELECT COUNT(*) FROM fact_draft_pick").fetchone()[0]
    con.close()
    if n != 2124:
        fail("fact_draft_pick drifted: %s != 2124" % n)

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    tr = feel["topRoute"]["route"]
    th = feel["topHole"]["hole"]
    print("players %s franchises %s feelers %s/%s" % (len(players), len(franchises), tr, th))
    return 0


if __name__ == "__main__":
    sys.exit(main())
