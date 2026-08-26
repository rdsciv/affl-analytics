#!/usr/bin/env python3
"""Fetch 2014–2017 ESPN mMatchup weeks and extract STARTER-only overlays.

Writes:
  data/box_raw/{year}/w{n}.json   raw payloads only (never data/box_YYYY.json)
  site/pre2018_starts.json        {year: {pid: {week: {tid, slot, pts}}}}

Reuses fetch.py auth (league 51418). Rate-limits. Resumes existing dumps.
Does not invent weekly starts: only rows ESPN actually returned, non-BN/IR.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import fetch  # noqa: E402

RAW = os.path.join(ROOT, "data", "box_raw")
SITE = os.path.join(ROOT, "site")
SLEEP_S = 0.45

# Confirmed from league_{year}.json schedule matchupPeriodIds.
# settings status.finalScoringPeriod is 17 for 2014–16 files (current-league
# status leaked into those dumps) but schedule only has periods 1–15.
# 2017 status.finalScoringPeriod=16 matches schedule 1–16.
WEEKS = {
    2014: range(1, 18),
    2015: range(1, 18),
    2016: range(1, 18),
    2017: range(1, 17),
}
BENCH = {20, 21}  # BN, IR
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


def roster_from_side(side):
    """Prefer rosterForMatchupPeriod; else any roster* dict that has rows."""
    if not isinstance(side, dict):
        return None, None
    mp = side.get("rosterForMatchupPeriod")
    if isinstance(mp, dict) and mp.get("entries"):
        return "rosterForMatchupPeriod", mp
    cur = side.get("rosterForCurrentScoringPeriod")
    if isinstance(cur, dict) and cur.get("entries"):
        return "rosterForCurrentScoringPeriod", cur
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


def is_bench(slot_id, slot_name):
    if slot_id in BENCH:
        return True
    if slot_name in BENCH_NAMES:
        return True
    return False


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


def extract_rows(d, week):
    """Starter rows for this scoring period. Does not invent benches."""
    rows = []
    games = list(d.get("schedule") or [])
    year = int(d.get("seasonId") or 0) or None
    period = matchup_period(year, week)
    matched = [g for g in games if g.get("matchupPeriodId") == period]
    used_fallback = False
    if not any(roster_from_side((g or {}).get(side) or {})[1] for g in matched for side in ("home", "away")):
        # 2-week playoff or ESPN omitted matchupPeriodId — use any side with rows
        alt = []
        for g in games:
            if any(roster_from_side((g or {}).get(side) or {})[1] for side in ("home", "away")):
                alt.append(g)
        if alt:
            matched = alt
            used_fallback = True
    sources = set()
    for g in matched:
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
                if is_bench(slot_id, slot):
                    continue
                rec = {
                    "year": int(d.get("seasonId") or 0) or None,
                    "week": week,
                    "tid": tid,
                    "pid": int(pid),
                    "slot": slot,
                }
                pts = entry_pts(e)
                if pts is not None:
                    rec["pts"] = pts
                rows.append(rec)
    return rows, used_fallback, sorted(sources)


def count_starters(d, week):
    rows, fallback, sources = extract_rows(d, week)
    return len(rows), fallback, sources


def fetch_week(year, week):
    path = dest(year, week)
    if usable(path):
        return "skip", path, json.load(open(path))
    url = fetch.url_for(year, ["mMatchup", "mMatchupScore"], f"&scoringPeriodId={week}")
    d = fetch.get(url)
    d = unwrap(d)
    if not isinstance(d, dict):
        return "fail", path, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    return "ok", path, d


def probe_2014_w1():
    url = fetch.url_for(2014, ["mMatchup", "mMatchupScore"], "&scoringPeriodId=1")
    print("PROBE 2014 W1")
    print("url_host_path=", url.split("?")[0])
    print("has_league_id=", str(fetch.LEAGUE) in url)
    print("has_cookie=", bool(fetch.COOKIE) and "espn_s2=" in fetch.COOKIE and "SWID=" in fetch.COOKIE)
    d = unwrap(fetch.get(url))
    if not isinstance(d, dict):
        print("PROBE_EMPTY: fetch returned", type(d).__name__)
        return False, None
    n, fallback, sources = count_starters(d, 1)
    print("seasonId=", d.get("seasonId"), "scoringPeriodId=", d.get("scoringPeriodId"))
    print("n_schedule=", len(d.get("schedule") or []))
    print(f"starter_rows={n} fallback={fallback} sources={sources}")
    ok = n >= 20
    print("PROBE_OK" if ok else "PROBE_EMPTY: not enough starter rows")
    return ok, d


def week_fingerprint(rows):
    return frozenset((r["tid"], r["pid"], r["slot"]) for r in rows)


def build_overlay(log):
    out = {}
    empty = []
    fetched_weeks = []
    per_year_weeks = {}
    fingerprints = defaultdict(dict)
    for year, weeks in WEEKS.items():
        ymap = {}
        weeks_with = 0
        for week in weeks:
            path = dest(year, week)
            if not usable(path):
                empty.append(f"{year} W{week} missing-raw")
                log.append((year, week, "missing", 0))
                continue
            d = json.load(open(path))
            rows, fallback, sources = extract_rows(d, week)
            if not rows:
                empty.append(f"{year} W{week} empty")
                log.append((year, week, "empty", 0))
                continue
            weeks_with += 1
            fetched_weeks.append(f"{year} W{week}")
            fingerprints[year][week] = week_fingerprint(rows)
            log.append((year, week, "ok", len(rows)))
            for r in rows:
                pid = str(r["pid"])
                rec = {"tid": r["tid"], "slot": r["slot"]}
                if "pts" in r:
                    rec["pts"] = r["pts"]
                ymap.setdefault(pid, {})[str(week)] = rec
        out[str(year)] = ymap
        per_year_weeks[year] = weeks_with

    # identical-all-weeks guard: do not publish a repeated snapshot as weekly starts
    for year, fps in fingerprints.items():
        uniq = set(fps.values())
        if len(fps) >= 8 and len(uniq) == 1:
            print(f"GUARD {year}: all {len(fps)} weeks have identical starter sets — not publishing (would invent weekly starts)")
            out[str(year)] = {}
            per_year_weeks[year] = 0
    return out, empty, per_year_weeks


def main():
    args = sys.argv[1:]
    extract_only = "--extract-only" in args
    print("auth league=", fetch.LEAGUE, "cookie_present=", bool(fetch.COOKIE))
    print("weeks 2014-16=1-17 (NFL; period 15 = W16-17) 2017=1-16")

    if not extract_only:
        ok, probed = probe_2014_w1()
        if not ok:
            print("STOP: 2014 W1 has no starter rows; not fetching empty seasons")
            return 2
        path = dest(2014, 1)
        if probed is not None and not usable(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(probed, f, separators=(",", ":"))
                f.write("\n")
            print("wrote probe payload", path)

        fetched = skipped = failed = 0
        for year, weeks in WEEKS.items():
            for week in weeks:
                status, path, d = fetch_week(year, week)
                if status == "skip":
                    skipped += 1
                    n, _, _ = count_starters(d, week)
                    print(f"  {year} W{week}: skip (exists) starters={n}")
                elif status == "ok":
                    fetched += 1
                    n, fallback, sources = count_starters(d, week)
                    print(f"  {year} W{week}: wrote {os.path.getsize(path)} bytes starters={n} fallback={fallback} src={sources}")
                else:
                    failed += 1
                    print(f"  {year} W{week}: FAIL/empty-response")
                time.sleep(SLEEP_S)
        print(f"fetch done fetched={fetched} skipped={skipped} failed={failed}")

    log = []
    overlay, empty, per_year_weeks = build_overlay(log)
    dest_json = os.path.join(SITE, "pre2018_starts.json")
    with open(dest_json, "w") as f:
        json.dump(overlay, f, indent=2, sort_keys=True)
        f.write("\n")

    print("==== extract ====")
    for year in WEEKS:
        ymap = overlay.get(str(year)) or {}
        n_pw = sum(len(w) for w in ymap.values())
        n_pl = len(ymap)
        print(f"  {year}: {per_year_weeks.get(year, 0)} weeks with starters, {n_pl} players, {n_pw} player-weeks")
    if empty:
        print("empty/missing weeks:")
        for e in empty:
            print(" ", e)
    else:
        print("empty/missing weeks: none")
    ben = ((overlay.get("2014") or {}).get("5536") or {})
    if ben:
        print("2014 pid 5536 start weeks:")
        for wk in sorted(ben, key=lambda x: int(x)):
            rec = ben[wk]
            print(f"  W{wk} tid={rec.get('tid')} slot={rec.get('slot')} pts={rec.get('pts')}")
    else:
        print("2014 pid 5536: no start rows (backup / not in starter payloads)")
    print("wrote", dest_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
