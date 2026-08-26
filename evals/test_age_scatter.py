#!/usr/bin/env python3
"""Phase 6 #5 Age is Just a Number: live ageOn, no frozen table, no Tittsburgh."""
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FEELERS = "m18"
YEAR = 2025
fails = []
fail = lambda m: fails.append(m)


def age_on(birth, as_of=None):
    if not birth:
        return None
    parts = str(birth)[:10].split("-")
    if len(parts) < 3:
        return None
    b = date(int(parts[0]), int(parts[1]), int(parts[2]))
    a = as_of or date.today()
    if a < b:
        return None
    return (a - b).days / 365.2425


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    cjs = (SITE / "common.js").read_text()

    if 'id="age-scatter-block"' not in html:
        fail("history.html missing #age-scatter-block")
    if "Age is Just a Number" not in html:
        fail("history.html missing Age is Just a Number title")
    if 'id="age-scatter-chart"' not in html:
        fail("history.html missing #age-scatter-chart")
    if 'id="age-squads"' not in html:
        fail("history.html missing oldest/youngest #age-squads")
    if 'id="age-asof"' not in html:
        fail("history.html missing as-of date input")

    if "function renderAgeScatter" not in js:
        fail("history.js missing renderAgeScatter")
    if "A.ageOn" not in js:
        fail("history.js does not call A.ageOn")
    if "A.playerBio" not in js:
        fail("history.js does not use A.playerBio")
    if "A.loadBios" not in js:
        fail("history.js does not load player_bio.json via A.loadBios")
    if "A.franchiseName" not in js:
        fail("history.js does not use A.franchiseName")
    if "A.onNextMidnight" not in js:
        fail("history.js missing midnight age refresh")
    if "pwrPct" not in js:
        fail("history.js does not read Power Win % (pwrPct)")
    if "pre2018_season_rosters" not in js:
        fail("history.js does not use snapshot/draft roster for 2014–17")
    if "ageByYear" in js:
        fail("history.js still reads frozen ageByYear")
    if "09-01" in js and "ageOn" in js:
        # live as-of must not hardcode Sept 1 for this card
        if 'String(y) + "-09-01"' in js or '"-09-01"' in js:
            fail("age scatter uses a frozen Sept 1 table")
    if "Tittsburgh" in html or "Tittsburgh" in js:
        fail("Tittsburgh leaked onto History age card")

    if "function ageOn" not in cjs:
        fail("common.js missing live ageOn")
    if "ageByYear && rec.ageByYear" in cjs:
        fail("playerBio still reads frozen ageByYear")

    data = json.loads((SITE / "data.json").read_text())
    year = json.loads((SITE / "years" / f"{YEAR}.json").read_text())
    bio = json.loads((SITE / "player_bio.json").read_text())
    feel = next((f for f in data.get("franchises") or [] if f.get("owner") == FEELERS), None)
    if not feel:
        fail("Feelers franchise missing")
    elif "Tittsburgh" in (feel.get("currentName") or ""):
        fail(f"Feelers currentName is {feel.get('currentName')}")
    elif "Feelers" not in (feel.get("currentName") or ""):
        fail(f"Feelers currentName is {feel.get('currentName')}")

    tid = next((t["id"] for t in data["seasons"][str(YEAR)]["teams"] if t.get("owner") == FEELERS), None)
    if tid is None:
        fail("Feelers 2025 team missing")
    roster_exists = bool(year.get("hasRosters")) and any(
        any((w[3] == tid or w[3] == int(tid)) for w in (p.get("wk") or []))
        for p in (year.get("players") or [])
    )
    print(f"2025 roster exists for Feelers tid={tid}: {roster_exists}")
    if roster_exists:
        ages = []
        for p in year.get("players") or []:
            weeks = p.get("wk") or []
            if not any((w[3] == tid or w[3] == int(tid)) for w in weeks):
                continue
            rec = bio.get(str(p.get("pid"))) or {}
            a = age_on(rec.get("birth"))
            if a is not None:
                ages.append(a)
        if not ages:
            fail("Feelers 2025 roster exists but no finite live ages from birth dates")
        else:
            mean = sum(ages) / len(ages)
            if not math.isfinite(mean):
                fail(f"Feelers 2025 mean age is not finite: {mean}")
            else:
                print(f"Feelers 2025 mean live age = {mean:.2f} from {len(ages)} birth dates")

    # league oldest / youngest for the report
    MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
    canon = lambda i: MERGE.get(str(i), str(i))
    franch = {f["owner"]: f.get("currentName") for f in data.get("franchises") or []}
    owners = {t["id"]: canon(t["owner"]) for t in data["seasons"][str(YEAR)]["teams"]}
    by_tid = {}
    for p in year.get("players") or []:
        seen = set()
        for w in p.get("wk") or []:
            seen.add(w[3])
        rec = bio.get(str(p.get("pid"))) or {}
        a = age_on(rec.get("birth"))
        if a is None:
            continue
        for tid2 in seen:
            by_tid.setdefault(tid2, []).append(a)
    rows = []
    for tid2, ages in by_tid.items():
        oid = owners.get(tid2)
        if not oid or not ages:
            continue
        rows.append((sum(ages) / len(ages), franch.get(oid) or oid, oid, len(ages)))
    rows.sort()
    if rows:
        print(f"2025 youngest: {rows[0][1]} {rows[0][0]:.2f} (n={rows[0][3]})")
        print(f"2025 oldest: {rows[-1][1]} {rows[-1][0]:.2f} (n={rows[-1][3]})")
        if any("Tittsburgh" in (r[1] or "") for r in rows):
            fail("Tittsburgh appeared in 2025 age names")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/history.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"history.html HTTP {code}")
        else:
            print("history.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/player_bio.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail(f"player_bio.json HTTP {c2}")
        else:
            print("player_bio.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
