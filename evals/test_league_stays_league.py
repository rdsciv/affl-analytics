#!/usr/bin/env python3
"""League pages stay league-wide.

Picking a squad on draft/trades/roto/players/scoreboard jumps to Teams.
League charts and tables must never collapse to one franchise — even if
?squad= is still in the URL (old bookmark). Teams page is the filter home.
"""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
FEELERS = "m18"
YEAR = 2025
FEELERS_TID = 7
fails = []


def fail(msg):
    fails.append(msg)


def src(name):
    return (SITE / name).read_text()


def load_year():
    return json.loads((SITE / "years/2025.json").read_text())


def test_draft_js():
    js = src("draft.js")
    if "applySquadDraft" in js:
        fail("draft.js still contains applySquadDraft — league draft must stay full-board")
    if "goTeam" not in js:
        fail("draft.js missing goTeam (squad pick must jump to Teams)")


def test_trades_js():
    js = src("trades.js")
    if "applySquadTx" in js:
        fail("trades.js still contains applySquadTx — league trades must stay full-league")
    if "goTeam" not in js:
        fail("trades.js missing goTeam (squad pick must jump to Teams)")


def test_roto_js():
    js = src("roto.js")
    assign = re.search(r"displayTeams\s*=\s*([^;]+)", js)
    if assign and "squad &&" in assign.group(1):
        fail("roto.js assigns displayTeams from a squad filter — table would collapse to one row")
    if "goTeam" not in js:
        fail("roto.js missing goTeam (squad pick must jump to Teams)")


def test_scoreboard_js():
    js = src("scoreboard.js")
    if re.search(r"if\s*\(\s*squad\s*\)\s*\{[^}]*home\.tid", js, re.S):
        fail("scoreboard.js still filters games with if (squad) + home.tid")
    if "goTeam" not in js:
        fail("scoreboard.js missing goTeam (squad pick must jump to Teams)")


def test_players_js():
    js = src("players.js")
    fn = re.search(r"function filtered\(\)\s*\{(.*?)\n  \}", js, re.S)
    body = fn.group(1) if fn else ""
    if not fn:
        fail("players.js missing filtered()")
    else:
        if re.search(r"if\s*\(\s*!squad\s*\)", body) or re.search(r"if\s*\(\s*squad\s*\)", body):
            fail("players.js filtered() still early-returns / branches on squad")
        if "teamIdFor" in body:
            fail("players.js filtered() still slices the roster by squad")
    if "goTeam" not in js:
        fail("players.js missing goTeam (squad pick must jump to Teams)")


def test_common_exports_goteam():
    js = src("common.js")
    if "function goTeam" not in js:
        fail("common.js missing function goTeam")
    exported = js.split("return {", 1)[-1] if "return {" in js else ""
    if "goTeam" not in exported:
        fail("common.js does not export goTeam on the AFFL return object")


def test_payload_sanity():
    y = load_year()
    board = (y.get("draft") or {}).get("board") or []
    tids = {p.get("tid") for p in board}
    feelers = [p for p in board if p.get("tid") == FEELERS_TID]
    print(f"2025 draft unique teams: {len(tids)}")
    print(f"2025 Feelers (tid {FEELERS_TID}) picks: {len(feelers)} / {len(board)}")
    if len(tids) != 12:
        fail(f"2025 draft board should have 12 distinct tids, got {len(tids)}")
    if not (0 < len(feelers) < len(board)):
        fail(f"Feelers should be a minority of 2025 picks, got {len(feelers)} / {len(board)}")


def main():
    test_draft_js()
    test_trades_js()
    test_roto_js()
    test_scoreboard_js()
    test_players_js()
    test_common_exports_goteam()
    test_payload_sanity()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("League pages stay league-wide; squad pick jumps to Teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
