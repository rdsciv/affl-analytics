#!/usr/bin/env python3
"""Apply the trained conditional-logit model to the real 2014-2016 holes.

WRITES ONLY TO affl_reconstruct.db.

Every proposed starter carries the model's probability, and those probabilities
are calibrated: measured out of sample, candidates the model scores above 0.9 are
right about 95% of the time. So a consumer can pick a bar and know what it buys,
instead of trusting a label.

    python3 apply_lineup_model.py            # report only
    python3 apply_lineup_model.py --write
"""
import collections
import sqlite3
import sys

import numpy as np

import build_candidate_scores
import lineup_model
from lineup_model import featurise, predict

TEMPLATE = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'D/ST': 1}
FLEXIBLE = ('RB', 'WR', 'TE')
TOL = 0.05
SEASONS = (2014, 2015, 2016)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_roster_week_modelled (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  slot            TEXT    NOT NULL,
  points          REAL    NOT NULL,
  probability     REAL    NOT NULL,   -- calibrated P(this player started)
  candidates      INTEGER NOT NULL,   -- size of the choice set
  runner_up       INTEGER,            -- next most likely player
  runner_up_prob  REAL,
  method          TEXT    NOT NULL,
  PRIMARY KEY (season, week, team_id, player_id)
)
"""


def solve_season(con, season, beta):
    known = collections.defaultdict(list)
    for w, t, pid, slot, pts, complete in con.execute(
            'SELECT week, team_id, player_id, slot, points, lineup_complete'
            '  FROM fact_roster_week WHERE season=? AND started=1', (season,)):
        known[(w, t)].append((pid, slot, pts, complete))
    targets = {(w, t): p for w, t, p in con.execute(
        'SELECT week, team_id, points FROM fact_matchup WHERE season=?', (season,))}
    scores = build_candidate_scores.all_scores(con, season)
    pool = lineup_model.load_pool(season)
    production = lineup_model.production_index(scores)
    position_of = {pid: pos for (_w, pid), (_pts, pos) in scores.items()}
    drafted = collections.defaultdict(set)
    for t, pid in con.execute(
            'SELECT team_id, player_id FROM fact_draft_pick WHERE season=?', (season,)):
        drafted[t].add(pid)

    starts, team_starts = collections.defaultdict(set), collections.defaultdict(collections.Counter)
    started_anywhere = collections.defaultdict(set)
    for (w, t), rows in known.items():
        for pid, _s, _p, _c in rows:
            starts[(t, w)].add(pid)
            team_starts[t][pid] += 1
            started_anywhere[w].add(pid)
    weeks = sorted({w for w, _t in known})

    by_week_pos = collections.defaultdict(list)
    for (w, pid), (pts, pos) in scores.items():
        by_week_pos[(w, pos)].append((pts, pid))

    # residual and open position per incomplete team-week
    open_slots = {}
    for (week, team), rows in known.items():
        if all(c for *_x, c in rows) or (week, team) not in targets:
            continue
        residual = round(targets[(week, team)] - sum(r[2] for r in rows), 2)
        counts = collections.Counter(r[1] for r in rows)
        missing = [p for p, n in TEMPLATE.items() for _ in range(max(0, n - counts.get(p, 0)))]
        if 9 - len(rows) != 1 or residual <= 0:
            continue
        position = missing[0] if len(missing) == 1 else 'FLEX'
        open_slots[(week, team)] = (residual, position, {r[0] for r in rows})

    results = []
    for (week, team), (residual, position, on_roster) in sorted(open_slots.items()):
        wanted = FLEXIBLE if position == 'FLEX' else (position,)
        elsewhere = started_anywhere[week] - on_roster
        cands = []
        for pos in wanted:
            for pts, pid in by_week_pos.get((week, pos), ()):
                if abs(pts - residual) > TOL or pid in on_roster or pid in elsewhere:
                    continue
                cands.append((pid, pts, pos))
        if not cands:
            continue

        cover = collections.Counter()
        for pid, _pts, _pos in cands:
            for (w2, t2), (r2, _p2, _o2) in open_slots.items():
                if t2 != team:
                    continue
                s = scores.get((w2, pid))
                if s and abs(s[0] - r2) <= TOL:
                    cover[pid] += 1

        ctx = {'pool': pool, 'team': team, 'week': week, 'starts': starts,
               'team_starts': team_starts, 'weeks': len(weeks), 'drafted': drafted,
               'production': production, 'position_of': position_of, 'cover': cover, 'is_flex': position == 'FLEX'}
        X = np.array([featurise(pid, ctx) for pid, _p, _o in cands])
        probs = predict(X, beta)
        order = np.argsort(-probs)
        best = order[0]
        pid, pts, pos = cands[best]
        runner = cands[order[1]][0] if len(cands) > 1 else None
        runner_p = float(probs[order[1]]) if len(cands) > 1 else None
        results.append((season, week, team, pid, pos, pts, float(probs[best]),
                        len(cands), runner, runner_p, 'conditional-logit'))
    return results


def main():
    write = '--write' in sys.argv
    beta = np.load('lineup_model_beta.npy')
    con = sqlite3.connect('affl.db')
    allr = []
    for season in SEASONS:
        r = solve_season(con, season, beta)
        allr += r
        print(f'{season}: {len(r)} single-slot holes given a modelled starter')

    probs = np.array([r[6] for r in allr])
    print(f'\n{len(allr)} slots modelled')
    print(f"{'probability':>14} {'slots':>7} {'expected right':>15}")
    # calibration measured out of sample in train_lineup_model.py
    for lo, hi, acc in ((0.9, 1.01, 0.95), (0.8, 0.9, 0.88), (0.7, 0.8, 0.83),
                        (0.5, 0.7, 0.60), (0.0, 0.5, 0.40)):
        n = int(((probs >= lo) & (probs < hi)).sum())
        if n:
            print(f'  {lo:>5.0%}-{hi if hi <= 1 else 1:>5.0%} {n:>7} {n * acc:>15.0f}')
    strong = int((probs >= 0.9).sum())
    print(f'\n{strong} slots at >=90% confidence (~{strong * 0.95:.0f} expected correct)')

    if not write:
        print('\nReport only. Re-run with --write to load into affl_reconstruct.db.')
        return 0
    fork = sqlite3.connect('affl_reconstruct.db')
    with fork:
        fork.execute(SCHEMA)
        fork.execute('DELETE FROM fact_roster_week_modelled')
        fork.executemany(
            'INSERT OR REPLACE INTO fact_roster_week_modelled VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            allr)
    print(f'\nWrote {len(allr)} modelled starters to affl_reconstruct.db')
    return 0


if __name__ == '__main__':
    sys.exit(main())
