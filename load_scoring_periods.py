#!/usr/bin/env python3
"""Recover per-NFL-week team scores that fact_matchup cannot represent.

In 2014-2016 the playoff matchup periods each span TWO NFL scoring periods:
matchup period 14 covers NFL weeks 14+15, and 15 covers 16+17. fact_matchup keys
on (season, week, team_id) and stores only the combined total, which is why those
weeks average ~174 against a ~90 baseline.

ESPN kept the breakdown all along - `pointsByScoringPeriod` in league_YYYY.json -
but nothing ever read it.

This does NOT split fact_matchup. A playoff win is decided on the two-week total,
so splitting in place would turn one real result into two per-week results that
never happened. 2014 matchup period 14 is the example: team 5 won NFL week 14
114-113 and lost week 15 75-79, but the game itself was an AWAY win on 192-189.
Rewriting that as 1-1 would corrupt result, margin and every standing built on
them.

Instead this loads an additive table. fact_matchup keeps matchup-level truth;
fact_team_scoring_period carries the per-NFL-week scores that lineup work needs.

    python3 load_scoring_periods.py            # report only
    python3 load_scoring_periods.py --write
"""
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_team_scoring_period (
  season          INTEGER NOT NULL,
  scoring_period  INTEGER NOT NULL,   -- real NFL week
  team_id         INTEGER NOT NULL,
  points          REAL    NOT NULL,
  matchup_period  INTEGER NOT NULL,   -- the fact_matchup week this belongs to
  PRIMARY KEY (season, scoring_period, team_id)
)
"""


def rows_for(path):
    season = int(re.search(r'league_(\d+)\.json', os.path.basename(path)).group(1))
    with open(path) as fh:
        league = json.load(fh)
    out = []
    for matchup in league.get('schedule', []):
        period = matchup.get('matchupPeriodId')
        for side in ('home', 'away'):
            entry = matchup.get(side) or {}
            team = entry.get('teamId')
            by_period = entry.get('pointsByScoringPeriod') or {}
            if team is None or not by_period:
                continue
            for scoring_period, points in by_period.items():
                out.append((season, int(scoring_period), team, float(points), period))
    return season, out


def load(con, write=False):
    """Load per-NFL-week team scores into an open connection. Returns rows written.

    build_db.py must call this BEFORE load_pre2018_lineups, which reads this table
    to work out which matchup periods span two NFL weeks. Without it the pre-2018
    recovery cannot run at all.
    """
    total = 0
    print(f"{'season':>7} {'rows':>6} {'periods':>8} {'multi-week matchups':>21}")
    staged = []
    for path in sorted(glob.glob(os.path.join(HERE, 'data', 'league_*.json'))):
        season, rows = rows_for(path)
        if not rows:
            continue
        periods = sorted({r[1] for r in rows})
        spans = {}
        for _, sp, _team, _pts, mp in rows:
            spans.setdefault(mp, set()).add(sp)
        multi = sum(1 for mp, sps in spans.items() if len(sps) > 1)
        print(f'{season:>7} {len(rows):>6} {len(periods):>8} {multi:>21}')
        staged += rows
        total += len(rows)

    # Every matchup period must sum to its fact_matchup total. fact_matchup stores
    # points rounded to one decimal while pointsByScoringPeriod carries full
    # precision, so agreement is judged at the stored precision, not exactly.
    ROUNDING = 0.05
    by_matchup = {}
    for season, _sp, team, points, mp in staged:
        by_matchup[(season, mp, team)] = by_matchup.get((season, mp, team), 0.0) + points

    rejected = set()
    for (season, mp, team), summed in by_matchup.items():
        row = con.execute('SELECT points FROM fact_matchup WHERE season=? AND week=? AND team_id=?',
                          (season, mp, team)).fetchone()
        if row and abs(row[0] - summed) > ROUNDING:
            rejected.add((season, mp, team))

    if rejected:
        print(f'\n{len(rejected)} matchup period(s) do NOT reconcile - excluded, not loaded:')
        for season, mp, team in sorted(rejected):
            row = con.execute('SELECT points FROM fact_matchup WHERE season=? AND week=? AND team_id=?',
                              (season, mp, team)).fetchone()
            print(f'  {season} matchup period {mp} team {team}: '
                  f'fact_matchup={row[0]:g} vs summed periods={by_matchup[(season, mp, team)]:g}')
        print('  These are weeks where ESPN truncated the roster: pointsByScoringPeriod')
        print('  reflects only the surviving entries, while totalPoints keeps the true')
        print('  score. The per-period value is therefore not trustworthy for them.')

    keep = [r for r in staged if (r[0], r[4], r[2]) not in rejected]
    reconciled = len(by_matchup) - len(rejected)
    print(f'\n{total} scoring-period rows staged, {len(keep)} reconcile and will load')
    print(f'reconciliation against fact_matchup: {reconciled}/{len(by_matchup)} '
          f'({reconciled / len(by_matchup):.1%}) within stored precision')
    if reconciled / len(by_matchup) < 0.99:
        raise SystemExit('load_scoring_periods: too many periods fail to '
                         'reconcile. Refusing to write.')
    print('GATE PASSED')
    staged = keep
    total = len(keep)

    if not write:
        print('Report only. Re-run with --write to load.')
        return 0
    with con:
        con.execute(SCHEMA)
        con.execute('DELETE FROM fact_team_scoring_period')
        con.executemany(
            'INSERT OR REPLACE INTO fact_team_scoring_period'
            '(season, scoring_period, team_id, points, matchup_period) VALUES (?,?,?,?,?)',
            staged)
    print(f'Wrote {total} rows to fact_team_scoring_period.')
    return total


def main():
    con = sqlite3.connect(os.environ.get('AFFL_DB') or DB)
    return 0 if load(con, write='--write' in sys.argv) is not None else 1


if __name__ == '__main__':
    sys.exit(main())
