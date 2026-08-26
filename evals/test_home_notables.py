#!/usr/bin/env python3
"""Home page ships real hero stats and the six warehouse notables.

Reads site/index.html, site/app.js, and site/years/2025.json (no rebuild).
Proves:

  1. Hero fallbacks are real numbers (15,723 / 84), never em-dashes.
  2. 2025 year JSON has all six notable kinds with both scores.
  3. Home JS renders NG.notables (all six), not the old process.py
     bestWeek / worstWeek / closest / blowout story path.
  4. Home luck chart reads warehouse Luck Index (luckFG), not t.luck.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
KINDS = ("min_win", "max_loss", "slugfest", "pillow_fight", "blowout", "nail_biter")
DASHES = ("—", "–", "&mdash;", "&ndash;", "&#8212;", "&#8211;")
fails = []


def fail(msg):
    fails.append(msg)


def main():
    html = (SITE / "index.html").read_text()
    js = (SITE / "app.js").read_text()
    year_path = SITE / "years" / "2025.json"
    if not year_path.exists():
        fail(f"missing {year_path}")
        done()
        return 1
    bundle = json.loads(year_path.read_text())

    hs_total = re.search(r'id="hs-total">([^<]*)</', html)
    hs_games = re.search(r'id="hs-games">([^<]*)</', html)
    if not hs_total or not hs_games:
        fail("hero stat nodes missing from index.html")
    else:
        total, games = hs_total.group(1).strip(), hs_games.group(1).strip()
        if total != "15,723":
            fail(f"hs-total fallback {total!r} != '15,723'")
        if games != "84":
            fail(f"hs-games fallback {games!r} != '84'")
        for node, val in (("hs-total", total), ("hs-games", games)):
            if any(d in val for d in DASHES) or val in ("-", "--"):
                fail(f"{node} still an em-dash / blank: {val!r}")
        print(f"hero fallbacks: {total} points / {games} games")

    hero_block = re.search(
        r'<div class="hero-stats">(.*?)</div>\s*<div class="season-block">',
        html, re.S)
    if hero_block:
        for d in DASHES:
            if d in hero_block.group(1):
                fail(f"hero-stats still contains {d!r}")

    champ = re.search(
        r'id="champ-spot">(.*?)</div>\s*<ul class="story-list"',
        html, re.S)
    if not champ:
        fail("champ-spot missing")
    else:
        body = champ.group(1)
        if "San Diego Shadowc" not in body:
            fail("champ fallback missing San Diego Shadowcocks")
        if "John Newton" not in body or "11-3" not in body:
            fail("champ fallback missing John Newton 11-3")
        if "1,543.02" not in body:
            fail("champ fallback missing 1,543.02 PF")

    notables = bundle.get("notables")
    if not isinstance(notables, list):
        fail("2025.json notables missing or not a list")
        notables = []
    have = {n.get("kind") for n in notables}
    if have != set(KINDS):
        fail(f"notable kinds {have} != {set(KINDS)}")
    for n in notables:
        kind = n.get("kind")
        if n.get("winnerPts") is None or n.get("loserPts") is None:
            fail(f"{kind} missing a side score")
        if n.get("winnerId") is None or n.get("loserId") is None:
            fail(f"{kind} missing a team id")
        if n.get("week") is None:
            fail(f"{kind} missing week")
    print(f"2025.json notables: {len(notables)} rows, kinds={sorted(have)}")

    side = js.split("function renderSide", 1)
    if len(side) < 2:
        fail("renderSide missing")
        side_body = ""
    else:
        side_body = side[1].split("function ", 1)[0]
    if "NG.notables" not in side_body and "notables" not in side_body:
        fail("renderSide does not read notables")
    for old in ("bestWeek", "worstWeek", "closest", "blowout"):
        if re.search(r"\b" + old + r"\b", side_body):
            fail(f"renderSide still uses old superlative {old}")
    if "NOTABLE_ORDER" not in js:
        fail("NOTABLE_ORDER missing")
    else:
        order = re.search(r"NOTABLE_ORDER = \[(.*?)\]", js, re.S)
        if not order:
            fail("NOTABLE_ORDER not a list")
        else:
            kinds_js = re.findall(r"'([a-z_]+)'", order.group(1))
            if kinds_js != list(KINDS):
                fail(f"NOTABLE_ORDER {kinds_js} != {list(KINDS)}")

    luck = js.split("function renderLuck", 1)
    luck_body = luck[1].split("function ", 1)[0] if len(luck) > 1 else ""
    if "luckFG" not in js:
        fail("app.js never reads luckFG")
    maps = js.split("function warehouseMaps", 1)
    maps_body = maps[1].split("function ", 1)[0] if len(maps) > 1 else ""
    if "luckFG" not in maps_body:
        fail("warehouseMaps does not read luckFG")
    if "r.net" not in luck_body:
        fail("renderLuck does not plot Luck Index net")
    if "weighted" not in luck_body:
        fail("renderLuck dropped weighted luck secondary")

    stand = js.split("function renderStandings", 1)
    stand_body = stand[1].split("function ", 1)[0] if len(stand) > 1 else ""
    if "warehouseMaps" not in stand_body or "power" not in stand_body:
        fail("renderStandings does not overlay warehouse Power")

    print("home JS: notables + luckFG + warehouse Power")
    done()
    return 1 if fails else 0


def done():
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
    else:
        print("PASS")
        print("home hero fallbacks present; six notables in JSON; JS reads notables not the old 4")


if __name__ == "__main__":
    sys.exit(main())
