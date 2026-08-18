#!/usr/bin/env python3
"""Elite Company FP is full-season nflverse AFFL points, not rostered-week ESPN.

v_player_season_any sums fact_roster_week.points only for weeks a player was
on an AFFL roster. Jalen Nailor 2025 was a week-16 FA add (0.0 on the bench)
so the board showed FP 0.0 / xFP 74.1. xFP is reconstructed from every
fact_nfl_week row (rush/rec yard pts + 6*xTD). FP must use that same window.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
SRC = ROOT / "compute_eight.py"
fails = []
fail = lambda m: fails.append(m)

NAILOR = 4382466
MCNICHOLS = 3127586
MIMS = 4686472


def main():
    src = SRC.read_text()
    fn = src.split("def receiving_usage", 1)[-1].split("def _median_weeks", 1)[0]
    if "FROM v_player_season_any" in fn or "fpmap" in fn:
        fail("receiving_usage still joins v_player_season_any for FP")
    if "fact_nfl_week" not in fn:
        fail("receiving_usage no longer reads fact_nfl_week")

    y25 = json.loads((SITE / "years/2025.json").read_text())
    usage = y25.get("receivingUsage") or []
    if not usage:
        fail("2025 receivingUsage empty")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    by_pid = {r.get("pid"): r for r in usage}
    nailor = by_pid.get(NAILOR)
    if not nailor:
        fail("Jalen Nailor missing from 2025 receivingUsage")
    else:
        print(f"Nailor 2025: pid={nailor.get('pid')} fp={nailor.get('fp')} "
              f"xfp={nailor.get('xfp')} wopr={nailor.get('wopr')}")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    expected = {}
    for pid in (NAILOR, MCNICHOLS, MIMS):
        row = con.execute("""
            SELECT p.name,
                   SUM(COALESCE(n.rec_yards,0)) AS recy,
                   SUM(COALESCE(n.rush_yards,0)) AS ry,
                   SUM(COALESCE(n.rec_tds,0)) AS retd,
                   SUM(COALESCE(n.rush_tds,0)) AS rtd,
                   SUM(COALESCE(n.two_pt,0)) AS tp,
                   SUM(COALESCE(n.fumbles_lost,0)) AS fl
              FROM fact_nfl_week n
              JOIN dim_player p ON p.gsis_id = n.gsis_id
             WHERE n.season=2025 AND p.player_id=?""", (pid,)).fetchone()
        exp = (row["ry"] * 0.1 + row["recy"] * 0.1
               + 6.0 * (row["retd"] + row["rtd"])
               + 2.0 * row["tp"] - 2.0 * row["fl"])
        expected[pid] = (row["name"], round(exp, 1))
        print(f"  warehouse {row['name']}: recy={row['recy']} ry={row['ry']} "
              f"td={row['retd']+row['rtd']} tp={row['tp']} fl={row['fl']} "
              f"AFFL={exp:.1f}")

    for pid, label in ((NAILOR, "Nailor"), (MCNICHOLS, "McNichols"), (MIMS, "Mims")):
        row = by_pid.get(pid)
        name, exp = expected[pid]
        if not row:
            fail(f"{label} missing from receivingUsage")
            continue
        fp = row.get("fp")
        if fp is None:
            fail(f"{label} FP is null")
            continue
        if abs(float(fp) - exp) > 0.15:
            fail(f"{label} FP {fp} != full-season AFFL {exp}")
        if pid == NAILOR and float(fp) == 0.0:
            fail("Nailor FP is still 0.0 (rostered-week ESPN join)")
        if pid == MIMS and float(fp) < 0:
            fail(f"Mims FP is still negative rostered-week ESPN ({fp})")

    zeros = [r for r in usage
             if (r.get("fp") == 0 or r.get("fp") == 0.0)
             and (r.get("xfp") or 0) > 20]
    if zeros:
        names = ", ".join(r.get("name") or "?" for r in zeros)
        fail(f"{len(zeros)} receivingUsage rows have FP==0 and xFP>20: {names}")

    luck = y25.get("luckCard") or []
    feel = next((r for r in luck if r.get("tid") == 7), None)
    if not feel:
        fail("Feelers tid 7 missing from 2025 luckCard")
    else:
        print(f"Feelers 2025 luckCard tid=7 actualW={feel.get('actualW')} "
              f"pf={feel.get('pf')}")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
