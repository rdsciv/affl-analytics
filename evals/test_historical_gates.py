#!/usr/bin/env python3
"""CHI-36 / AFFL-016: repeatable historical intake and completeness gates.

leeg + ESPN + Auction Lab are inputs. Missing stays missing.
"""
import sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    seasons=list(con.execute("SELECT * FROM dim_season ORDER BY season"))
    if [s["season"] for s in seasons]!=list(range(2014,2026)):
        fail(f"seasons {[s['season'] for s in seasons]} != 2014-2025")
    rows=[]
    for s in seasons:
        y=s["season"]
        mu=con.execute("SELECT COUNT(*) FROM fact_matchup WHERE season=?", (y,)).fetchone()[0]
        rw=con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=?", (y,)).fetchone()[0]
        dp=con.execute("SELECT COUNT(*) FROM fact_draft_pick WHERE season=?", (y,)).fetchone()[0]
        tx=con.execute("SELECT COUNT(*) FROM fact_transaction WHERE season=?", (y,)).fetchone()[0]
        expect_rw = rw>0 if s["has_rosters"] else rw==0
        expect_tx = tx>0 if s["has_tx"] else tx==0
        if not expect_rw: fail(f"{y} has_rosters={s['has_rosters']} but roster_weeks={rw}")
        if not expect_tx: fail(f"{y} has_tx={s['has_tx']} but tx={tx}")
        if mu<100: fail(f"{y} matchups {mu} too low")
        if dp<100: fail(f"{y} draft {dp} too low")
        rows.append((y,s["team_count"],s["reg_weeks"],s["auction_draft"],s["has_rosters"],s["has_tx"],mu,rw,dp,tx))
    print(f"completeness gates: {len(rows)} seasons")
    PREVIEW.mkdir(exist_ok=True)
    lines=["# Historical completeness gates","", "CHI-36 / AFFL-016. Flags on `dim_season` must match actual counts. Missing stays missing.","",
           "| season | teams | reg_weeks | auction | rosters | tx | matchups | roster_weeks | draft | transactions |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| "+" | ".join(str(x) for x in r)+" |")
    lines += ["","```","python3 evals/test_historical_gates.py","```",""]
    (PREVIEW/"HISTORY_GATES.md").write_text("\n".join(lines))
    print(PREVIEW/"HISTORY_GATES.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-36: season completeness flags match warehouse counts"); return 0
if __name__=="__main__":
    sys.exit(main())
