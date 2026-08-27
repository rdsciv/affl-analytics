#!/usr/bin/env python3
"""Run the temporal joint solver on the real 2014-2016 holes.

WRITES ONLY TO affl_reconstruct.db.

    python3 fhmm_apply.py            # report only
    python3 fhmm_apply.py --write
"""
import collections
import sqlite3
import sys

import numpy as np

import build_candidate_scores
import fhmm_solve

SEASONS = (2014, 2015, 2016)
# measured by fhmm_calibrate.py on clustered ablations of 2017 and 2018
ACCURACY = {1: 0.790, 2: 0.496}

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_roster_week_fhmm (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  slot            TEXT    NOT NULL,
  points          REAL    NOT NULL,
  open_slots      INTEGER NOT NULL,   -- 1 or 2; drives expected accuracy
  expected_acc    REAL    NOT NULL,   -- out-of-sample rate for that shape
  lambda_used     REAL    NOT NULL,
  method          TEXT    NOT NULL,
  PRIMARY KEY (season, week, team_id, player_id)
)
"""


def main():
    write = '--write' in sys.argv
    lam = float(np.load('fhmm_lambda.npy')[0])
    beta = np.load('lineup_model_beta.npy')
    con = sqlite3.connect('affl.db')

    rows, per_season = [], {}
    for season in SEASONS:
        scores = build_candidate_scores.all_scores(con, season)
        known = collections.defaultdict(list)
        for w, t, pid, slot, pts, complete in con.execute(
                'SELECT week, team_id, player_id, slot, points, lineup_complete'
                '  FROM fact_roster_week WHERE season=? AND started=1 AND week<=13',
                (season,)):
            known[(w, t)].append((pid, slot, pts, complete))
        targets = {(w, t): p for w, t, p in con.execute(
            'SELECT week, team_id, points FROM fact_matchup WHERE season=? AND week<=13',
            (season,))}
        res = fhmm_solve.solve(season, known, targets, scores, beta, lam)
        per_season[season] = len(res)
        for r in res:
            rows.append((season, r['week'], r['team_id'], r['player_id'], r['slot'],
                         r['points'], r['slots'], ACCURACY.get(r['slots'], 0.4),
                         lam, 'fhmm-viterbi'))

    print(f'lambda = {lam}\n')
    for season, n in per_season.items():
        print(f'  {season}: {n} starters recovered')

    holes = con.execute("""
        SELECT SUM(9 - n) FROM (
          SELECT season, week, team_id, COUNT(*) n FROM fact_roster_week
           WHERE season BETWEEN 2014 AND 2016 AND week<=13
           GROUP BY season, week, team_id)""").fetchone()[0]
    by_shape = collections.Counter(r[6] for r in rows)
    expected = sum(ACCURACY.get(r[6], 0.4) for r in rows)
    print(f'\n{len(rows)} of {holes} missing starter slots filled '
          f'({len(rows) / holes:.0%} coverage)')
    print(f"{'shape':>16} {'slots':>7} {'accuracy':>9} {'expected right':>15}")
    for shape in sorted(by_shape):
        n = by_shape[shape]
        print(f'{shape:>12} slot {n:>7} {ACCURACY.get(shape, 0.4):>8.1%} '
              f'{n * ACCURACY.get(shape, 0.4):>15.0f}')
    print(f"{'TOTAL':>16} {len(rows):>7} {'':>9} {expected:>15.0f}")

    if not write:
        print('\nReport only. Re-run with --write.')
        return 0
    fork = sqlite3.connect('affl_reconstruct.db')
    with fork:
        fork.execute(SCHEMA)
        fork.execute('DELETE FROM fact_roster_week_fhmm')   # never accumulate
        fork.executemany(
            'INSERT OR REPLACE INTO fact_roster_week_fhmm VALUES (?,?,?,?,?,?,?,?,?,?)',
            rows)
    print(f'\nWrote {len(rows)} rows to affl_reconstruct.db :: fact_roster_week_fhmm')
    return 0


if __name__ == '__main__':
    sys.exit(main())
