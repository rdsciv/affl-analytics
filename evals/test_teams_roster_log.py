#!/usr/bin/env python3
"""Teams roster: names only; click opens totals + averages, not every week."""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
FEELERS = "m18"
YEAR = 2025
fails = []


def fail(msg):
    fails.append(msg)


def src(name):
    return (SITE / name).read_text()


def test_roster():
    js = src("teams.js")
    if "function renderRoster" not in js:
        fail("renderRoster missing")
    if "headshotHTML" in js:
        fail("teams.js still calls headshotHTML")
    if "tm-name" not in js or "data-pid" not in js:
        fail("names are not clickable")
    if "function statCard" not in js:
        fail("statCard missing")
    if "Totals" not in js or "Averages" not in js:
        fail("card missing Totals/Averages")
    if "<th>Wk</th>" in js:
        fail("still dumps a weekly game log")
    if "logs:" not in js and "logs =" not in js:
        fail("mergePlayers dropped weekly rows needed for averages")


def test_payload():
    data = json.loads((SITE / "data.json").read_text())
    y = json.loads((SITE / "years/2025.json").read_text())
    t = next(x for x in data["seasons"][str(YEAR)]["teams"] if x["owner"] == FEELERS)
    tid = t["id"]
    mine = [
        p for p in y["players"]
        if p.get("mainTeam") == tid or any(w[3] == tid for w in (p.get("wk") or []))
    ]
    with_log = [p for p in mine if p.get("wk")]
    print(f"Feelers 2025 players with weeks (for averages): {len(with_log)} / {len(mine)}")
    if not (0 < len(with_log) < len(y["players"])):
        fail("Feelers week coverage is empty or the whole league")


def main():
    test_roster()
    test_payload()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
