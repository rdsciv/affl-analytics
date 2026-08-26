#!/usr/bin/env python3
"""Draft Overview (all-time) + franchise-year recap.

PAR only. No ADP, no keeper leaderboard, no owner names, no Tittsburgh.
Cumulative 2014–2025 from year JSON parByOverall. MERGE applied.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def fail(msg):
    fails.append(msg)


def canon(i):
    return MERGE.get(str(i), str(i))


def main():
    html = (SITE / "draft.html").read_text()
    js = (SITE / "draft.js").read_text()
    data = json.loads((SITE / "data.json").read_text())

    # --- page ships overview + recap ---
    if "Draft Overview" not in html:
        fail("draft.html missing Draft Overview")
    if "all-time franchise" not in html.lower() and "All-time franchise draft rankings" not in html:
        fail("draft.html missing all-time franchise rankings")
    if "by position" not in html.lower() and "by team by position" not in html.lower():
        fail("draft.html missing by position")
    if 'id="draft-overview"' not in html:
        fail("draft.html missing #draft-overview")
    if 'id="draft-recap"' not in html:
        fail("draft.html missing #draft-recap")
    if "function renderOverview" not in js:
        fail("draft.js missing renderOverview")
    if "function renderRecap" not in js:
        fail("draft.js missing renderRecap")
    if "function ovCollect" not in js:
        fail("draft.js missing ovCollect")
    if "renderOverview();" not in js:
        fail("pick() never calls renderOverview")
    if "renderRecap();" not in js:
        fail("pick() never calls renderRecap")
    if "parByOverall" not in js:
        fail("draft.js does not read parByOverall")
    if "A.loadAllYears" not in js and "loadAllYears" not in js:
        fail("overview does not use loadAllYears")
    if "draft.js?v=17" not in html:
        fail("draft.html did not bump draft.js cache to v=17")
    if "AFFL does not use keepers" not in html and "AFFL does not use keepers" not in js:
        fail("missing one-line keepers denial")

    # --- metric is PAR, not ADP; no keeper board ---
    if re.search(r"grade.*ADP|ADP.*grade|matched ADP|vs consensus|% of draft", js, re.I):
        fail("JS treats ADP / consensus as the grade basis")
    adp_lines = [ln.strip() for ln in js.splitlines() if re.search(r"\bADP\b", ln)]
    for ln in adp_lines:
        if not re.search(r"not ADP|no ADP|isn't ADP|is not ADP", ln, re.I):
            fail(f"ADP mentioned as something other than a denial: {ln}")
    if re.search(r"keeper (leaderboard|board|rank|table)", html + js, re.I):
        fail("keeper leaderboard present")
    if "firstName(" in js:
        fail("draft.js uses firstName")
    if "Tittsburgh" in html or "Tittsburgh" in js:
        fail("Tittsburgh leaked onto the draft page")

    members = data.get("members") or {}
    owner_names = {v for v in members.values() if v}
    ov = js
    if "function renderOverview" in js:
        ov = js.split("function renderOverview", 1)[1]
    for name in ("Jason Kafka", "Tanner Dunn", "Patrick O'Neill", "Alex Renney"):
        if name in html or name in ov:
            fail(f"owner name {name} appears in draft overview/recap")

    # identity / MERGE
    if "A.canon" not in js or "function ownerKey" not in js:
        fail("draft.js lost ownerKey / A.canon merge")
    if "A.franchiseName" not in js and "function tName" not in js:
        fail("draft.js lost franchise name helper")
    if re.search(r'>\s*m01\s*<|"m01"', html):
        fail("raw m01 label in draft.html")
    # overview collect must canon tids
    collect = js.split("function ovCollect", 1)[1].split("function ovMean", 1)[0] if "function ovCollect" in js else ""
    if "A.canon" not in collect:
        fail("ovCollect does not apply A.canon / MERGE")

    # --- every year 2014–2025 contributes PAR keys ---
    year_n = {}
    burrow = mitchell = None
    for y in range(2014, 2026):
        d = json.loads((SITE / f"years/{y}.json").read_text())
        par = (d.get("draftValue") or {}).get("parByOverall") or {}
        year_n[y] = len(par)
        if y == 2014 and len(par) != 138:
            fail(f"2014 parByOverall has {len(par)} keys, expected 138")
        if len(par) < 1:
            fail(f"{y} contributes no PAR keys")
        if y == 2022:
            board = (d.get("draft") or {}).get("board") or []
            burrow = next((p for p in board if str(p.get("pid")) == "3915511"), None)
            mitchell = next((p for p in board if str(p.get("pid")) == "4241555"), None)
            if burrow:
                bpar = par.get(str(burrow.get("overall")))
                print(f"2022 Burrow {burrow.get('name')} par={bpar}")
                if bpar is None or abs(bpar - 82.4) > 0.6:
                    fail(f"Burrow PAR {bpar} is not ~82.4")
            else:
                fail("2022 board missing Joe Burrow")
            if mitchell:
                mpar = par.get(str(mitchell.get("overall")))
                print(f"2022 Mitchell {mitchell.get('name')} par={mpar}")
                if mpar is None or abs(mpar - (-106.0)) > 0.6:
                    fail(f"Mitchell PAR {mpar} is not ~-106")
            else:
                fail("2022 board missing Elijah Mitchell")

    print("PAR keys", year_n)
    if "2014" in js and re.search(r"year\s*<\s*2016", js.split("function renderOverview", 1)[-1][:4000]):
        fail("overview hides pre-2016 seasons")

    # known 2022 points are in the all-time pool (same attach path)
    if "parByOverall" not in collect:
        fail("ovCollect does not read each year's parByOverall — 2022 Burrow/Mitchell would drop")

    # --- simulate all-time + MERGE ---
    picks = []
    raw_oids = set()
    for y in range(2014, 2026):
        d = json.loads((SITE / f"years/{y}.json").read_text())
        board = (d.get("draft") or {}).get("board") or []
        par = (d.get("draftValue") or {}).get("parByOverall") or {}
        owners = {t["id"]: canon(t.get("owner")) for t in (data["seasons"].get(str(y), {}).get("teams") or [])}
        for p in board:
            raw = owners.get(p.get("tid"))
            # track pre-canon from season file
            for t in data["seasons"].get(str(y), {}).get("teams") or []:
                if t["id"] == p.get("tid"):
                    raw_oids.add(t.get("owner"))
            pv = par.get(str(p.get("overall")))
            if pv is None:
                continue
            oid = owners.get(p.get("tid"))
            if not oid:
                continue
            picks.append({"year": y, "oid": oid, "par": float(pv), "name": p.get("name"), "pid": p.get("pid")})

    oids = {p["oid"] for p in picks}
    if "m01" in oids:
        fail("MERGE not applied — raw m01 still a franchise key")
    if "m03" in oids or "m20" in oids:
        fail("MERGE not applied — raw m03/m20 still a franchise key")
    if "m01" in raw_oids and "m07" not in oids:
        fail("m01 seasons did not roll into m07")

    # 2022 points in the pool
    b = [p for p in picks if p["year"] == 2022 and str(p["pid"]) == "3915511"]
    m = [p for p in picks if p["year"] == 2022 and str(p["pid"]) == "4241555"]
    if not b:
        fail("Burrow 2022 not in all-time PAR pool")
    if not m:
        fail("Mitchell 2022 not in all-time PAR pool")

    # --- Feelers 2022 recap ---
    y2022 = json.loads((SITE / "years/2022.json").read_text())
    board = (y2022.get("draft") or {}).get("board") or []
    par = (y2022.get("draftValue") or {}).get("parByOverall") or {}
    teams = {t["id"]: t for t in data["seasons"]["2022"]["teams"]}
    feel_tid = next((t["id"] for t in teams.values() if canon(t.get("owner")) == "m18"), None)
    if feel_tid != 7:
        fail(f"2022 Feelers tid is {feel_tid}, expected 7")
    feel_picks = []
    by_oid = defaultdict(float)
    for p in board:
        pv = par.get(str(p.get("overall")))
        if pv is None:
            continue
        t = teams.get(p.get("tid"))
        oid = canon(t["owner"]) if t else None
        if oid:
            by_oid[oid] += float(pv)
        if p.get("tid") == 7 or oid == "m18":
            feel_picks.append(p)
    total = by_oid.get("m18")
    print(f"Feelers 2022 tid={feel_tid} picks={len(feel_picks)} totalPAR={total}")
    if not feel_picks:
        fail("Feelers 2022 recap pick list length is 0")
    if total is None:
        fail("Feelers 2022 has no total PAR")
    # recap JS must list picks and total PAR
    recap = js.split("function renderRecap", 1)[1] if "function renderRecap" in js else ""
    if "recap-picks-tbl" not in recap and "recap-picks-tbl" not in html:
        fail("recap missing pick list table")
    if "Total PAR" not in recap and "total PAR" not in recap.lower():
        fail("recap missing total PAR KPI")
    if "ownerKey" not in recap and "A.canon" not in recap:
        fail("recap does not MERGE via ownerKey / canon")
    if "A.franchiseName" not in recap and "tName" not in recap:
        fail("recap does not use current franchise name")
    if "matched ADP" in recap.lower() or "% of draft" in recap.lower():
        fail("recap has ADP copy")

    feel_name = next((f.get("currentName") for f in data["franchises"] if canon(f.get("owner")) == "m18"), "")
    if feel_name != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel_name}")
    if "Tittsburgh" in feel_name:
        fail("Feelers current name is still Tittsburgh")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
