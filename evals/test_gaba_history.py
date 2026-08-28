#!/usr/bin/env python3
"""Gabagooners career-book lock.

History All-Play / franchise records / H2H must not include Gabagooners or a
0-0-0 row for m22. Career book is 2014-2025; they have not played.

Teams landing All MAY keep them as a current 2026 card with 0 seasons.
Team picker stays 20/11/13 (All keeps them, 2014/2025 drop them).
Do not invent an AFFL 2026 season.
Feelers career All-Play stays 954-727.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def career_allplay(data: dict, owner: str) -> tuple[int, int]:
    w = l = 0
    for ys, season in (data.get("seasons") or {}).items():
        year = int(ys)
        if year < 2014 or year > 2025:
            continue
        for t in season.get("teams") or []:
            if t.get("owner") == owner:
                w += int(t.get("allplayW") or 0)
                l += int(t.get("allplayL") or 0)
    return w, l


def owners_in_seasons(data: dict) -> set[str]:
    out: set[str] = set()
    for ys, season in (data.get("seasons") or {}).items():
        year = int(ys)
        if year < 2014 or year > 2025:
            continue
        for t in season.get("teams") or []:
            oid = t.get("owner")
            if oid:
                out.add(str(oid))
    return out


def franchise_years(data: dict, owner: str) -> list[int]:
    out = []
    for ys, season in (data.get("seasons") or {}).items():
        for t in season.get("teams") or []:
            if t.get("owner") == owner:
                out.append(int(ys))
    return sorted(set(out))


def in_career_book(data: dict, owner: str) -> bool:
    if owner == "m22":
        return False
    return any(2014 <= y <= 2025 for y in franchise_years(data, owner))


def test_data_book(data: dict) -> None:
    seasons = sorted(int(y) for y in (data.get("seasons") or {}))
    if 2026 in seasons:
        fail("data.json invented an AFFL 2026 season")
    if seasons != list(range(2014, 2026)):
        fail(f"data.json seasons {seasons} — want 2014-2025 only")

    played = owners_in_seasons(data)
    if "m22" in played:
        fail("data.json still places Gabagooners on a 2014-2025 season")

    feel_w, feel_l = career_allplay(data, "m18")
    if (feel_w, feel_l) != (954, 727):
        fail(f"Feelers career All-Play {feel_w}-{feel_l} — expected 954-727")

    m22 = next((f for f in (data.get("franchises") or []) if f.get("owner") == "m22"), None)
    if not m22:
        fail("Gabagooners franchise row missing from data.json")
    elif (m22.get("years") or []) or (m22.get("seasons") or 0):
        fail(f"Gabagooners years/seasons are not empty: {m22.get('years')} / {m22.get('seasons')}")

    names = {f.get("owner"): f.get("currentName") or "" for f in (data.get("franchises") or [])}
    for oid in played:
        if "Gabagooners" in names.get(oid, ""):
            fail(f"All-Play career owners include Gabagooners ({oid})")
        if oid == "m22":
            fail("All-Play career owners include m22")

    rec_owners = [oid for oid in played if in_career_book(data, oid)]
    if "m22" in rec_owners:
        fail("franchise records career book includes m22")

    h2h_owners = [a for a in (data.get("activeOwners") or []) if in_career_book(data, a)]
    if "m22" in h2h_owners:
        fail("H2H owners include m22")
    if "m22" not in (data.get("activeOwners") or []):
        fail("activeOwners dropped Gabagooners (Teams/nav still need them)")

    for f in data.get("franchises") or []:
        oid = f.get("owner")
        if oid != "m22":
            continue
        if in_career_book(data, oid):
            fail("in_career_book still admits m22")
        w = int(f.get("wins") or 0)
        l = int(f.get("losses") or 0)
        t = int(f.get("ties") or 0)
        if (w, l, t) == (0, 0, 0) and oid in rec_owners:
            fail("0-0-0 career row for m22 in franchise records")


def test_history_source(js: str, html: str) -> None:
    if "function inCareerBook" not in js:
        fail("history.js missing inCareerBook")
    if 'id === "m22"' not in js:
        fail("inCareerBook does not hard-drop m22")
    cr = re.search(r"function careerRows\(\) \{([\s\S]*?)\n  \}", js)
    if not cr or "inCareerBook" not in cr.group(1):
        fail("franchise records careerRows does not strip no-career teams")
    h2h = re.search(r"function renderH2H\(\) \{([\s\S]*?)\n  \}", js)
    if not h2h or "inCareerBook" not in h2h.group(1):
        fail("H2H still uses every activeOwner including Gabagooners")
    if "inCareerBook(r.owner)" not in js:
        fail("All-Play careerStandRows does not strip no-career teams")
    seed = re.search(r"\(DATA\.franchises \|\| \[\]\)\.forEach\(\(f\) => \{([\s\S]*?)\n    \}\);", js)
    if not seed:
        fail("cannot parse rollFranchises franchise overlay")
    elif "if (!by[oid]) {" in seed.group(1) and "seasons: 0" in seed.group(1):
        fail("rollFranchises still seeds empty 0-0-0 franchise rows")
    if "if (!by[oid]) return" not in js:
        fail("rollFranchises does not skip franchises with no 2014-2025 seasons")
    if "Gabagooners" not in js:
        fail("history.js lost the Gabagooners career-book comment")
    bust = re.search(r"history\.js\?v=(\d+)", html)
    if not bust:
        fail("history.html missing history.js cache bust")
    elif int(bust.group(1)) < 22:
        fail(f"history.js cache still v={bust.group(1)} (need v>=22)")
    if 'value="2026"' in html or 'data-y="2026"' in html:
        fail("history.html offers 2026")


def test_teams_card(teams_js: str, common: str, data: dict) -> None:
    if "function renderGrid" not in teams_js:
        fail("teams.js missing renderGrid")
    if "A.visibleFranchises(A.squads())" not in teams_js:
        fail("Teams All grid no longer paints current 0-season cards from squads")
    if 'owner: "m22"' not in common:
        fail("Gabagooners dropped from 2026 current rail")
    names = [f.get("currentName") or "" for f in (data.get("franchises") or [])]
    if not any("Gabagooners" in n for n in names):
        fail("Gabagooners missing from DATA.franchises (Teams card source)")
    if "inCareerBook" in teams_js:
        fail("teams.js imported History career-book strip (would drop the All card)")


def test_picker() -> None:
    script = ROOT / "evals" / "chi142_team_options.mjs"
    if not script.is_file():
        fail("missing evals/chi142_team_options.mjs")
        return
    try:
        raw = subprocess.check_output(["node", str(script)], cwd=str(ROOT), timeout=20)
        painted = json.loads(raw.decode())
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        fail(f"Team picker did not paint: {e}")
        return
    counts = {}
    for label, key in (("All", "all"), ("2014", "y2014"), ("2025", "y2025")):
        names = painted.get(key) or []
        counts[key] = len(names)
        gaba = [n for n in names if "Gabagooners" in n]
        if key == "all":
            if not gaba:
                fail("Gabagooners missing from Team when Season is All")
        elif gaba:
            fail(f"Gabagooners is a Team option for year={label}")
    all_n, n14, n25 = counts.get("all") or 0, counts.get("y2014") or 0, counts.get("y2025") or 0
    if (all_n, n14, n25) != (20, 11, 13):
        fail(f"Team option counts All/2014/2025 = {all_n}/{n14}/{n25}; need 20/11/13")


def main() -> int:
    hist_js = (SITE / "history.js").read_text()
    hist_html = (SITE / "history.html").read_text()
    teams_js = (SITE / "teams.js").read_text()
    common = (SITE / "common.js").read_text()
    data = json.loads((SITE / "data.json").read_text())

    test_data_book(data)
    test_history_source(hist_js, hist_html)
    test_teams_card(teams_js, common, data)
    test_picker()

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    feel_w, feel_l = career_allplay(data, "m18")
    print("PASS")
    print(
        "Gabagooners stripped from History All-Play / franchise records / H2H; "
        f"Teams All keeps the card; Feelers {feel_w}-{feel_l}; picker 20/11/13"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
