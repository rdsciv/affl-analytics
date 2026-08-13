#!/usr/bin/env python3
"""Phase 1 gate: prove we can reproduce ESPN's fantasy points from raw nflverse
stats under dim_scoring.

Why this matters: ESPN keeps no weekly lineups before 2018, so any player-level
pre-2018 history has to be computed from NFL stats. That is only trustworthy if
the same engine reproduces ESPN's own numbers in the seasons where we can check.

    python3 validate_scoring.py
"""
import math
import sqlite3
import sys
import os

DB_AFFL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'affl.db')
DB_NFL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nfl.db')
PASS_THRESHOLD = 0.95      # fraction of player-weeks that must match exactly

def rules_for(con, season):
    return {r[0]: r[1] for r in con.execute(
        'SELECT stat_name, points FROM dim_scoring WHERE season=? AND stat_name IS NOT NULL',
        (season,))}

def score(r, k, mode):
    if mode == 'BUCKET':
        # ESPN floored yardage to whole points through 2018: 1 per 25 passing,
        # 1 per 10 rushing/receiving, remainder discarded.
        yards = (math.floor(r['py'] / 25) + math.floor(r['ry'] / 10)
                 + math.floor(r['cy'] / 10))
        return (yards + r['pt'] * k.get('passTD', 0) + r['i'] * k.get('passInt', 0)
                + r['rt'] * k.get('rushTD', 0) + r['ct'] * k.get('recTD', 0)
                + r['rc'] * k.get('rec', 0) + r['fl'] * k.get('fumLost', 0)
                + r['tp'] * k.get('rush2pt', 0))
    return (r['py'] * k.get('passYds', 0) + r['pt'] * k.get('passTD', 0)
            + r['i'] * k.get('passInt', 0)
            + r['ry'] * k.get('rushYds', 0) + r['rt'] * k.get('rushTD', 0)
            + r['cy'] * k.get('recYds', 0) + r['ct'] * k.get('recTD', 0)
            + r['rc'] * k.get('rec', 0)
            + r['fl'] * k.get('fumLost', 0)
            + r['tp'] * k.get('rush2pt', 0))

def main():
    con = sqlite3.connect(DB_AFFL)
    con.row_factory = sqlite3.Row
    # Attach NFL database for the join
    con.execute(f"ATTACH DATABASE '{DB_NFL}' AS nfl")
    seasons = [r[0] for r in con.execute(
        'SELECT season FROM dim_season WHERE has_rosters=1 ORDER BY season')]
    print(f"{'season':>6} {'mode':>11} {'weeks':>9} {'exact':>8} {'<=1pt':>8} {'p99':>6}  verdict")
    ok = True
    for season in seasons:
        k = rules_for(con, season)
        mode = con.execute('SELECT yardage_mode FROM dim_season WHERE season=?',
                           (season,)).fetchone()[0]
        rows = con.execute("""
            SELECT r.points AS espn, n.pass_yards py, n.pass_tds pt, n.interceptions i,
                   n.rush_yards ry, n.rush_tds rt, n.rec_yards cy, n.rec_tds ct,
                   n.receptions rc, n.fumbles_lost fl, n.two_pt tp
              FROM fact_roster_week r
              JOIN dim_player p    ON p.player_id = r.player_id
              JOIN nfl.fact_nfl_week n ON n.season = r.season AND n.week = r.week
                                  AND n.gsis_id = p.gsis_id
             WHERE r.season = ? AND p.position IN ('QB','RB','WR','TE')
               AND r.points <> 0""", (season,)).fetchall()
        if not rows:
            continue
        d = sorted(abs(score(r, k, mode) - r['espn']) for r in rows)
        n = len(d)
        exact = sum(1 for x in d if x < 0.05) / n
        near = sum(1 for x in d if x <= 1.0) / n
        good = exact >= PASS_THRESHOLD
        ok &= good
        print(f'{season:>6} {mode:>11} {n:>9,} {exact*100:>7.1f}% {near*100:>7.1f}% '
              f'{d[int(n*0.99)]:>6.2f}  {"pass" if good else "FAIL"}')
    print()
    if ok:
        print('PASS — the scoring engine reproduces ESPN. Pre-2018 recomputation is viable.')
    else:
        print('FAIL — do not build pre-2018 player history until this passes.')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
