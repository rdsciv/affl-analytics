#!/usr/bin/env python3
"""ESPN weekly proj overlay on the Players production chart."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = ROOT / "data"
fails = []


def fail(m):
    fails.append(m)


def main():
    proj_path = SITE / "proj.json"
    if not proj_path.exists():
        fail("site/proj.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    proj = json.loads(proj_path.read_text())

    y25 = proj.get("2025") or proj.get(2025) or {}
    taylor = y25.get("4242335") or y25.get(4242335) or {}
    pos = []
    for wk, val in taylor.items():
        if isinstance(val, (int, float)) and val > 0:
            pos.append(wk)
    if len(pos) < 10:
        fail(f"Taylor 2025 has {len(pos)} weeks with numeric proj > 0 (need >= 10)")

    # Historical backfill (probe of 2024 W1 found weekly appliedTotal).
    pre = {}
    for y, players in proj.items():
        ys = str(y)
        if ys >= "2025":
            continue
        n = 0
        for weeks in (players or {}).values():
            if not isinstance(weeks, dict):
                continue
            for val in weeks.values():
                if isinstance(val, (int, float)) and val > 0:
                    n += 1
        pre[ys] = n
    if not any(n >= 100 for n in pre.values()):
        fail(
            "no pre-2025 year has >= 100 player-weeks with proj>0; "
            f"counts={ {k: pre[k] for k in sorted(pre)} }"
        )

    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()

    if "label: \"ESPN proj\"" not in js and "label: 'ESPN proj'" not in js:
        fail("players.js chart missing ESPN proj dataset")
    if "actual (started / benched" not in js:
        fail("players.js chart missing actual (started / benched) legend")
    if "weekProj" not in js:
        fail("players.js missing weekProj lookup")
    if "spanGaps: false" not in js:
        fail("players.js proj series should spanGaps:false so missing weeks stay omitted")
    if re.search(r"weekProj\([^)]*\)\s*\|\|\s*0", js):
        fail("players.js coerces missing proj to 0")
    if re.search(r"weekProj\([^)]*\)\s*\?\?\s*0", js):
        fail("players.js nullish-coalesces missing proj to 0")
    if "<th>Proj</th>" not in js:
        fail("players.js log missing Proj header")
    if 'pj != null ? fmt(pj, 1) : "—"' not in js and "pj != null ? fmt(pj, 1) : '—'" not in js:
        fail("players.js log does not keep missing proj as em dash")
    if "hasOwnProperty.call(rec, key)" not in js:
        fail("weekProj must distinguish missing from ESPN 0")
    if "ESPN weekly projection" not in html:
        fail("players.html card subtitle does not mention ESPN weekly projection")
    if "players.js?v=" not in html:
        fail("players.html did not cache-bust players.js")

    # No invented zeros: a 2025 box player-week without a weekly appliedTotal
    # must not appear in proj.json (especially not as 0).
    raw_weeks = {}
    for w in range(1, 18):
        path = DATA / f"box_w{w}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        week = d.get("scoringPeriodId") or w
        have = set()
        for g in d.get("schedule") or []:
            if g.get("matchupPeriodId") not in (None, week, w):
                continue
            for side in ("home", "away"):
                s = g.get(side) or {}
                roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
                if not roster:
                    continue
                for e in roster.get("entries") or []:
                    ppe = e.get("playerPoolEntry") or {}
                    p = ppe.get("player") or {}
                    pid = p.get("id") if p.get("id") is not None else e.get("playerId")
                    if pid is None:
                        continue
                    pid = str(int(pid))
                    weekly = False
                    for st in p.get("stats") or []:
                        if st.get("statSourceId") == 1 and st.get("scoringPeriodId") == week:
                            if st.get("appliedTotal") is not None:
                                weekly = True
                                break
                    if weekly:
                        have.add(pid)
        raw_weeks[int(week)] = have

    invented = 0
    checked_missing = 0
    box = json.loads((DATA / "box_2025.json").read_text())
    for wk_s, games in (box.get("weeks") or {}).items():
        wk = int(wk_s)
        raw = raw_weeks.get(wk) or set()
        for g in games:
            for side in ("home", "away"):
                for row in ((g.get(side) or {}).get("roster") or []):
                    if not row:
                        continue
                    pid = str(int(row[0]))
                    stored = (y25.get(pid) or {}).get(str(wk))
                    if pid not in raw:
                        checked_missing += 1
                        if stored is not None:
                            invented += 1
                            if invented <= 5:
                                fail(f"invented proj for pid {pid} 2025 W{wk} = {stored}")
    if invented:
        fail(f"{invented} invented proj values for box player-weeks with no ESPN weekly appliedTotal")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    n_pw = sum(len(w) for y in proj.values() for w in y.values())
    print("PASS")
    print(f"proj.json years={sorted(proj)} player-weeks={n_pw}")
    print(f"Taylor 2025 weeks with proj>0: {len(pos)}")
    print(f"pre-2025 proj>0 player-weeks: { {k: pre[k] for k in sorted(pre)} }")
    print(f"box player-weeks without ESPN weekly proj (not stored): {checked_missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
