#!/usr/bin/env python3
"""Measure the lineup solver by hiding starters we already know.

2017 is the right test bed: same league, same 12 teams, same integer scoring as
2014-2016, and every lineup complete and verified. Punch holes in it that match
the pattern ESPN actually left in 2014-2016, run the SAME solver, and compare
what it recovers against the truth it never saw.

The holes are not random. ESPN's deletions cluster by team and position - one
team is missing its kicker in eight separate weeks - so the harness samples real
(slots_open, positions) shapes observed in 2014-2016 rather than dropping players
uniformly, which would flatter the solver.

    python3 ablate_2017.py [--season 2017]
"""
import collections
import random
import sqlite3
import sys

import build_candidate_scores
import solve_lineups

TEMPLATE = solve_lineups.TEMPLATE


def observed_clusters(con):
    """(team, position, n_weeks) clusters ESPN actually left in 2014-2016."""
    known = collections.defaultdict(list)
    for s, w, t, slot, complete in con.execute(
            'SELECT season, week, team_id, slot, lineup_complete FROM fact_roster_week'
            '  WHERE season BETWEEN 2014 AND 2016 AND started=1'):
        known[(s, w, t)].append((slot, complete))
    per_team = collections.Counter()
    for (season, _w, team), rows in known.items():
        if all(c for _s, c in rows):
            continue
        counts = collections.Counter(s for s, _c in rows)
        for pos, need in TEMPLATE.items():
            for _ in range(max(0, need - counts.get(pos, 0))):
                per_team[(season, team, pos)] += 1
    return [(team, pos, n) for (_season, team, pos), n in per_team.most_common()]


def observed_hole_shapes(con):
    """(n_missing, tuple(positions)) shapes actually left by ESPN in 2014-2016."""
    known = collections.defaultdict(list)
    for s, w, t, slot, complete in con.execute(
            'SELECT season, week, team_id, slot, lineup_complete FROM fact_roster_week'
            '  WHERE season BETWEEN 2014 AND 2016 AND started=1'):
        known[(s, w, t)].append((slot, complete))
    shapes = []
    for rows in known.values():
        if all(c for _s, c in rows):
            continue
        counts = collections.Counter(s for s, _c in rows)
        missing = []
        for pos, need in TEMPLATE.items():
            missing += [pos] * max(0, need - counts.get(pos, 0))
        open_slots = 9 - len(rows)
        if 1 <= open_slots <= 2:
            shapes.append((open_slots, tuple(sorted(missing))))
    return shapes


def main():
    season = 2017
    if '--season' in sys.argv:
        season = int(sys.argv[sys.argv.index('--season') + 1])
    rng = random.Random(20260826)      # fixed seed: reproducible, not cherry-picked
    con = sqlite3.connect('affl.db')

    truth = collections.defaultdict(list)
    for w, t, pid, slot, pts in con.execute(
            'SELECT week, team_id, player_id, slot, points FROM fact_roster_week'
            '  WHERE season=? AND started=1', (season,)):
        truth[(w, t)].append((pid, slot, pts))
    targets = {(w, t): p for w, t, p in con.execute(
        'SELECT week, team_id, points FROM fact_matchup WHERE season=?', (season,))}
    scores = build_candidate_scores.all_scores(con, season)
    shapes = observed_hole_shapes(con)

    full = {k: v for k, v in truth.items() if len(v) == 9 and k in targets}

    # ESPN's holes CLUSTER: one team loses its kicker across many weeks, because
    # what it deleted were streamed pickups, not held starters. Reproduce that
    # shape - holing single isolated weeks would leave continuity intact on both
    # sides of every hole and badly overstate the solver.
    cluster_profile = observed_clusters(con)
    weeks = sorted({w for w, _t in full})
    teams = sorted({t for _w, t in full})

    known, hidden = {}, {}
    for key, rows in truth.items():
        known[key] = [(pid, slot, pts, 1) for pid, slot, pts in rows]

    for team, position, n_weeks in cluster_profile:
        if team not in teams:
            team = rng.choice(teams)
        target_weeks = rng.sample(weeks, min(n_weeks, len(weeks)))
        for week in target_weeks:
            key = (week, team)
            if key not in full:
                continue
            rows = list(truth[key])
            already = hidden.get(key, set())
            match = [r for r in rows if r[1] == position and r[0] not in already]
            if not match:
                continue
            if len(already) >= 2:
                continue
            pick = rng.choice(match)
            hidden.setdefault(key, set()).add(pick[0])
            known[key] = [(pid, slot, pts, 0) for pid, slot, pts in rows
                          if pid not in hidden[key]]

    results, stats = solve_lineups.solve(season, known, targets, scores)

    per_conf = collections.defaultdict(lambda: [0, 0])
    per_ev = collections.defaultdict(lambda: [0, 0])
    for (_s, week, team, pid, _pos, _pts, confidence, evidence, _n, _m) in results:
        actual = hidden.get((week, team), set())
        hit = pid in actual
        per_conf[confidence][0] += hit
        per_conf[confidence][1] += 1
        per_ev[evidence][0] += hit
        per_ev[evidence][1] += 1

    total_hidden = sum(len(v) for v in hidden.values())
    print(f'ablation on {season}: {len(hidden)} team-weeks holed, '
          f'{total_hidden} starters hidden\n')
    print(f"{'tier':>10} {'recovered':>10} {'correct':>8} {'accuracy':>9}")
    for conf in ('CERTAIN', 'PROBABLE'):
        hit, n = per_conf[conf]
        if n:
            print(f'{conf:>10} {n:>10} {hit:>8} {hit / n:>8.1%}')
    print(f"\n{'evidence':>10} {'n':>10} {'correct':>8} {'accuracy':>9}")
    for ev in ('anchored', 'adjacent', 'rostered', 'free'):
        hit, n = per_ev[ev]
        if n:
            print(f'{ev:>10} {n:>10} {hit:>8} {hit / n:>8.1%}')
    recovered = sum(v[1] for v in per_conf.values())
    correct = sum(v[0] for v in per_conf.values())
    print(f'\noverall: {correct}/{total_hidden} hidden starters correctly named '
          f'({correct / total_hidden:.1%} of holes), '
          f'{correct}/{recovered} of answers given were right '
          f'({correct / recovered:.1%})' if recovered else '')
    return 0


if __name__ == '__main__':
    sys.exit(main())
