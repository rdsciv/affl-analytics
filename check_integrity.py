#!/usr/bin/env python3
"""Guard affl.db against inferred data.

affl.db holds facts only: rows ESPN returned, or corrections proven against
ESPN's own numbers. Anything solved, guessed or probabilistic belongs in a
separate fork and must never appear here.

Two checks, both cheap enough to run on every commit:

  1. No reconstructed table exists in main.
  2. Every COMPLETE fact_roster_week team-week sums exactly to that team's known
     score. A reconstructed lineup cannot satisfy this by construction, so this
     doubles as a contamination detector rather than only a data-quality check.
     Team-weeks flagged lineup_complete = 0 are ones ESPN truncated; their
     surviving starters are real but cannot sum to the full score, so they are
     held only to the bound that a lineup cannot outscore its team.

    python3 check_integrity.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
# Solver output must never reach production. The patterns below are what a fork
# writes; anything matching fails the build.
BANNED = ('%_reconstructed', '%_inferred', '%_predicted', '%_solved',
          '%_fhmm', '%_modelled')
# Two exceptions, both sanctioned by the CONTRACTS.md evidence table: pre-2018
# season totals computed from nflverse under that year's scoring rules are the
# "Reconstructed" tier, explorable and labelled. They are built by the main
# pipeline (contracts.py::load_reconstructed_par, called from build_db.py) and
# wiped by build_db.wipe(), so they cannot live in a fork - they reappear on
# every build. Named exactly; anything else matching a pattern above still fails.
SANCTIONED = {'fact_player_season_par_reconstructed',
              'v_custody_par_reconstructed'}
# fact_matchup stores points to one decimal while a lineup is the sum of nine
# full-precision player scores, so the two can legitimately differ by one step in
# the last stored place. Anything larger is a real discrepancy, not rounding.
ROUNDING = 0.11

# Team-weeks where ESPN's own payload is internally inconsistent, so no lineup can
# reconcile. Verified against data/box_raw: for every team below, ESPN reports a
# team total larger than the sum of its own starter rows.
#
#   2022 week 17 - BUF at CIN was abandoned after Damar Hamlin's cardiac arrest and
#   declared a no-contest. ESPN zeroed every Bill and Bengal player row but left the
#   team totals frozen at their pre-cancellation values. Measured shortfalls, and the
#   starters holding a zero:
#     team  7  78.3 vs 60.5   Mixon, Bass
#     team  9  76.0 vs 59.6   Diggs
#     team 10  85.0 vs 72.1   McPherson, G. Davis, (Tagovailoa - genuine DNP)
#     team 11  80.5 vs 57.5   Singletary, Allen
#     team 13 110.7 vs 84.5   Chase, Burrow
#   nflverse has no stat rows for the abandoned game, so this is not recoverable and
#   not ours to fix. Widening ROUNDING would hide it everywhere else, so it is named
#   here instead.
ESPN_DEFECT = {(2022, 17)}


def main():
    con = sqlite3.connect(DB)
    failures = []

    print('1. no inferred tables in affl.db')
    found = []
    for pattern in BANNED:
        found += [name for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name LIKE ?",
            (pattern,))]
    found = [n for n in found if n not in SANCTIONED]
    if found:
        failures.append(f'inferred objects present in main: {sorted(found)}')
        print(f'   FAIL - {sorted(found)}')
    else:
        print(f'   ok - none present ({len(SANCTIONED)} sanctioned PAR objects skipped)')

    print('\n2. every fact_roster_week team-week reconciles to its known score')
    # A team's score comes from fact_matchup, or from fact_team_scoring_period for
    # weeks with no matchup row (playoff byes).
    rows = con.execute("""
        SELECT rw.season, rw.week, rw.team_id,
               ROUND(SUM(rw.points), 2)                  AS lineup,
               COALESCE(m.points, sp.points)             AS target,
               MIN(COALESCE(rw.lineup_complete, 1))      AS complete
          FROM fact_roster_week rw
          LEFT JOIN fact_matchup m
                 ON m.season = rw.season AND m.week = rw.week AND m.team_id = rw.team_id
          LEFT JOIN fact_team_scoring_period sp
                 ON sp.season = rw.season AND sp.scoring_period = rw.week
                AND sp.team_id = rw.team_id
         WHERE rw.started = 1
         GROUP BY rw.season, rw.week, rw.team_id
    """).fetchall()

    by_season = {}
    unmatched = 0
    material = []
    partial = 0
    defects = []
    for season, week, team, lineup, target, complete in rows:
        if target is None:
            unmatched += 1
            continue
        gap = abs(lineup - target)
        if (season, week) in ESPN_DEFECT:
            if gap > ROUNDING:
                defects.append((season, week, team, lineup, target, gap))
            continue
        if not complete:
            # ESPN dropped entries from this lineup. The surviving starters are
            # still real, so the only thing that can be checked is that they do
            # not outscore the team.
            partial += 1
            if lineup - target > ROUNDING:
                material.append((season, week, team, lineup, target, gap))
                good, total = by_season.get(season, (0, 0))
                by_season[season] = (good, total + 1)
            continue
        ok = gap <= ROUNDING
        good, total = by_season.get(season, (0, 0))
        by_season[season] = (good + (1 if ok else 0), total + 1)
        if not ok:
            material.append((season, week, team, lineup, target, gap))

    for season in sorted(by_season):
        good, total = by_season[season]
        flag = 'ok' if good == total else 'FAIL'
        print(f'   {season}: {good}/{total} reconcile  {flag}')
        if good != total:
            failures.append(f'{season}: {total - good} team-week(s) do not reconcile')
    if material:
        print('\n   team-weeks that do not reconcile:')
        for season, week, team, lineup, target, gap in sorted(material):
            print(f'     {season} wk{week} team {team}: lineup={lineup:g} '
                  f'known score={target:g} short by {gap:.2f}')
    if defects:
        print('\n   team-weeks excluded - ESPN\'s own payload does not reconcile:')
        for season, week, team, lineup, target, gap in sorted(defects):
            print(f'     {season} wk{week} team {team}: lineup={lineup:g} '
                  f'ESPN score={target:g} short by {gap:.2f}')
    if unmatched:
        print(f'   note: {unmatched} team-week(s) have no known score to check against')
    if partial:
        print(f'   note: {partial} team-week(s) flagged lineup_complete=0 - ESPN dropped')
        print(f'         entries, so only the "cannot outscore the team" bound applies')

    # The pre-2018 recovery is irreplaceable and build_db.py wipes the table it
    # lives in, so silence is not proof it is still there. These are floors, not
    # observations: they only move up, and only when more is genuinely recovered.
    FLOORS = {2014: 1277, 2015: 1250, 2016: 1277, 2017: 1726}
    print('\n3. pre-2018 recovery is still present and still covers its team-weeks')
    for season, floor in sorted(FLOORS.items()):
        rows = con.execute('SELECT COUNT(*) FROM fact_roster_week WHERE season=?',
                           (season,)).fetchone()[0]
        gaps = con.execute("""
            SELECT COUNT(*) FROM fact_matchup m
             WHERE m.season = ? AND NOT EXISTS (
               SELECT 1 FROM fact_roster_week r
                WHERE r.season=m.season AND r.week=m.week AND r.team_id=m.team_id)""",
                           (season,)).fetchone()[0]
        flag = 'ok' if rows >= floor else 'FAIL'
        print(f'   {season}: {rows} rows (floor {floor})  {gaps} team-week(s) '
              f'scored but unlineup-ed  {flag}')
        if rows < floor:
            failures.append(f'{season}: fact_roster_week fell to {rows} rows, '
                            f'below the recovered floor of {floor} - data was lost')

    print('\n4. every player referenced by a lineup or a draft pick has a name')
    unknown = con.execute("""
        SELECT COUNT(*) FROM (
          SELECT player_id FROM fact_roster_week
          UNION SELECT player_id FROM fact_draft_pick WHERE player_id IS NOT NULL)
         WHERE player_id NOT IN (SELECT player_id FROM dim_player)""").fetchone()[0]
    print(f'   {unknown} unnamed  {"ok" if unknown == 0 else "FAIL"}')
    if unknown:
        failures.append(f'{unknown} player id(s) referenced with no dim_player row')

    print()
    if failures:
        print('INTEGRITY CHECK FAILED')
        for f in failures:
            print(f'  - {f}')
        return 1
    print('INTEGRITY CHECK PASSED - affl.db contains facts only.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
