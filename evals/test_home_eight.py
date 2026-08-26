#!/usr/bin/env python3
"""Home eight + awards: current names, empty keys, 2014 H2H.

Reads site files only (no rebuild). Proves:

  1. Current franchise names (never owner first names, no was/inactive).
  2. Feelers label is Grand Teeton Feelers (m18 / 2025 tid 7).
  3. Missing opportunity / trophies / luckCard / awards => empty state, no crash.
  4. 2014 trophies still render H2H if h2hChampionTid is present.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def src(name):
    return (SITE / name).read_text()


def main():
    data = json.loads((SITE / "data.json").read_text())
    app = src("app.js")
    hist = src("history.js")
    awards = src("awards.js")
    index = src("index.html")
    history_html = src("history.html")

    if not (SITE / "awards.html").exists():
        fail("awards.html missing")
    if not (SITE / "awards.js").exists():
        fail("awards.js missing")

    feel = [f for f in data.get("franchises") or [] if f.get("owner") == "m18"]
    if len(feel) != 1:
        fail(f"Feelers should be 1 franchise row, got {len(feel)}")
    elif feel[0].get("currentName") != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel[0].get('currentName')!r}")
    else:
        print("Feelers current name: Grand Teeton Feelers")

    teams_2025 = (data.get("seasons") or {}).get("2025", {}).get("teams") or []
    feel_tid = [t for t in teams_2025 if t.get("owner") == "m18"]
    if not feel_tid or feel_tid[0].get("id") != 7:
        fail(f"2025 Feelers tid should be 7, got {feel_tid}")
    if feel_tid and feel_tid[0].get("name") != "Grand Teeton Feelers":
        fail(f"2025 Feelers season name is {feel_tid[0].get('name')!r}")

    for body, label in ((app, "app.js"), (hist, "history.js"), (awards, "awards.js")):
        if "was " in body or "inactive" in body:
            fail(f"{label} still renders was/inactive labels")
        if "firstName(" in body and label != "app.js":
            fail(f"{label} uses firstName")
        if "Tittsburgh Feelers" in body:
            fail(f"{label} hardcodes Tittsburgh Feelers")

    # Home new surfaces must use current franchise names, not owner first names
    for fn in ("function currentFranchise", "function renderTrophies", "function renderLuckCard",
               "function opportunityRows"):
        if fn not in app:
            fail(f"app.js missing {fn}")
    if "franchiseName(owner)" not in app:
        fail("app.js currentFranchise does not call franchiseName")
    trophy_fn = app.split("function renderTrophies", 1)[-1].split("function ", 1)[0]
    if "firstName" in trophy_fn or "memberName" in trophy_fn:
        fail("renderTrophies uses owner first names")
    luck_fn = app.split("function renderLuckCard", 1)[-1].split("function ", 1)[0]
    if "firstName" in luck_fn or "memberName" in luck_fn:
        fail("renderLuckCard uses owner first names")

    if "A.franchiseName" not in hist:
        fail("history.js trophy case does not use A.franchiseName")
    if "A.franchiseName" not in awards and "franchiseName" not in awards:
        fail("awards.js does not use franchiseName")
    if "A.franchiseLogo" not in awards:
        fail("awards.js does not use franchiseLogo")

    # empty keys: no crash
    if "opportunityRows(NG)" not in app and "opportunityRows(bundle)" not in app:
        fail("app.js does not read opportunity / receivingUsage via opportunityRows")
    if "not in the ${curYear} file yet" not in app and "not in the" not in app:
        fail("app.js missing empty-state copy for missing keys")
    for key in ("trophies", "luckCard", "h2hChampionTid"):
        if key not in app:
            fail(f"app.js never reads {key}")
    if "bundle.awards" not in awards and "awards[kind]" not in awards:
        fail("awards.js does not read awards.allLeague / bushLeague")
    if "not in the" not in awards:
        fail("awards.js missing empty state when awards key is absent")

    # 2014 H2H still renders if present
    if "h2hChampionTid" not in app:
        fail("app.js does not render trophies.h2hChampionTid")
    if "2014 trophies still render H2H" not in app and "hasH2H" not in app:
        fail("app.js does not keep H2H Cup when Board/Roto are missing")
    if "trophySlot(\"Cup\"" not in app and "trophySlot('Cup'" not in app:
        fail("app.js does not render a Cup slot from h2hChampionTid")

    # opportunity board columns + player links
    for col in ("Tgt Share", "WOPR", "aDOT", "xFP", "FP−xFP"):
        if col not in index:
            fail(f"index.html opportunity board missing {col}")
    if "players.html?year=" not in app or "pid=" not in app:
        fail("opportunity board does not link players.html?pid=")
    if 'data-k="wopr"' not in index:
        fail("opportunity board is not sortable")

    # luck card columns
    for col in ("W-L", "All-Play", "Median", "Exp W", "Sched luck", "TD−xTD"):
        if col not in index:
            fail(f"luck card missing {col}")

    # trophies card
    if 'id="trophy-grid"' not in index:
        fail("index.html missing trophy grid")
    if "medianChampionTid" not in app or "allPlayChampionTid" not in app:
        fail("app.js Board trophy does not read median / all-play")
    if "rotoChampionTid" not in app:
        fail("app.js missing Roto trophy")

    # history all-time counts
    if 'id="trophy-tbl"' not in history_html:
        fail("history.html missing trophy case")
    if "rollTrophies" not in hist:
        fail("history.js missing rollTrophies")

    # awards page
    awards_html = src("awards.html")
    if "All-League" not in awards_html or "Bush League" not in awards_html:
        fail("awards.html missing All-League / Bush League")
    if "you do not want to lead" not in awards_html.lower() and "you do not want to lead" not in awards.lower():
        fail("Bush League copy missing the 'do not want to lead' line")
    if "awards.html" not in index or "awards.html" not in history_html:
        fail("Awards nav missing on index or history")

    # cache-bust
    if "app.js?v=" not in index:
        fail("index.html app.js is not cache-busted")
    if "awards.js?v=" not in awards_html:
        fail("awards.html awards.js is not cache-busted")

    # year files may still be missing keys — that is the empty-state case
    y2025 = json.loads((SITE / "years" / "2025.json").read_text())
    y2014 = json.loads((SITE / "years" / "2014.json").read_text())
    for y, bundle in ((2025, y2025), (2014, y2014)):
        for key in ("opportunity", "receivingUsage", "trophies", "luckCard", "awards"):
            if key in bundle:
                print(f"{y}.json has {key}")
    if "trophies" in y2014 and (y2014["trophies"] or {}).get("h2hChampionTid") is None:
        fail("2014 trophies present but h2hChampionTid missing")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("home eight: current names, Feelers=Grand Teeton Feelers, empty keys safe, 2014 H2H Cup path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
