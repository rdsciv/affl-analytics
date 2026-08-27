#!/usr/bin/env python3
"""Train and evaluate the conditional-logit lineup model.

Builds real choice sets by hiding starters in a season we already know, fits the
weights on one season, and evaluates on a DIFFERENT one so nothing is scored on
data it was fitted to.

    python3 train_lineup_model.py
"""
import collections
import random
import sqlite3
import sys

import numpy as np

import build_candidate_scores
import lineup_model
from lineup_model import FEATURES, featurise, fit, predict, report

TEMPLATE = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'D/ST': 1}
FLEXIBLE = ('RB', 'WR', 'TE')
TOL = 0.05


def hole_clusters(con):
    """(team, position, n_weeks) runs of holes ESPN actually left in 2014-2016."""
    known = collections.defaultdict(list)
    for s, w, t, slot, c in con.execute(
            'SELECT season, week, team_id, slot, lineup_complete FROM fact_roster_week'
            ' WHERE season BETWEEN 2014 AND 2016 AND started=1'):
        known[(s, w, t)].append((slot, c))
    per = collections.Counter()
    for (season, _w, team), rows in known.items():
        if all(c for _s, c in rows):
            continue
        counts = collections.Counter(s for s, _c in rows)
        for pos, need in TEMPLATE.items():
            for _ in range(max(0, need - counts.get(pos, 0))):
                per[(team, pos)] += 1
    return per.most_common()


def build_choice_sets(con, season, rng):
    """Hide starters the way ESPN did, then enumerate each slot's candidates."""
    truth = collections.defaultdict(list)
    for w, t, pid, slot, pts in con.execute(
            'SELECT week, team_id, player_id, slot, points FROM fact_roster_week'
            ' WHERE season=? AND started=1', (season,)):
        truth[(w, t)].append((pid, slot, pts))
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

    full = {k: v for k, v in truth.items() if len(v) == 9 and k in targets}
    weeks = sorted({w for w, _t in full})
    teams = sorted({t for _w, t in full})

    hidden = {}
    for (team, position), n_weeks in hole_clusters(con):
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

    starts = collections.defaultdict(set)
    team_starts = collections.defaultdict(collections.Counter)
    for (w, t), rows in truth.items():
        for pid, _s, _p in rows:
            if pid in hidden.get((w, t), ()):
                continue          # the model must not see what it is guessing
            starts[(t, w)].add(pid)
            team_starts[t][pid] += 1

    by_week_pos = collections.defaultdict(list)
    for (w, pid), (pts, pos) in scores.items():
        by_week_pos[(w, pos)].append((pts, pid))
    started_anywhere = collections.defaultdict(set)
    for (t, w), players in starts.items():
        started_anywhere[w] |= players

    sets = []
    for (week, team), gone in sorted(hidden.items()):
        if len(gone) != 1:
            continue                       # single-slot sets only, for clean labels
        true_pid = next(iter(gone))
        kept = [r for r in truth[(week, team)] if r[0] not in gone]
        residual = round(targets[(week, team)] - sum(r[2] for r in kept), 2)
        counts = collections.Counter(r[1] for r in kept)
        missing = [p for p, n in TEMPLATE.items() for _ in range(max(0, n - counts.get(p, 0)))]
        position = missing[0] if len(missing) == 1 else 'FLEX'
        wanted = FLEXIBLE if position == 'FLEX' else (position,)
        on_roster = {r[0] for r in kept}
        elsewhere = started_anywhere[week] - on_roster - {true_pid}

        cands = []
        for pos in wanted:
            for pts, pid in by_week_pos.get((week, pos), ()):
                if abs(pts - residual) > TOL or pid in on_roster or pid in elsewhere:
                    continue
                cands.append(pid)
        if true_pid not in cands or len(cands) < 2:
            continue                       # nothing to learn from a set of one

        cover = collections.Counter()
        for pid in cands:
            for w2 in weeks:
                s = scores.get((w2, pid))
                if s and (w2, team) in hidden:
                    kept2 = [r for r in truth[(w2, team)] if r[0] not in hidden[(w2, team)]]
                    r2 = round(targets[(w2, team)] - sum(r[2] for r in kept2), 2)
                    if abs(s[0] - r2) <= TOL:
                        cover[pid] += 1

        ctx = {'pool': pool, 'team': team, 'week': week, 'starts': starts,
               'team_starts': team_starts, 'weeks': len(weeks), 'drafted': drafted,
               'production': production, 'position_of': position_of, 'cover': cover, 'is_flex': position == 'FLEX'}
        X = np.array([featurise(pid, ctx) for pid in cands])
        sets.append((X, cands.index(true_pid), cands, (week, team)))
    return sets


def evaluate(sets, beta, label):
    top1 = 0
    buckets = collections.defaultdict(lambda: [0, 0])
    for X, truth, _c, _k in sets:
        p = predict(X, beta)
        pick = int(np.argmax(p))
        top1 += pick == truth
        b = min(int(p[pick] * 10) / 10, 0.9)
        buckets[b][0] += pick == truth
        buckets[b][1] += 1
    print(f'\n{label}: {top1}/{len(sets)} correct ({top1 / len(sets):.1%}) '
          f'over {len(sets)} choice sets, mean set size '
          f'{np.mean([len(s[2]) for s in sets]):.1f}')
    print(f"  {'confidence':>12} {'n':>5} {'actual':>8}")
    for b in sorted(buckets, reverse=True):
        hit, n = buckets[b]
        if n >= 5:
            print(f'  {b:>11.0%}+ {n:>5} {hit / n:>7.0%}')
    return top1 / len(sets)


REPLICATES = 12


def gather(con, season, seeds):
    """Many ablation replicates of one season - each seed hides a different set of
    starters, so one season yields hundreds of independent choice sets instead of
    the few dozen a single draw produces."""
    out = []
    for seed in seeds:
        out += build_choice_sets(con, season, random.Random(seed))
    return out


def main():
    con = sqlite3.connect('affl.db')
    seeds = list(range(100, 100 + REPLICATES))

    # Two folds, each trained on one complete season and tested on the other, so
    # every reported number is out of sample.
    folds = [(2018, 2017), (2017, 2018)]
    data = {s: gather(con, s, seeds) for s in (2017, 2018)}
    for season, sets in data.items():
        print(f'{season}: {len(sets)} choice sets from {REPLICATES} ablation replicates, '
              f'mean set size {np.mean([len(s[2]) for s in sets]):.1f}')

    accs = []
    for train_season, test_season in folds:
        beta = fit([(X, t) for X, t, _c, _k in data[train_season]])
        print(f'\n{"=" * 64}\ntrained on {train_season}, tested on {test_season}')
        report(beta)
        evaluate(data[test_season], np.zeros(len(FEATURES)), 'baseline (no model)')
        accs.append(evaluate(data[test_season], beta, 'conditional logit'))

    beta = fit([(X, t) for s in data.values() for X, t, _c, _k in s])
    print(f'\n{"=" * 64}')
    print(f'cross-validated accuracy: {np.mean(accs):.1%}')
    print('final weights fitted on both complete seasons:')
    report(beta)
    np.save('lineup_model_beta.npy', beta)
    print('\nsaved weights to lineup_model_beta.npy')
    return 0


if __name__ == '__main__':
    sys.exit(main())
