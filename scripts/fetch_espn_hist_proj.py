#!/usr/bin/env python3
"""Fetch raw ESPN mMatchup weeks for historical weekly projections.

Writes data/box_raw/{year}/w{n}.json only. Does not touch data/box_YYYY.json.
Reuses fetch.py cookies / league id. Rate-limits. Resumes existing dumps.
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
YEARS = list(range(2018, 2025))  # 2018-2024
WEEKS = list(range(1, 18))
SLEEP_S = 0.35
TAYLOR = 4242335
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}


def dest(year, week):
    return os.path.join(RAW, str(year), f"w{week}.json")


def usable(path):
    try:
        d = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(d, dict) and "schedule" in d


def count_proj(d, week):
    n = 0
    n_pos = 0
    taylor = None
    sample = None
    for g in d.get("schedule") or []:
        if g.get("matchupPeriodId") not in (None, week):
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
                src1 = src0 = None
                for st in p.get("stats") or []:
                    if st.get("scoringPeriodId") != week:
                        continue
                    if st.get("statSourceId") == 1:
                        src1 = st
                    elif st.get("statSourceId") == 0:
                        src0 = st
                if src1 is not None and src1.get("appliedTotal") is not None:
                    n += 1
                    tot = src1.get("appliedTotal")
                    if isinstance(tot, (int, float)) and tot > 0:
                        n_pos += 1
                        if sample is None:
                            sample = {
                                "name": p.get("fullName"),
                                "pid": pid,
                                "pos": POS.get(p.get("defaultPositionId"), "?"),
                                "actual": (src0 or {}).get("appliedTotal"),
                                "proj": tot,
                            }
                if pid == TAYLOR:
                    taylor = {
                        "name": p.get("fullName"),
                        "pid": pid,
                        "actual": (src0 or {}).get("appliedTotal") if src0 else None,
                        "proj": (src1 or {}).get("appliedTotal") if src1 else None,
                    }
    return n, n_pos, taylor, sample


def probe(year=2024, week=1):
    url = fetch.url_for(year, ["mMatchup", "mMatchupScore"], f"&scoringPeriodId={week}")
    print(f"PROBE year={year} week={week}")
    print("url_host_path=", url.split("?")[0])
    print("has_league_id=", str(fetch.LEAGUE) in url)
    print("has_cookie=", bool(fetch.COOKIE) and "espn_s2=" in fetch.COOKIE)
    d = fetch.get(url)
    if not isinstance(d, dict):
        print("PROBE_EMPTY: fetch returned", type(d).__name__)
        return False, None
    n, n_pos, taylor, sample = count_proj(d, week)
    print("seasonId=", d.get("seasonId"), "scoringPeriodId=", d.get("scoringPeriodId"))
    print(f"weekly_proj_rows={n} proj>0={n_pos}")
    if taylor:
        print(f"TAYLOR actual={taylor["actual"]} proj={taylor["proj"]}")
    elif sample:
        print(f"SAMPLE {sample["name"]} ({sample["pos"]}) actual={sample["actual"]} proj={sample["proj"]}")
    ok = n_pos >= 5
    print("PROBE_OK" if ok else "PROBE_EMPTY: ESPN no longer has historical weekly proj")
    return ok, d


def fetch_week(year, week):
    path = dest(year, week)
    if usable(path):
        return "skip", path, None
    url = fetch.url_for(year, ["mMatchup", "mMatchupScore"], f"&scoringPeriodId={week}")
    d = fetch.get(url)
    if not isinstance(d, dict):
        return "fail", path, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    return "ok", path, d


def main():
    args = sys.argv[1:]
    if "--probe-only" in args:
        ok, _ = probe()
        return 0 if ok else 2

    print("auth league=", fetch.LEAGUE, "cookie_present=", bool(fetch.COOKIE))
    ok, probed = probe()
    if not ok:
        print("STOP: not fetching 7 seasons of empty payloads")
        return 2

    # keep the probe payload
    path = dest(2024, 1)
    if probed is not None and not usable(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(probed, f, separators=(",", ":"))
            f.write("\n")
        print("wrote probe payload", path)

    fetched = skipped = failed = 0
    for year in YEARS:
        for week in WEEKS:
            status, path, d = fetch_week(year, week)
            if status == "skip":
                skipped += 1
                print(f"  {year} W{week}: skip (exists)")
            elif status == "ok":
                fetched += 1
                n, n_pos, _, _ = count_proj(d, week)
                print(f"  {year} W{week}: wrote {os.path.getsize(path)} bytes  proj_rows={n} proj>0={n_pos}")
            else:
                failed += 1
                print(f"  {year} W{week}: FAIL")
            time.sleep(SLEEP_S)
    print(f"done fetched={fetched} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
