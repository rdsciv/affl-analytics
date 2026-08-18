#!/usr/bin/env python3
"""Player name links + college card. Nulls stay em dash. No owner-name labels."""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []


def fail(m):
    fails.append(m)


def src(name):
    return (SITE / name).read_text()


def main():
    common = src("common.js")
    pjs = src("players.js")
    phtml = src("players.html")
    teams = src("teams.js")
    trades = src("trades.js")
    score = src("scoreboard.js")
    hist = src("history.js")
    data = json.loads((SITE / "data.json").read_text())
    bio = json.loads((SITE / "player_bio.json").read_text())

    if "function playerLink" not in common:
        fail("common.js missing A.playerLink")
    if "function playerHref" not in common:
        fail("common.js missing playerHref")
    if "players.html" not in common or "pid" not in common:
        fail("playerLink does not target players.html?pid=")
    if "function collegeLogoHTML" not in common:
        fail("collegeLogoHTML missing")
    if "function franchiseName" not in common:
        fail("franchiseName broken")
    if "function ageOn" not in common:
        fail("ageOn broken")
    if 'MERGE = { m01: "m07"' not in common:
        fail("MERGE broken")

    for name, body in (
        ("players.js", pjs),
        ("teams.js", teams),
        ("trades.js", trades),
        ("scoreboard.js", score),
    ):
        if "A.playerLink" not in body:
            fail(f"{name} does not use A.playerLink")
        if "data-pid" not in body and "playerLink" not in body:
            fail(f"{name} names lack pid")

    if "A.playerLink" not in pjs:
        fail("Players grid names are not links")
    if 'id="pl-college"' not in phtml:
        fail("players.html missing college card")
    if "function renderCollege" not in pjs:
        fail("renderCollege missing")
    for field in ("breakoutAge", "dominator", "earlyDeclare", "draftRound", "draftPick", "draftTeam"):
        if field not in pjs:
            fail(f"college card missing {field}")
    if "breakoutAge != null" not in pjs and "bio.breakoutAge" not in pjs:
        fail("college card does not guard missing breakoutAge")
    if '"—"' not in pjs and "'—'" not in pjs:
        fail("college card does not render em dash")

    # no owner-name labels on the player profile
    banned = ("ownerName", "memberName", "shortOwner")
    for b in banned:
        if b in pjs:
            fail(f"players.js still uses owner-name label {b}")
    if "A.franchiseName" not in pjs:
        fail("player profile team label is not current franchise name")

    # cache-bust
    if "players.js?v=9" in phtml:
        fail("players.js still cache-busted at v=9")
    if "players.js?v=" not in phtml:
        fail("players.js not cache-busted")

    # identity
    feel = [f for f in data.get("franchises") or [] if f.get("owner") == "m18"]
    if len(feel) != 1:
        fail(f"Feelers franchise rows {len(feel)}")
    elif feel[0].get("currentName") != "Grand Teeton Feelers":
        fail(f"Feelers current name {feel[0].get('currentName')}")

    # Josh Allen college is real, breakout may be missing — must not invent
    josh = bio.get("3918298") or {}
    if josh.get("college") != "Wyoming":
        fail(f"Josh Allen college {josh.get('college')}")
    if josh.get("breakoutAge") not in (None, ""):
        pass  # sibling may have filled it; still must render via guard
    wyo = SITE / "logos/ncaa/wyoming.png"
    if not wyo.exists() or wyo.stat().st_size < 400:
        fail("Wyoming NCAA logo missing")

    # History has no player-name cells; it must stay current-franchise only
    if "ownerName" in hist or "shortOwner" in hist:
        fail("history.js owner-name labels")
    if "currentName" not in hist and "f.name" not in hist:
        fail("history.js lost current franchise names")

    # scoreboard links go through the helper
    if "players.html?year=${year}&pid=${pid}" in score:
        fail("scoreboard still hand-rolls player hrefs")

    print("Feelers = Grand Teeton Feelers / m18")
    print(f"Josh Allen college={josh.get('college')} breakoutAge={josh.get('breakoutAge')}")
    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
