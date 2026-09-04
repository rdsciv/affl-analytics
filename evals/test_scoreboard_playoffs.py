#!/usr/bin/env python3
"""2014–2016 scoreboard playoff labels + recovered-starter enrichment path."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def main():
    js = (SITE / "scoreboard.js").read_text()
    html = (SITE / "scoreboard.html").read_text()

    # period 14 label: R1 and/or 14–15 (en-dash or hyphen)
    if not re.search(r"R1|14[–-]15", js):
        fail("scoreboard.js period 14 label missing R1 or 14–15")
    else:
        print("period 14 label: R1 / 14–15 present")

    # period 15 label: Final and/or 16–17
    if not re.search(r"Final|16[–-]17", js):
        fail("scoreboard.js period 15 label missing Final or 16–17")
    else:
        print("period 15 label: Final / 16–17 present")

    # trophy must not be applied to every week > 13 for 2014–2016
    # the old bug: w > YD.regWeeks ? ' 🏆'
    if re.search(r"w\s*>\s*YD\.regWeeks\s*\?\s*['\"] 🏆", js):
        fail("scoreboard.js still trophies every week > regWeeks (2014–2016 bug)")
    if "isChampionshipPeriod" not in js and "twoWeekPlayoffs" not in js:
        fail("scoreboard.js missing championship-period gate for 2014–2016")
    if "twoWeekPlayoffs" in js:
        if not re.search(r"p\s*===\s*15", js) and "period === 15" not in js and "p === 15" not in js:
            fail("2014–2016 championship period 15 not gated")
    print("trophy gated (not every week > 13)")

    # identity: franchiseName, not memberName / historical t.name as primary
    if "franchiseName" not in js:
        fail("scoreboard.js does not use A.franchiseName")
    if "memberName" in js:
        fail("scoreboard.js still shows owner first names via memberName")

    # enrichment path
    if "pre2018_starts" not in js:
        fail("scoreboard.js missing pre2018_starts enrichment path")
    else:
        print("roster enrichment path: pre2018_starts")
    if "unidentified" not in js:
        fail("scoreboard.js missing leftover/unidentified callout for pre-2018 holes")
    if "pre2018_candidates" not in js:
        fail("scoreboard.js missing CERTAIN candidate overlay")
    if "Late-season snapshot" not in js:
        fail("scoreboard.js must not present the undated snapshot as this week's roster")
    cand_path = SITE / "pre2018_candidates.json"
    if not cand_path.exists():
        fail("site/pre2018_candidates.json missing")
    else:
        cand = json.loads(cand_path.read_text())
        sliger = (((cand.get("2014") or {}).get("1") or {}).get("3") or [])
        if not any(int(r.get("pid")) == 14993 and abs(float(r.get("pts") or 0) - 8) <= 0.05 for r in sliger):
            fail("Sliger 2014 W1 CERTAIN sidecar missing Zuerlein 14993 at 8 pts")
        else:
            print("sidecar CERTAIN: Sliger 2014 W1 Zuerlein 8")
        free = [r for weeks in cand.values() for teams in weeks.values()
                for rows in teams.values() for r in rows if r.get("evidence") == "free"]
        if free:
            fail(f"{len(free)} free fills in CERTAIN sidecar")
    for phrase in ("not rostered", "not on an AFFL roster"):
        if phrase in js:
            fail(f"scoreboard.js uses banned phrase {phrase!r}")

    # 2014 championship scores untouched: Feelers tid 7 vs Horndogs tid 10 in week 15
    yd = json.loads((SITE / "years" / "2014.json").read_text())
    games = (yd.get("weeks") or {}).get("15") or []
    champ = None
    for g in games:
        tids = {g["home"]["tid"], g["away"]["tid"]}
        if 7 in tids and 10 in tids:
            champ = g
            break
    if not champ:
        fail("2014 year JSON week 15 missing Feelers (7) vs Horndogs (10)")
    else:
        sides = {champ["home"]["tid"]: champ["home"]["pts"], champ["away"]["tid"]: champ["away"]["pts"]}
        print(f"2014 Final Feelers {sides.get(7)} vs Horndogs {sides.get(10)}")
        if sides.get(7) != 179.0:
            fail(f"2014 Feelers championship pts {sides.get(7)} != 179.0 (do not change scores)")
        if sides.get(10) != 124.0:
            fail(f"2014 Horndogs championship pts {sides.get(10)} != 124.0 (do not change scores)")

    r1 = None
    for g in (yd.get("weeks") or {}).get("14") or []:
        tids = {g["home"]["tid"], g["away"]["tid"]}
        if 7 in tids and 5 in tids:
            r1 = g
            break
    if r1:
        sides = {r1["home"]["tid"]: r1["home"]["pts"], r1["away"]["tid"]: r1["away"]["pts"]}
        print(f"2014 R1 Feelers {sides.get(7)} vs Mad Dawgs {sides.get(5)}")
        if sides.get(7) != 192.0 or sides.get(5) != 189.0:
            fail("2014 R1 scores changed (Feelers 192 vs Mad Dawgs 189 expected)")

    # starts: week 16/17 if ESPN returned them — optional for pass
    starts_path = SITE / "pre2018_starts.json"
    if starts_path.exists():
        starts = json.loads(starts_path.read_text())
        y2014 = starts.get("2014") or {}
        weeks = set()
        for rec in y2014.values():
            if isinstance(rec, dict):
                weeks.update(int(w) for w in rec if str(w).isdigit())
        print(f"2014 start weeks: {sorted(weeks)}")
        if 16 in weeks or 17 in weeks:
            print("2014 starts include championship NFL week 16 and/or 17")
        else:
            print("2014 starts have no W16/W17 (ESPN empty is allowed)")
    else:
        print("pre2018_starts.json missing — labels still tested")

    if "scoreboard.js?v=" not in html:
        fail("scoreboard.html did not cache-bust scoreboard.js")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/scoreboard.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"scoreboard.html HTTP {code}")
        else:
            print("scoreboard.html HTTP 200")
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
