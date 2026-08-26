#!/usr/bin/env python3
"""CHI-34 / AFFL-014: transactions and ownership stints. Do not invent missing trades."""
import sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    n=con.execute("SELECT COUNT(*) FROM fact_transaction WHERE season=2025").fetchone()[0]
    print(f"2025 transactions={n}")
    if n<1000: fail(f"2025 tx {n} unexpectedly low")
    for y in range(2014,2018):
        k=con.execute("SELECT COUNT(*) FROM fact_transaction WHERE season=?", (y,)).fetchone()[0]
        if k: fail(f"{y} has {k} transactions — unavailable")
    types=list(con.execute("SELECT tx_type, direction, COUNT(*) n FROM fact_transaction WHERE season=2025 GROUP BY 1,2 ORDER BY 1,2"))
    # stints: drafted / traded / waived already in fact_player_week_par
    acq=list(con.execute("SELECT acquisition, COUNT(*) n FROM fact_player_week_par WHERE season=2025 GROUP BY 1"))
    PREVIEW.mkdir(exist_ok=True)
    lines=["# 2025 transactions","", "CHI-34 / AFFL-014. ESPN tx feed 2018+. Pre-2018 unavailable. No invented trades.","",
           f"- 2025 rows: **{n}**","",
           "| type | direction | n |","| --- | --- | --- |"]
    for r in types:
        lines.append(f"| {r['tx_type']} | {r['direction']} | {r['n']} |")
    lines += ["","## Custody stints (acquisition)","", "| acquisition | player-weeks |","| --- | --- |"]
    for r in acq:
        lines.append(f"| {r['acquisition']} | {r['n']} |")
    lines += ["","```","python3 evals/test_transactions_2025.py","```",""]
    (PREVIEW/"TRANSACTIONS.md").write_text("\n".join(lines))
    print(PREVIEW/"TRANSACTIONS.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-34: 2025 tx imported; pre-2018 empty"); return 0
if __name__=="__main__":
    sys.exit(main())
