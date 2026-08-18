#!/usr/bin/env python3
"""Draft Lab: single-season PAR lab on the Draft page.

Value is PAR already stored on site/years/{year}.json (parByOverall).
No ADP, no invented consensus, no owner labels. 2014 snake + computed PAR
still renders. Current franchise names only.
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


def main():
    html = (SITE / "draft.html").read_text()
    js = (SITE / "draft.js").read_text()
    css = (SITE / "styles.css").read_text()
    y2022 = json.loads((SITE / "years/2022.json").read_text())
    y2014 = json.loads((SITE / "years/2014.json").read_text())
    data = json.loads((SITE / "data.json").read_text())

    # --- page ships the lab ---
    if "Draft Lab" not in html:
        fail("draft.html missing Draft Lab heading")
    if "By position" not in html:
        fail("draft.html missing By position")
    if "By round" not in html:
        fail("draft.html missing By round")
    if 'id="draft-lab"' not in html:
        fail("draft.html missing #draft-lab")
    if "function renderLab" not in js:
        fail("draft.js missing renderLab")
    if "labParOf" not in js or "parByOverall" not in js:
        fail("draft.js does not read parByOverall / PAR")
    if "renderLab();" not in js:
        fail("pick() never calls renderLab")
    if "draft.js?v=17" not in html:
        fail("draft.html did not bump draft.js cache to v=17")
    if "styles.css?v=16" not in html:
        fail("draft.html did not bump styles.css cache to v=16")
    if "lab-board-cell" not in css:
        fail("styles.css missing visual-board rules")
    if "Mean PAR by round" not in js:
        fail("round chart is not labeled mean PAR")

    # --- metric is PAR, not ADP ---
    lab = js.split("function renderLab", 1)[1].split("async function pick", 1)[0] if "function renderLab" in js else js
    if re.search(r"grade.*ADP|ADP.*grade|matched ADP|vs consensus|% of draft", js, re.I):
        fail("JS treats ADP / consensus as the grade basis")
    adp_lines = [ln.strip() for ln in js.splitlines() if re.search(r"\bADP\b", ln)]
    for ln in adp_lines:
        if not re.search(r"not ADP|no ADP|isn't ADP|is not ADP", ln, re.I):
            fail(f"ADP mentioned as something other than a denial: {ln}")
    if "LOSS" in lab:
        fail("lab renders LOSS labels")
    if "firstName(" in js:
        fail("draft.js uses firstName")
    if "Tittsburgh" in html or "Tittsburgh" in js:
        fail("Tittsburgh leaked onto the draft page")

    # --- identity: current names via existing helpers ---
    if "A.franchiseName" not in js and "function tName" not in js:
        fail("draft.js lost franchise name helper")
    if "function ownerKey" not in js or "A.canon" not in js:
        fail("draft.js lost ownerKey / A.canon merge")
    if "teamCell(r.tid)" not in lab:
        fail("team grades not using teamCell (current franchise name)")
    members = data.get("members") or {}
    owner_names = {v for v in members.values() if v}
    for name in ("Jason Kafka", "Tanner Dunn", "Patrick O'Neill", "Alex Renney"):
        if name in html or name in lab:
            fail(f"owner name {name} appears in draft lab")

    # --- 2022 board + known PAR from the year file (do not invent) ---
    board = (y2022.get("draft") or {}).get("board") or []
    par_map = (y2022.get("draftValue") or {}).get("parByOverall") or {}
    if len(board) != 180:
        fail(f"2022 board has {len(board)} picks, expected 180")
    if len(par_map) != 180:
        fail(f"2022 parByOverall has {len(par_map)} keys, expected 180")

    burrow = next((p for p in board if str(p.get("pid")) == "3915511"), None)
    if not burrow:
        fail("2022 board missing Joe Burrow pid 3915511")
    else:
        bpar = par_map.get(str(burrow.get("overall")))
        print(f"2022 Burrow {burrow.get('name')} bid={burrow.get('bid')} overall={burrow.get('overall')} par={bpar}")
        if burrow.get("bid") != 3:
            fail(f"Burrow bid is {burrow.get('bid')}, expected 3")
        if bpar is None:
            fail("Burrow has no parByOverall")
        elif abs(bpar - 82.4) > 0.6:
            fail(f"Burrow PAR {bpar} is not ~82 from the year json")
        if bpar is not None and bpar < 50:
            fail("Burrow should be a high-PAR steal")

    mitchell = next((p for p in board if str(p.get("pid")) == "4241555"), None)
    if not mitchell:
        fail("2022 board missing Elijah Mitchell pid 4241555")
    else:
        mpar = par_map.get(str(mitchell.get("overall")))
        print(f"2022 Mitchell {mitchell.get('name')} bid={mitchell.get('bid')} overall={mitchell.get('overall')} par={mpar}")
        if mpar is None:
            fail("Mitchell has no parByOverall")
        elif abs(mpar - (-106.0)) > 0.6:
            fail(f"Mitchell PAR {mpar} is not ~-106 from the year json")
        if mpar is not None and mpar >= 0:
            fail("Mitchell should be a bust (negative PAR)")

    # lab ranks by PAR, so Burrow/Mitchell must be attachable
    if "labParOf" not in js or "parByOverall" not in js:
        fail("cannot attach 2022 PAR onto the board")

    # --- 2014 still grades: snake + computed PAR ---
    d14 = y2014.get("draft") or {}
    dv14 = y2014.get("draftValue") or {}
    if d14.get("auction"):
        fail("2014 should be snake")
    if not dv14.get("computed"):
        fail("2014 draftValue.computed should be true")
    if not (dv14.get("parByOverall") or {}):
        fail("2014 missing parByOverall — lab would empty-state a graded year")
    if len(d14.get("board") or []) < 100:
        fail("2014 board too small")
    # lab must not hide snake / computed years
    if re.search(r"year\s*<\s*2016", lab) or re.search(r"year\s*<\s*2018", lab):
        fail("lab hides pre-auction / pre-2018 seasons")
    if "labAuction()" not in js or "snake" not in lab.lower():
        fail("2014 snake cost/slot path missing")
    if "labCol" not in js:
        fail("visual board missing slot mapper")
    # snake columns remap even rounds; auction uses stored pick
    if "slots + 1 - p.pick" not in js and "slots+1-p.pick" not in js:
        fail("snake slot remap missing")
    if "if (auction) return p.pick" not in js:
        fail("auction visual board must use stored pick, not an invented snake")

    # empty / all-years scope
    if "Pick a season" not in html and "pick a season" not in js.lower():
        fail("no pick-a-season empty state for all-years scope")
    if "no parByOverall" not in js:
        fail("missing honest empty state when parByOverall is absent")

    # team grades from local PAR distribution, not copied ADP letters
    if "function labLetter" not in js:
        fail("letter grades not computed locally")
    if "A+" not in js or '"F"' not in js:
        fail("grade scale missing A+ / F")
    if "Best steal" not in html or "Worst reach" not in html:
        fail("team grades table missing steal/reach columns")

    print(f"2014 snake computed={dv14.get('computed')} parKeys={len(dv14.get('parByOverall') or {})} board={len(d14.get('board') or [])}")
    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
