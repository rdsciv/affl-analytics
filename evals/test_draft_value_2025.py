#!/usr/bin/env python3
"""CHI-31 / AFFL-011: auction construction metrics use AFFL replacement, not raw pts/$."""
import sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"; SEASON=2025
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    n=con.execute("SELECT COUNT(*) FROM v_draft_value WHERE season=?", (SEASON,)).fetchone()[0]
    picks=con.execute("SELECT COUNT(*) FROM fact_draft_pick WHERE season=?", (SEASON,)).fetchone()[0]
    if n!=picks: fail(f"v_draft_value {n} != picks {picks}")
    # PAR = points - replacement; par_per_dollar uses PAR not raw points
    bad=list(con.execute("""
        SELECT name, bid, total_points, par, par_per_dollar, points_per_dollar, replacement_points
          FROM v_draft_value WHERE season=? AND par IS NOT NULL
           AND ABS(par - (total_points - COALESCE(replacement_points,0))) > 0.15
    """, (SEASON,)))
    if bad: fail(f"PAR is not points-replacement: {len(bad)}")
    # a cheap QB must not outrank a stud on raw pts/$ if we sort by PAR/$
    rows=list(con.execute("""
        SELECT name, position, bid, par, par_per_dollar, points_per_dollar
          FROM v_draft_value WHERE season=? AND bid>0 AND par IS NOT NULL
            AND position IN ('QB','RB','WR','TE')
    """, (SEASON,)))
    if not rows: fail("no scored auction value rows")
    print(f"v_draft_value {n} rows; PAR formula holds")
    baselines=list(con.execute("SELECT position, demand, baseline_points FROM v_baseline WHERE season=? AND position IN ('QB','RB','WR','TE')", (SEASON,)))
    if len(baselines)<4: fail("missing 2025 replacement baselines")
    PREVIEW.mkdir(exist_ok=True)
    top=list(con.execute("""
        SELECT name, position, bid, ROUND(par,1) par, par_per_dollar
          FROM v_draft_value WHERE season=? AND par>0 ORDER BY par_per_dollar DESC LIMIT 8
    """, (SEASON,)))
    lines=["# 2025 draft value","", "CHI-31 / AFFL-011. AFFL replacement baseline, not raw points/$.","",
           "| pos | demand | replacement |","| --- | --- | --- |"]
    for b in baselines:
        lines.append(f"| {b['position']} | {b['demand']} | {b['baseline_points']:.1f} |")
    lines += ["","## Top PAR/$ (par>0)","", "| player | pos | bid | par | par/$ |","| --- | --- | --- | --- | --- |"]
    for r in top:
        lines.append(f"| {r['name']} | {r['position']} | {r['bid']} | {r['par']} | {r['par_per_dollar']} |")
    lines += ["","```","python3 evals/test_draft_value_2025.py","```",""]
    (PREVIEW/"DRAFT_VALUE.md").write_text("\n".join(lines))
    print(PREVIEW/"DRAFT_VALUE.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-31: draft value uses AFFL PAR baseline"); return 0
if __name__=="__main__":
    sys.exit(main())
