#!/usr/bin/env python3
"""Export v_started_vs_nfl data for the TanStack lab page.

This demonstrates the AFFL ⋈ NFL join: started fantasy points paired with
NFL EPA, stats, and cap hit via gsis_id.
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_AFFL = os.path.join(HERE, 'affl.db')
DB_NFL = os.path.join(HERE, 'nfl.db')
OUT = os.path.join(HERE, 'lab', 'public', 'started_vs_nfl.json')

def export():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    con = sqlite3.connect(DB_AFFL)
    con.row_factory = sqlite3.Row
    
    # Attach NFL database
    con.execute(f"ATTACH DATABASE '{DB_NFL}' AS nfl")
    
    # Query the join view
    rows = con.execute("""
        SELECT season, week, team_name, member_id, player_name, position,
               ROUND(fantasy_points, 1) AS fantasy_points,
               ROUND(nfl_epa, 2) AS nfl_epa,
               ROUND(pass_yards, 0) AS pass_yards,
               pass_tds,
               ROUND(rush_yards, 0) AS rush_yards,
               rush_tds,
               receptions,
               ROUND(rec_yards, 0) AS rec_yards,
               rec_tds,
               targets,
               ROUND(cap_hit / 1000000.0, 2) AS cap_hit_m,
               nfl_team
        FROM v_started_vs_nfl
        WHERE fantasy_points > 0
        ORDER BY season DESC, week DESC, fantasy_points DESC
    """).fetchall()
    
    data = [dict(row) for row in rows]
    
    with open(OUT, 'w') as f:
        json.dump(data, f)
    
    print(f'Exported {len(data):,} started player-weeks to {OUT}')
    print(f'  Seasons: {min(r["season"] for r in data)} – {max(r["season"] for r in data)}')
    print(f'  Positions: {", ".join(sorted(set(r["position"] for r in data if r["position"])))}')
    
    # Summary stats
    with_epa = sum(1 for r in data if r['nfl_epa'] is not None)
    with_cap = sum(1 for r in data if r['cap_hit_m'] is not None)
    print(f'  With EPA: {with_epa:,} ({with_epa*100/len(data):.1f}%)')
    print(f'  With cap data: {with_cap:,} ({with_cap*100/len(data):.1f}%)')

if __name__ == '__main__':
    export()
