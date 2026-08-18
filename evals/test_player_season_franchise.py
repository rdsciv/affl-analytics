#!/usr/bin/env python3
"""Player page season + franchise tables (League Legacy-style).

Gates:
- players.js/html have the two tables
- Hurts (4040715) has multiple season rows including PHI
- Adams (16800) franchise rows use current names, no Tittsburgh
- cache bust players.js
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def canon(oid):
    if oid is None or oid == "":
        return None
    return MERGE.get(str(oid), str(oid))


def is_year(k):
    return str(k).isdigit() and len(str(k)) == 4


def is_week(k):
    return str(k).isdigit() and int(k) > 0


def nfl_season_pts(rec, y):
    weeks = rec.get(str(y)) or {}
    s = n = 0
    for wk, row in weeks.items():
        if not is_week(wk) or not isinstance(row, dict):
            continue
        if row.get("pts") is not None:
            s += float(row["pts"])
            n += 1
    return s if n else None


def nfl_team(rec, y):
    weeks = rec.get(str(y)) or {}
    wks = sorted((k for k in weeks if is_week(k)), key=lambda x: int(x))
    for wk in reversed(wks):
        row = weeks[wk]
        if isinstance(row, dict) and row.get("team"):
            return row["team"]
    return ""


def owner_for_tid(data, year, tid):
    if tid is None:
        return None
    teams = ((data.get("seasons") or {}).get(str(year)) or {}).get("teams") or []
    for t in teams:
        if t.get("id") == tid:
            return canon(t.get("owner"))
    return None


def current_name(data, owner):
    oid = canon(owner)
    for f in data.get("franchises") or []:
        if canon(f.get("owner")) == oid:
            return f.get("currentName") or ""
    return ""


def player_years(pid, index, nfl, pre, starts):
    years = set()
    meta = index.get(str(pid)) or {}
    for y in meta.get("years") or []:
        years.add(int(y))
    rec = nfl.get(str(pid)) or {}
    for y in rec:
        if is_year(y):
            years.add(int(y))
    for y, bag in (pre or {}).items():
        if (bag or {}).get(str(pid)):
            years.add(int(y))
    for y, bag in (starts or {}).items():
        if (bag or {}).get(str(pid)):
            years.add(int(y))
    return sorted(years, reverse=True)


def season_rows(pid, data, index, nfl, pre, starts):
    rec = nfl.get(str(pid)) or {}
    out = []
    for y in player_years(pid, index, nfl, pre, starts):
        yp = None
        ypath = SITE / "years" / f"{y}.json"
        if ypath.exists():
            yj = json.loads(ypath.read_text())
            yp = next((p for p in (yj.get("players") or []) if p.get("pid") == int(pid)), None)
        snap = None if y >= 2018 else ((pre.get(str(y)) or {}).get(str(pid)))
        tid = None
        if yp and yp.get("mainTeam") is not None:
            tid = yp["mainTeam"]
        elif snap and snap.get("tid") is not None:
            tid = snap["tid"]
        elif snap and snap.get("draftTid") is not None:
            tid = snap["draftTid"]
        owner = owner_for_tid(data, y, tid)
        starts_n = st_pts = None
        if yp and (yp.get("starts") is not None or yp.get("stPts") is not None):
            starts_n = yp.get("starts") or 0
            st_pts = yp.get("stPts") or 0
        else:
            bag = (starts.get(str(y)) or {}).get(str(pid)) or {}
            if bag:
                starts_n = len(bag)
                st_pts = sum(float((bag[k] or {}).get("pts") or 0) for k in bag)
        out.append({
            "year": y,
            "owner": owner,
            "franchise": current_name(data, owner) if owner else "—",
            "nfl": nfl_team(rec, y) or "—",
            "pts": nfl_season_pts(rec, y),
            "starts": starts_n,
            "stPts": st_pts,
        })
    return out


def franchise_rows(seasons):
    by = {}
    for s in seasons:
        if not s.get("owner"):
            continue
        oid = canon(s["owner"])
        a = by.setdefault(oid, {"owner": oid, "name": s["franchise"], "seasons": 0, "pts": 0, "starts": 0})
        a["seasons"] += 1
        if s.get("stPts") is not None:
            a["pts"] += float(s["stPts"])
        if s.get("starts") is not None:
            a["starts"] += int(s["starts"])
    return sorted(by.values(), key=lambda r: (-r["pts"], -r["starts"], r["name"]))


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()
    data = json.loads((SITE / "data.json").read_text())
    index = json.loads((SITE / "player_index.json").read_text())
    nfl = json.loads((SITE / "nfl_weeks.json").read_text())
    pre = json.loads((SITE / "pre2018_rosters.json").read_text())
    starts = json.loads((SITE / "pre2018_starts.json").read_text())

    if 'id="pl-season-tbl"' not in html:
        fail("players.html missing #pl-season-tbl")
    if 'id="pl-franchise-tbl"' not in html:
        fail("players.html missing #pl-franchise-tbl")
    if "function careerSeasonRows" not in js:
        fail("players.js missing careerSeasonRows")
    if "function careerFranchiseRows" not in js:
        fail("players.js missing careerFranchiseRows")
    if "function renderCareerTables" not in js:
        fail("players.js missing renderCareerTables")
    if "A.franchiseName" not in js:
        fail("players.js does not use A.franchiseName")
    if "A.canon" not in js and "MERGE" not in js:
        fail("players.js missing MERGE/canon for franchise identity")
    if "preSnap" not in js or "draftTid" not in js:
        fail("players.js missing 2014-17 snapshot/draft franchise path")
    if "not rostered" in js.split("function careerSeasonRows")[1][:4000] if "function careerSeasonRows" in js else "":
        fail("season table labels not rostered")
    if "Tittsburgh" in js:
        fail("players.js mentions Tittsburgh")
    if "memberName" in js or "ownerName" in js:
        fail("players.js uses owner first names")
    if '"all-time"' not in js or '"pos rank"' not in js or '"best week"' not in js:
        fail("shipped hero tiles were ripped out")
    if "yoffstud" not in js or "drafted → yoff" not in js or "AFFL titles" not in js:
        fail("shipped yoff/rings/draft tiles were ripped out")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html did not cache-bust players.js")
    elif int(bust.group(1)) < 18:
        fail(f"players.js cache still v={bust.group(1)}")

    hurts = season_rows("4040715", data, index, nfl, pre, starts)
    if len(hurts) < 2:
        fail(f"Hurts has {len(hurts)} season rows (need multiple)")
    if not any(r["nfl"] == "PHI" for r in hurts):
        fail("Hurts season rows missing PHI")
    print("Hurts seasons:")
    for r in hurts[:2]:
        pts = "—" if r["pts"] is None else f"{r['pts']:.1f}"
        st = "—" if r["starts"] is None else r["starts"]
        stp = "—" if r["stPts"] is None else f"{r['stPts']:.1f}"
        print(f"  {r['year']}  {r['franchise']}  {r['nfl']}  pts={pts}  starts={st}  started={stp}")

    adams = season_rows("16800", data, index, nfl, pre, starts)
    frans = franchise_rows(adams)
    names = [f["name"] for f in frans]
    if not frans:
        fail("Adams has no franchise rows")
    if any("Tittsburgh" in (n or "") for n in names):
        fail(f"Adams franchise rows include Tittsburgh: {names}")
    current = {f.get("currentName") for f in data.get("franchises") or []}
    for n in names:
        if n and n != "—" and n not in current:
            fail(f"Adams franchise name is not current: {n}")
    firsts = {str(v).split()[0] for v in (data.get("members") or {}).values() if v}
    for n in names:
        if n in firsts:
            fail(f"Adams franchise row uses owner first name: {n}")
    feel = current_name(data, "m18")
    if feel != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel}")
    if "Grand Teeton Feelers" not in names:
        fail(f"Adams franchise rows missing Feelers: {names}")
    print("Adams franchises:")
    for f in frans[:2]:
        print(f"  {f['name']}  seasons={f['seasons']}  pts={f['pts']:.1f}  starts={f['starts']}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
