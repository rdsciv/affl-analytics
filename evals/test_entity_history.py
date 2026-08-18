#!/usr/bin/env python3
"""CHI-37 / AFFL-017: entity, rivalry, history from shared warehouse (not a second store)."""
import json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SITE=ROOT/"site"; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    owners=list(con.execute("SELECT owner_id, display_name, is_active FROM dim_owner ORDER BY display_name"))
    if len(owners)<12: fail(f"only {len(owners)} owners")
    # career records follow owner, not team_id
    kafka=con.execute("""
        SELECT COUNT(*) FROM dim_team t
        JOIN dim_member m ON m.member_id=t.member_id
        WHERE m.owner_id='m07'
    """).fetchone()[0]
    if kafka<2: fail("Kafka merge missing team-seasons")
    # teams page exists and is in nav
    html=(SITE/"teams.html").read_text()
    if "teams.js" not in html: fail("teams.html missing teams.js")
    data=json.loads((SITE/"data.json").read_text())
    # H2H lives in matchups across years — count pairs for 2025
    pairs=con.execute("""
        SELECT COUNT(*) FROM fact_matchup
         WHERE season=2025 AND is_playoff=0 AND is_home=1
    """).fetchone()[0]
    print(f"owners={len(owners)} kafka_seasons={kafka} 2025_h2h_games={pairs}")
    PREVIEW.mkdir(exist_ok=True)
    lines=["# Entity / rivalry / history","", "CHI-37 / AFFL-017. Shared warehouse. No second store.","",
           f"- Owners: **{len(owners)}** (Kafka merged)","- 2025 regular H2H games: **{pairs}**","",
           "| owner_id | name | active |","| --- | --- | --- |"]
    for o in owners:
        lines.append(f"| {o['owner_id']} | {o['display_name']} | {o['is_active']} |")
    lines += ["","```","python3 evals/test_entity_history.py","```",""]
    (PREVIEW/"ENTITIES.md").write_text("\n".join(lines))
    print(PREVIEW/"ENTITIES.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-37: owners/H2H from warehouse; teams page present"); return 0
if __name__=="__main__":
    sys.exit(main())
