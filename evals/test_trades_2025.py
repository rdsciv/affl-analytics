#!/usr/bin/env python3
"""CHI-35 / AFFL-015: trade ledger. Reconstructed from roster movement; keep distinct from verified tx."""
import sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    trades=con.execute("SELECT COUNT(*) FROM fact_trade WHERE season=2025").fetchone()[0]
    items=con.execute("SELECT COUNT(*) FROM fact_trade_item i JOIN fact_trade t ON t.trade_id=i.trade_id WHERE t.season=2025").fetchone()[0]
    print(f"2025 trades={trades} items={items}")
    if trades<1: fail("no 2025 trades")
    if items<trades: fail("fewer items than trades")
    # every item has two distinct teams
    bad=con.execute("""
        SELECT COUNT(*) FROM fact_trade_item i JOIN fact_trade t ON t.trade_id=i.trade_id
         WHERE t.season=2025 AND (i.from_team_id=i.to_team_id OR i.player_id IS NULL)
    """).fetchone()[0]
    if bad: fail(f"{bad} malformed trade items")
    # do not require tx-feed equality — trades are reconstructed
    PREVIEW.mkdir(exist_ok=True)
    sample=list(con.execute("""
        SELECT tr.week, pf.name AS frm, pt.name AS too, p.name AS player
          FROM fact_trade_item i
          JOIN fact_trade tr ON tr.trade_id=i.trade_id
          JOIN dim_team pf ON pf.season=tr.season AND pf.team_id=i.from_team_id
          JOIN dim_team pt ON pt.season=tr.season AND pt.team_id=i.to_team_id
          JOIN dim_player p ON p.player_id=i.player_id
         WHERE tr.season=2025 ORDER BY tr.week, tr.trade_id LIMIT 12
    """))
    lines=["# 2025 trade ledger","",
           "CHI-35 / AFFL-015. `fact_trade` is reconstructed from roster movement, not the ESPN tx feed. Labeled reconstructed.","",
           f"- Trades: **{trades}**","- Items: **{items}**","",
           "| week | from | to | player |","| --- | --- | --- | --- |"]
    for r in sample:
        lines.append(f"| {r['week']} | {r['frm']} | {r['too']} | {r['player']} |")
    lines += ["","```","python3 evals/test_trades_2025.py","```",""]
    (PREVIEW/"TRADES.md").write_text("\n".join(lines))
    print(PREVIEW/"TRADES.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-35: 2025 trade ledger present; reconstructed, not invented"); return 0
if __name__=="__main__":
    sys.exit(main())
