#!/usr/bin/env python3
"""CHI-30 / AFFL-010: 2025 auction purchases and budget.

fact_draft_pick already holds the ESPN bids. Do not infer missing prices.
"""
import json, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DB, PREVIEW, SEASON = ROOT/"affl.db", ROOT/"preview", 2025
BUDGET = 200
fails=[]
fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    n, spent, keepers, zero, nullp = con.execute(
        "SELECT COUNT(*), SUM(bid), SUM(is_keeper), SUM(CASE WHEN bid=0 THEN 1 ELSE 0 END), SUM(CASE WHEN player_id IS NULL THEN 1 ELSE 0 END) FROM fact_draft_pick WHERE season=?",
        (SEASON,)).fetchone()
    teams=list(con.execute("""
        SELECT t.team_id, t.name, COUNT(d.overall) n, COALESCE(SUM(d.bid),0) spent
          FROM dim_team t LEFT JOIN fact_draft_pick d ON d.season=t.season AND d.team_id=t.team_id
         WHERE t.season=? GROUP BY t.team_id ORDER BY t.name""", (SEASON,)))
    print(f"2025 picks={n} spent={spent} keepers={keepers} zero_bid={zero} null_player={nullp}")
    if n!=192: fail(f"2025 picks {n} != 192")
    if zero: fail(f"{zero} zero bids — do not treat as inferred $0 fills unless ESPN stored 0")
    if nullp: fail(f"{nullp} picks with no player")
    if keepers: fail(f"keepers={keepers} unexpected for 2025")
    over=[r for r in teams if r["spent"]>BUDGET]
    if over: fail(f"over budget: {over}")
    short=[r for r in teams if r["n"]!=16]
    if short: fail(f"not 16 picks: {[(r['name'],r['n']) for r in short]}")
    leftover=[(r["name"], r["spent"]) for r in teams if r["spent"]<BUDGET]
    print("leftover (real, not inferred):", leftover)
    league=json.loads((ROOT/"data/league_2025.json").read_text())
    if isinstance(league, list): league=league[0]
    bud=((league.get("settings") or {}).get("draftSettings") or {}).get("auctionBudget")
    if bud!=BUDGET: fail(f"ESPN auctionBudget {bud} != {BUDGET}")
    PREVIEW.mkdir(exist_ok=True)
    lines=["# 2025 auction","", "CHI-30 / AFFL-010. ESPN bids in `fact_draft_pick`. No inferred prices.","",
           f"- Picks: **{n}** (12 × 16)","- League budget: **${BUDGET}**","- Spent: **${spent}**",
           f"- Leftover: {leftover or 'none'}","",
           "| team | picks | spent | leftover |","| --- | --- | --- | --- |"]
    for r in teams:
        lines.append(f"| {r['name']} | {r['n']} | {r['spent']} | {BUDGET-r['spent']} |")
    lines += ["","```","python3 evals/test_auction_2025.py","```",""]
    (PREVIEW/"AUCTION.md").write_text("\n".join(lines))
    print(PREVIEW/"AUCTION.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-30: 2025 auction bids+budget reconcile; leftover not invented"); return 0
if __name__=="__main__":
    sys.exit(main())
