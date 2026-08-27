#!/usr/bin/env python3
"""Calibrate the transition penalty by ablation, and test whether it helps at all.

lambda = 0 makes the Viterbi path reduce exactly to the per-slot solver, so it is
the honest baseline. If no lambda > 0 beats it, the temporal model adds nothing
here and that is the finding - ESPN preferentially deleted STREAMED players, the
ones with the weakest continuity, so it is a real possibility.

Holes are punched using the clustered pattern ESPN actually left, not uniform
random: uniform holes leave continuity intact on both sides of every gap and
badly overstate any temporal method.

    python3 fhmm_calibrate.py
"""
import collections
import random
import sqlite3
import sys

import numpy as np

import build_candidate_scores
import fhmm_solve

TEMPLATE = fhmm_solve.TEMPLATE
LAMBDAS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
REPLICATES = 6


def observed_clusters(con):
    known = collections.defaultdict(list)
    for s, w, t, slot, c in con.execute(
            'SELECT season, week, team_id, slot, lineup_complete FROM fact_roster_week'
            ' WHERE season BETWEEN 2014 AND 2016 AND started=1'):
        known[(s, w, t)].append((slot, c))
    per = collections.Counter()
    for (_s, _w, team), rows in known.items():
        if all(c for _x, c in rows):
            continue
        counts = collections.Counter(x for x, _c in rows)
        for pos, need in TEMPLATE.items():
            for _ in range(max(0, need - counts.get(pos, 0))):
                per[(team, pos)] += 1
    return per.most_common()


def make_ablation(con, season, rng, clusters):
    truth = collections.defaultdict(list)
    for w, t, pid, slot, pts in con.execute(
            'SELECT week, team_id, player_id, slot, points FROM fact_roster_week'
            ' WHERE season=? AND started=1', (season,)):
        truth[(w, t)].append((pid, slot, pts))
    targets = {(w, t): p for w, t, p in con.execute(
        'SELECT week, team_id, points FROM fact_matchup WHERE season=? AND week<=13',
        (season,))}
    full = {k: v for k, v in truth.items() if len(v) == 9 and k in targets}
    weeks = sorted({w for w, _t in full})
    teams = sorted({t for _w, t in full})

    hidden = {}
    for (team, position), n_weeks in clusters:
        if team not in teams:
            team = rng.choice(teams)
        for week in rng.sample(weeks, min(n_weeks, len(weeks))):
            key = (week, team)
            if key not in full or len(hidden.get(key, ())) >= 2:
                continue
            match = [r for r in truth[key]
                     if r[1] == position and r[0] not in hidden.get(key, set())]
            if match:
                hidden.setdefault(key, set()).add(rng.choice(match)[0])

    # 13% of REAL holes are FLEX holes - all named slots filled, the open slot
    # taking any RB/WR/TE. Hiding only by named position never produces one, so the
    # model would never see the case and could not learn that a tight end is almost
    # never the flexed player. Generate them at the observed rate.
    n_flex = max(1, int(0.13 * len(hidden)))
    for key in rng.sample(sorted(full), min(n_flex * 3, len(full))):
        if len(hidden) and n_flex <= 0:
            break
        if key in hidden:
            continue
        counts = collections.Counter(r[1] for r in truth[key])
        surplus = [r for r in truth[key]
                   if r[1] in ('RB', 'WR', 'TE') and counts[r[1]] > TEMPLATE[r[1]]]
        if not surplus:
            continue
        hidden[key] = {rng.choice(surplus)[0]}
        n_flex -= 1

    known = {}
    for key, rows in truth.items():
        gone = hidden.get(key, set())
        known[key] = [(pid, slot, pts, 0 if gone else 1)
                      for pid, slot, pts in rows if pid not in gone]
    return known, targets, hidden, truth


def score_run(results, hidden, truth):
    by_pos = collections.defaultdict(lambda: [0, 0])
    hit = n = 0
    pos_of = {}
    for key, gone in hidden.items():
        for pid, slot, _p in truth[key]:
            if pid in gone:
                pos_of[(key, pid)] = slot
    for r in results:
        key = (r['week'], r['team_id'])
        gone = hidden.get(key, set())
        correct = r['player_id'] in gone
        n += 1
        hit += correct
        # attribute to the position of whatever was actually hidden in that slot
        pos = r['slot']
        by_pos[pos][0] += correct
        by_pos[pos][1] += 1
    total_hidden = sum(len(v) for v in hidden.values())
    return hit, n, total_hidden, by_pos


def main():
    con = sqlite3.connect('affl.db')
    beta = np.load('lineup_model_beta.npy')
    clusters = observed_clusters(con)
    scores = {s: build_candidate_scores.all_scores(con, s) for s in (2017, 2018)}

    print(f'sweeping lambda over {LAMBDAS}, {REPLICATES} replicates x 2 seasons\n')
    print(f"{'lambda':>7} {'answers':>8} {'correct':>8} {'accuracy':>9} {'coverage':>9}")
    table = {}
    for lam in LAMBDAS:
        hit = n = hidden_total = 0
        pos_acc = collections.defaultdict(lambda: [0, 0])
        for season in (2017, 2018):
            for seed in range(200, 200 + REPLICATES):
                rng = random.Random(seed)
                known, targets, hidden, truth = make_ablation(con, season, rng, clusters)
                res = fhmm_solve.solve(season, known, targets, scores[season], beta, lam)
                h, m, th, bp = score_run(res, hidden, truth)
                hit += h
                n += m
                hidden_total += th
                for k, v in bp.items():
                    pos_acc[k][0] += v[0]
                    pos_acc[k][1] += v[1]
        acc = hit / n if n else 0.0
        cov = n / hidden_total if hidden_total else 0.0
        table[lam] = (acc, cov, dict(pos_acc))
        print(f'{lam:>7.2f} {n:>8} {hit:>8} {acc:>8.1%} {cov:>8.1%}')

    base = table[0.0][0]
    best_lam = max(table, key=lambda k: table[k][0])
    best = table[best_lam][0]
    print(f'\nbaseline (lambda=0, per-slot):   {base:.1%}')
    print(f'best temporal (lambda={best_lam}):     {best:.1%}')
    delta = best - base
    if best_lam == 0.0 or delta <= 0.005:
        print('\nVERDICT: temporal coupling does NOT help here. The per-slot solver is')
        print('as good. Consistent with ESPN having deleted streamed players - exactly')
        print('the ones with no week-to-week continuity to exploit.')
    else:
        print(f'\nVERDICT: temporal coupling helps, +{delta:.1%} absolute over per-slot.')
        print(f'\nby position at lambda={best_lam}:')
        for pos, (h, m) in sorted(table[best_lam][2].items(), key=lambda kv: -kv[1][1]):
            if m:
                print(f'   {pos:>6} {m:>5} answers {h / m:>7.1%}')
    np.save('fhmm_lambda.npy', np.array([best_lam]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
