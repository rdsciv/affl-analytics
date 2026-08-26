#!/usr/bin/env python3
"""Fetch 2014–2016 NFL weeks 16 and 17 (championship half) and merge starts.

Writes:
  data/box_raw/{year}/w16.json
  data/box_raw/{year}/w17.json
Merges new starter rows into site/pre2018_starts.json (does not rewrite other weeks).
Does not touch league_*.json or box_YYYY.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import fetch  # noqa: E402

RAW = os.path.join(ROOT, "data", "box_raw")
SITE = os.path.join(ROOT, "site")
SLEEP_S = 0.45
YEARS = (2014, 2015, 2016)
WEEKS = (16, 17)
BENCH = {20, 21}
BENCH_NAMES = {"BN", "IR"}


def dest(year, week):
    return os.path.join(RAW, str(year), f"w{week}.json")


def usable(path):
    try:
        d = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(d, dict) and "schedule" in d


def unwrap(d):
    return d[0] if isinstance(d, list) and d else d


def matchup_period(year, nfl_week):
    """2014–2016: period 14 = NFL 14–15, period 15 = NFL 16–17."""
    if year <= 2016:
        if nfl_week <= 13:
            return nfl_week
        if nfl_week in (14, 15):
            return 14
        if nfl_week in (16, 17):
            return 15
    return nfl_week


def roster_from_side(side):
    if not isinstance(side, dict):
        return None, None
    # Prefer current scoring period (true NFL week) when ESPN still has it.
    cur = side.get("rosterForCurrentScoringPeriod")
    if isinstance(cur, dict) and cur.get("entries"):
        return "rosterForCurrentScoringPeriod", cur
    mp = side.get("rosterForMatchupPeriod")
    if isinstance(mp, dict) and mp.get("entries"):
        return "rosterForMatchupPeriod", mp
    for k, v in side.items():
        if not isinstance(k, str) or "roster" not in k.lower():
            continue
        if isinstance(v, dict) and v.get("entries"):
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


def extract_rows(d, year, week):
    period = matchup_period(year, week)
    rows = []
    sources = set()
    for g in d.get("schedule") or []:
        if g.get("matchupPeriodId") != period:
            continue
        for side in ("home", "away"):
            s = (g or {}).get(side) or {}
            src, roster = roster_from_side(s)
            if not roster:
                continue
            sources.add(src)
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
                rec = {"tid": tid, "slot": slot, "pid": int(pid)}
                pts = entry_pts(e)
                if pts is not None:
                    rec["pts"] = pts
                rows.append(rec)
    return rows, sorted(sources)


def fetch_week(year, week):
    path = dest(year, week)
    if usable(path):
        return "skip", path, json.load(open(path))
    url = fetch.url_for(year, ["mMatchup", "mMatchupScore"], f"&scoringPeriodId={week}")
    d = unwrap(fetch.get(url))
    if not isinstance(d, dict):
        return "fail", path, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    return "ok", path, d


def merge_starts(overlay, year, week, rows):
    ymap = overlay.setdefault(str(year), {})
    added = 0
    for r in rows:
        pid = str(r["pid"])
        rec = {"tid": r["tid"], "slot": r["slot"]}
        if "pts" in r:
            rec["pts"] = r["pts"]
        bucket = ymap.setdefault(pid, {})
        if str(week) not in bucket:
            added += 1
        bucket[str(week)] = rec
    return added


def main():
    print("auth league=", fetch.LEAGUE, "cookie_present=", bool(fetch.COOKIE))
    print("fetch 2014-2016 NFL weeks 16 and 17 only (championship half)")

    dest_json = os.path.join(SITE, "pre2018_starts.json")
    overlay = {}
    if os.path.exists(dest_json):
        overlay = json.load(open(dest_json))
        if not isinstance(overlay, dict):
            overlay = {}

    empty = []
    for year in YEARS:
        for week in WEEKS:
            status, path, d = fetch_week(year, week)
            if status == "fail" or not isinstance(d, dict):
                print(f"  {year} W{week}: FAIL/empty-response")
                empty.append(f"{year} W{week} empty-response")
                time.sleep(SLEEP_S)
                continue
            rows, sources = extract_rows(d, year, week)
            n_bytes = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"  {year} W{week}: {status} bytes={n_bytes} starters={len(rows)} src={sources}")
            if not rows:
                empty.append(f"{year} W{week} empty")
            else:
                added = merge_starts(overlay, year, week, rows)
                print(f"    merged {added} new player-weeks (total rows this week {len(rows)})")
            time.sleep(SLEEP_S)

    with open(dest_json, "w") as f:
        json.dump(overlay, f, indent=2, sort_keys=True)
        f.write("\n")

    print("==== 2014 week coverage after merge ====")
    y2014 = overlay.get("2014") or {}
    weeks = set()
    for rec in y2014.values():
        if isinstance(rec, dict):
            weeks.update(k for k in rec if str(k).isdigit())
    print("2014 weeks:", ", ".join(f"W{w}" for w in sorted(weeks, key=int)))
    for wk in ("16", "17"):
        n = sum(1 for rec in y2014.values() if isinstance(rec, dict) and wk in rec)
        print(f"  2014 W{wk} starter rows: {n}")
    feel = []
    for pid, rec in y2014.items():
        if not isinstance(rec, dict):
            continue
        for wk in ("16", "17"):
            row = rec.get(wk)
            if row and row.get("tid") == 7:
                feel.append((pid, wk, row))
    print(f"2014 Feelers (tid 7) W16/W17 start rows: {len(feel)}")
    if empty:
        print("empty/missing weeks:")
        for e in empty:
            print(" ", e)
    else:
        print("empty/missing weeks: none")
    print("wrote", dest_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
