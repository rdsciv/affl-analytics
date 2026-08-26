#!/usr/bin/env python3
"""Probe one historical ESPN week for weekly projected appliedTotal."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import fetch  # noqa: E402

TAYLOR = 4242335
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
YEAR = 2024
WEEK = 1


def main():
    url = fetch.url_for(YEAR, ["mMatchup", "mMatchupScore"], f"&scoringPeriodId={WEEK}")
    print(f"PROBE year={YEAR} week={WEEK}")
    print("url_host_path=", url.split("?")[0])
    print("has_league_id=", str(fetch.LEAGUE) in url)
    print("has_cookie=", bool(fetch.COOKIE) and "espn_s2=" in fetch.COOKIE and "SWID=" in fetch.COOKIE)

    d = fetch.get(url)
    if d is None:
        print("RESULT: fetch returned None (404 or empty)")
        return 0
    if not isinstance(d, dict):
        print("RESULT: unexpected type", type(d))
        return 0

    print("top_keys=", sorted(d.keys()))
    print("seasonId=", d.get("seasonId"))
    print("scoringPeriodId=", d.get("scoringPeriodId"))
    print("n_schedule=", len(d.get("schedule") or []))

    n_entries = 0
    n_with_stats = 0
    n_src1_week = 0
    n_src1_week_pos = 0
    n_src0_week = 0
    src1_pos_examples = []
    rbs = []
    taylor = None

    for g in d.get("schedule") or []:
        week = g.get("matchupPeriodId")
        if week not in (None, WEEK):
            continue
        for side in ("home", "away"):
            s = g.get(side) or {}
            roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
            if not roster:
                continue
            for e in roster.get("entries") or []:
                n_entries += 1
                ppe = e.get("playerPoolEntry") or {}
                p = ppe.get("player") or {}
                pid = p.get("id") if p.get("id") is not None else e.get("playerId")
                stats = p.get("stats") or []
                if stats:
                    n_with_stats += 1
                src1 = None
                src0 = None
                src1_rows = []
                summaries = []
                for st in stats:
                    rec = {
                        "statSourceId": st.get("statSourceId"),
                        "scoringPeriodId": st.get("scoringPeriodId"),
                        "statSplitTypeId": st.get("statSplitTypeId"),
                        "appliedTotal": st.get("appliedTotal"),
                        "appliedProjectedReal": st.get("appliedProjectedReal"),
                    }
                    summaries.append(rec)
                    if st.get("statSourceId") == 1 and st.get("scoringPeriodId") == WEEK:
                        src1 = st
                        src1_rows.append(rec)
                    if st.get("statSourceId") == 0 and st.get("scoringPeriodId") == WEEK:
                        src0 = st
                if src1 is not None:
                    n_src1_week += 1
                    tot = src1.get("appliedTotal")
                    if isinstance(tot, (int, float)) and tot > 0:
                        n_src1_week_pos += 1
                        if len(src1_pos_examples) < 8:
                            src1_pos_examples.append({
                                "name": p.get("fullName"),
                                "pid": pid,
                                "pos": POS.get(p.get("defaultPositionId"), "?"),
                                "actual": (src0 or {}).get("appliedTotal"),
                                "proj": tot,
                                "split": src1.get("statSplitTypeId"),
                            })
                if src0 is not None:
                    n_src0_week += 1
                info = {
                    "name": p.get("fullName"),
                    "pid": pid,
                    "pos": POS.get(p.get("defaultPositionId"), "?"),
                    "n_stats": len(stats),
                    "src1_week_rows": src1_rows,
                    "actual": (src0 or {}).get("appliedTotal") if src0 else None,
                    "proj": (src1 or {}).get("appliedTotal") if src1 else None,
                    "stat_sources": sorted({st.get("statSourceId") for st in stats}),
                    "stat_periods": sorted({st.get("scoringPeriodId") for st in stats}),
                    "summaries": summaries,
                }
                if pid == TAYLOR:
                    taylor = info
                if p.get("defaultPositionId") == 2:
                    rbs.append(info)

    print("n_roster_entries=", n_entries)
    print("n_with_any_stats=", n_with_stats)
    print("n_with_statSourceId1_week1=", n_src1_week)
    print("n_with_statSourceId1_week1_proj>0=", n_src1_week_pos)
    print("n_with_statSourceId0_week1=", n_src0_week)
    print("n_RBs_on_rosters=", len(rbs))
    print("taylor_found=", taylor is not None)
    if taylor:
        print("TAYLOR name=", taylor["name"], "pid=", taylor["pid"], "pos=", taylor["pos"])
        print("TAYLOR actual=", taylor["actual"], "proj=", taylor["proj"])
        print("TAYLOR n_stats=", taylor["n_stats"], "sources=", taylor["stat_sources"], "periods=", taylor["stat_periods"])
        print("TAYLOR all_stat_summaries=")
        for row in taylor["summaries"]:
            print(" ", row)
    else:
        print("Taylor not on a 2024 W1 roster; showing first 3 RBs:")
        for rb in rbs[:3]:
            print(" RB", rb["name"], "pid=", rb["pid"], "actual=", rb["actual"], "proj=", rb["proj"],
                  "n_stats=", rb["n_stats"], "sources=", rb["stat_sources"], "periods=", rb["stat_periods"])
            print("  src1_week_rows=", rb["src1_week_rows"])

    print("EXAMPLES with proj>0:")
    for ex in src1_pos_examples:
        print(" ", ex)

    if n_src1_week_pos >= 5:
        print("PROBE_OK: historical weekly proj present")
        return 0
    print("PROBE_EMPTY: ESPN no longer has historical weekly proj (or too few >0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
