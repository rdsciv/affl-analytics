#!/usr/bin/env python3
"""CHI-62 / AFFL-040: Scoreboard squad filter (All + 12 current names).

Picking a current franchise hides other matchup cards and gates the
CHI-42 injury list on that tid/franchise. All shows everyone.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
FEELERS = "m18"
YEAR = 2025
BANNED = ("NFL not rostered", "not rostered", "not on an AFFL roster")


def canon(i):
    return MERGE.get(str(i), str(i))


def main():
    html = (SITE / "scoreboard.html").read_text()
    js = (SITE / "scoreboard.js").read_text()
    common = (SITE / "common.js").read_text()
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years" / "2025.json").read_text())

    # --- filter control exists ---
    if 'id="squad-picker"' not in html:
        fail("scoreboard.html missing #squad-picker")
    if "sb-squad" not in html:
        fail("scoreboard.html missing .sb-squad")
    if "Squad" not in html:
        fail("scoreboard.html missing Squad label")
    if "function drawSquadFilter" not in js and "function currentSquads" not in js:
        fail("scoreboard.js missing squad filter draw")
    if "function filterGames" not in js:
        fail("scoreboard.js missing filterGames")
    if "function squadTidFor" not in js:
        fail("scoreboard.js missing squadTidFor")
    print("filter control: chips on #squad-picker.sb-squad")

    # --- chrome kept ---
    for needle in ("nfl-injury-card", "week-picker", "scope-picker", "year-picker"):
        if needle not in html:
            fail("scoreboard.html lost chrome %s" % needle)
    if "function renderNflInjuries" not in js:
        fail("renderNflInjuries missing (CHI-42)")

    # --- cache pin bumped ---
    bust = re.search(r"scoreboard\.js\?v=(\d+)", html)
    if not bust:
        fail("scoreboard.html did not cache-bust scoreboard.js")
    elif int(bust.group(1)) < 5:
        fail("scoreboard.js cache still v=%s" % bust.group(1))
    else:
        print("cache pin scoreboard.js?v=%s" % bust.group(1))

    # --- 12 current names, no old owner-as-identity ---
    if "m01" not in common or "m07" not in common or "MERGE" not in common:
        fail("common.js missing MERGE m01→m07")
    if "A.canon" not in js:
        fail("scoreboard.js does not use A.canon for merge")
    if "franchiseName" not in js:
        fail("scoreboard.js does not use franchiseName")
    if "memberName" in js:
        fail("scoreboard.js still shows owner first names via memberName")
    if "ownerName" in js:
        fail("scoreboard.js uses ownerName as identity")
    if "A.goTeam" in js:
        fail("scoreboard squad pick still navigates away via goTeam")
    if "f.active" not in js and ".active" not in js:
        fail("scoreboard.js does not gate chips to active/current franchises")

    active = [f for f in (data.get("franchises") or []) if f.get("active")]
    if len(active) != 12:
        fail("expected 12 current franchises, got %s" % len(active))
    current_names = {f.get("currentName") for f in active}
    owner_names = set((data.get("members") or {}).values())
    former = [f for f in (data.get("franchises") or []) if not f.get("active")]
    former_names = {f.get("currentName") for f in former}
    print("current", sorted(current_names))
    if "Grand Teeton Feelers" not in current_names:
        fail("Feelers missing from current 12")
    overlap = current_names & owner_names
    if overlap:
        fail("currentName is an owner name: %s" % overlap)
    # filter must not treat former franchise names as the 12-chip set
    if "Muck City Mad Dawgs" in current_names or "Pawtucket Patriots" in current_names:
        fail("former franchise slipped into current 12")
    if "Jason Kafka" in js or "Scott Ace" in js or "Garrett Jones" in js:
        fail("old owner-as-identity hardcoded in scoreboard.js")

    # chips use current franchise identity (franchiseName / currentName / shortTeam)
    if "A.franchiseName" not in js and "currentName" not in js:
        fail("chip labels are not current franchise names")
    if "All" not in js:
        fail("filter missing All chip")

    # --- Feelers hides other matchup cards ---
    teams = (data.get("seasons") or {}).get(str(YEAR), {}).get("teams") or []
    feelers_tid = next((t["id"] for t in teams if t.get("owner") == FEELERS), None)
    if feelers_tid != 7:
        fail("Feelers 2025 tid should be 7, got %s" % feelers_tid)
    week1 = (y2025.get("weeks") or {}).get("1") or []
    mine = [g for g in week1
            if g.get("home", {}).get("tid") == feelers_tid
            or g.get("away", {}).get("tid") == feelers_tid]
    if not week1:
        fail("2025 week 1 has no games")
    elif not (0 < len(mine) < len(week1)):
        fail("Feelers week 1 slice %s / %s is not a proper subset" % (len(mine), len(week1)))
    else:
        print("Feelers week 1: %s of %s cards remain" % (len(mine), len(week1)))
    if "filterGames" not in js or "gameHasSquad" not in js:
        fail("matchup cards are not filtered by selected squad tid")
    if "data-home" not in js or "data-away" not in js:
        fail("matchup cards missing home/away tid markers")

    # --- injury filter gated on selected tid/franchise ---
    inj_fn = js
    if "function renderNflInjuries" in js:
        inj_fn = js.split("function renderNflInjuries", 1)[1].split("function injRowHTML", 1)[0]
    if "if (squad)" not in inj_fn and "if(squad)" not in inj_fn:
        fail("injury filter is not gated on selected squad")
    if "squadTidFor" not in inj_fn and "r.tid" not in inj_fn:
        fail("injury filter is not gated on selected tid")
    if "A.canon" not in inj_fn and "franchise" not in inj_fn:
        fail("injury filter is not gated on selected franchise")
    print("injury filter gated on squad tid/franchise")

    # --- 2014–17 never say NFL not rostered ---
    for phrase in BANNED:
        if phrase in js or phrase in html:
            fail("scoreboard uses banned phrase %r" % phrase)

    # --- HTTP 200 ---
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/scoreboard.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail("scoreboard.html HTTP %s" % code)
        else:
            print("scoreboard.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail("not reachable on 8765: %s" % e)

    # --- CHI-42 eval still PASS ---
    inj_eval = ROOT / "evals" / "test_injuries.py"
    if inj_eval.exists():
        proc = subprocess.run([sys.executable, str(inj_eval)], cwd=str(ROOT),
                              capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 or "FAIL" in out.splitlines()[-5:]:
            fail("test_injuries.py no longer PASS")
            for line in out.splitlines()[-12:]:
                print("  inj:", line)
        else:
            print("test_injuries.py PASS")
    else:
        fail("evals/test_injuries.py missing")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
