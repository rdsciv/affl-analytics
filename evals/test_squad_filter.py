#!/usr/bin/env python3
"""Squad identity + payload slices.

League pages stay league-wide; Teams page is the filter home.
These tests prove the Teams page CAN slice Feelers 2025 (identity +
payload subsets). They do not require league JS to hard-filter.
"""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
FEELERS = "m18"
YEAR = 2025
fails = []


def fail(msg):
    fails.append(msg)


def load():
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years/2025.json").read_text())
    return data, y2025


def team_id(data, year, owner):
    teams = data["seasons"][str(year)]["teams"]
    t = next((x for x in teams if x["owner"] == owner), None)
    return t["id"] if t else None


def same(a, b):
    return a is not None and b is not None and int(a) == int(b)


def test_identity(data):
    tid = team_id(data, YEAR, FEELERS)
    if tid != 7:
        fail(f"Feelers 2025 team id should be 7, got {tid}")
    name = next(t["name"] for t in data["seasons"]["2025"]["teams"] if t["owner"] == FEELERS)
    if "Feelers" not in name:
        fail(f"Feelers 2025 name is {name}")
    years = next(f["years"] for f in data["franchises"] if f["owner"] == FEELERS)
    if YEAR not in years:
        fail("Feelers franchise years missing 2025")


def test_payload_filters(data, y):
    tid = team_id(data, YEAR, FEELERS)
    picks = [p for p in y["draft"]["board"] if same(p["tid"], tid)]
    if not (0 < len(picks) < len(y["draft"]["board"])):
        fail(f"draft Feelers picks {len(picks)} / {len(y['draft']['board'])}")
    trades = [tr for tr in y["trades"] if any(same(s["tid"], tid) for s in tr["sides"])]
    if not (0 < len(trades) < len(y["trades"])):
        fail(f"trades Feelers {len(trades)} / {len(y['trades'])}")
    players = [p for p in y["players"] if same(p["mainTeam"], tid) or any(same(w[3], tid) for w in p.get("wk") or [])]
    if not (0 < len(players) < len(y["players"])):
        fail(f"players Feelers {len(players)} / {len(y['players'])}")
    games = []
    for wk, gs in y["weeks"].items():
        games.extend(gs)
    mine = [g for g in games if same(g["home"]["tid"], tid) or same(g["away"]["tid"], tid)]
    if not (0 < len(mine) < len(games)):
        fail(f"scoreboard Feelers games {len(mine)} / {len(games)}")
    # one game per week in a 12-team league
    if len(mine) != 17 and len(mine) < 14:
        fail(f"Feelers should have ~season of games, got {len(mine)}")


def main():
    data, y2025 = load()
    test_identity(data)
    test_payload_filters(data, y2025)
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("Feelers m18 -> 2025 team 7")
    print("Payload slices are proper subsets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
