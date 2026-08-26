#!/usr/bin/env python3
"""Build site/pre2018_starts.json from data/box_raw/{2014-2017}/w{n}.json.

Starter rows only (not BN/IR). Re-run after fetch_pre2018_starts.py.
Does not invent weekly starts.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import fetch  # noqa: E402

RAW = os.path.join(ROOT, "data", "box_raw")
SITE = os.path.join(ROOT, "site")
WEEKS = {2014: range(1, 18), 2015: range(1, 18), 2016: range(1, 18), 2017: range(1, 17)}
BENCH = {20, 21}
BENCH_NAMES = {"BN", "IR"}


def roster_from_side(side):
    if not isinstance(side, dict):
        return None, None
    mp = side.get("rosterForMatchupPeriod")
    if isinstance(mp, dict) and mp.get("entries"):
        return "rosterForMatchupPeriod", mp
    cur = side.get("rosterForCurrentScoringPeriod")
    if isinstance(cur, dict) and cur.get("entries"):
        return "rosterForCurrentScoringPeriod", cur
    for k, v in side.items():
        if isinstance(k, str) and "roster" in k.lower() and isinstance(v, dict) and v.get("entries"):
            return k, v
    return None, None


def entry_pid(e):
    ppe = e.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    pid = p.get("id")
    if pid is None:
        pid = e.get("playerId")
    return pid


def entry_pts(e):
    ppe = e.get("playerPoolEntry") or {}
    for src in (ppe.get("appliedStatTotal"), e.get("appliedStatTotal")):
        if isinstance(src, (int, float)):
            return round(float(src), 1)
    p = ppe.get("player") or {}
    for st in p.get("stats") or []:
        if st.get("statSourceId") == 0 and isinstance(st.get("appliedTotal"), (int, float)):
            return round(float(st["appliedTotal"]), 1)
    return None


def matchup_period(year, nfl_week):
    """2014–2016: period 14 = NFL 14–15, period 15 = NFL 16–17."""
    if year and year <= 2016:
        if nfl_week <= 13:
            return nfl_week
        if nfl_week in (14, 15):
            return 14
        if nfl_week in (16, 17):
            return 15
    return nfl_week


def extract_rows(d, week, year=None):
    rows = []
    games = list(d.get("schedule") or [])
    period = matchup_period(year, week)
    matched = [g for g in games if g.get("matchupPeriodId") == period]
    if not any(roster_from_side((g or {}).get(side) or {})[1] for g in matched for side in ("home", "away")):
        matched = [g for g in games if any(roster_from_side((g or {}).get(side) or {})[1] for side in ("home", "away"))]
    for g in matched:
        for side in ("home", "away"):
            s = (g or {}).get(side) or {}
            src, roster = roster_from_side(s)
            if not roster:
                continue
            tid = s.get("teamId")
            if tid is None:
                continue
            tid = int(tid)
            for e in roster.get("entries") or []:
                pid = entry_pid(e)
                if pid is None:
                    continue
                slot_id = e.get("lineupSlotId")
                slot = fetch.SLOT.get(slot_id, "?")
                if slot_id in BENCH or slot in BENCH_NAMES:
                    continue
                rec = {"tid": tid, "pid": int(pid), "slot": slot}
                pts = entry_pts(e)
                if pts is not None:
                    rec["pts"] = pts
                rows.append(rec)
    return rows


def main():
    overlay = {}
    empty = []
    for year, weeks in WEEKS.items():
        ymap = {}
        fps = {}
        for week in weeks:
            path = os.path.join(RAW, str(year), f"w{week}.json")
            if not os.path.exists(path):
                empty.append(f"{year} W{week} missing-raw")
                continue
            d = json.load(open(path))
            rows = extract_rows(d, week, year)
            if not rows:
                empty.append(f"{year} W{week} empty")
                continue
            fps[week] = frozenset((r["tid"], r["pid"], r["slot"]) for r in rows)
            for r in rows:
                rec = {"tid": r["tid"], "slot": r["slot"]}
                if "pts" in r:
                    rec["pts"] = r["pts"]
                ymap.setdefault(str(r["pid"]), {})[str(week)] = rec
        if len(fps) >= 8 and len(set(fps.values())) == 1:
            print(f"GUARD {year}: identical starter set every week — not publishing")
            ymap = {}
        overlay[str(year)] = ymap
        n_pw = sum(len(w) for w in ymap.values())
        print(f"  {year}: {len(fps)} weeks, {len(ymap)} players, {n_pw} player-weeks")
    dest = os.path.join(SITE, "pre2018_starts.json")
    with open(dest, "w") as f:
        json.dump(overlay, f, indent=2, sort_keys=True)
        f.write("\n")
    print("empty/missing:", empty or "none")
    print("wrote", dest)


if __name__ == "__main__":
    main()
