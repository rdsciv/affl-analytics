#!/usr/bin/env python3
"""Temporal joint solver for missing lineup starters (Viterbi over hole-clusters).

WRITES NOTHING. Pure library - callers decide where results go, and the only legal
destination is affl_reconstruct.db.

Why this exists: the per-slot solver scores each hole in isolation. Energy
disaggregation hit the same wall - Hart's per-instant combinatorial formulation -
and the fix (Kolter & Jaakkola 2012) was to model each source as a state chain
over time. Here a "source" is one team's slot at one position, e.g. team 1's
kicker, and its state each week is WHICH PLAYER filled it.

That matters because ESPN's deletions cluster: 2014 team 1 is missing its kicker
in eight separate weeks. Independently those are eight guesses. As a sequence they
are close to determined, because managers hold kickers - so a path that reuses one
player is far cheaper than one that switches every week.

    cost(path) = sum_w  -log P(player_w | features)          emission
               + sum_w  lambda * [player_w != player_{w-1}]  transition

lambda is calibrated by ablation in fhmm_calibrate.py, never guessed. lambda = 0
reduces exactly to the per-slot solver, which is the baseline it must beat.
"""
import collections

import numpy as np

import lineup_model
from lineup_model import featurise, predict

TEMPLATE = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'D/ST': 1}
FLEXIBLE = ('RB', 'WR', 'TE')
# The robust component: our engines are not equally exact, so the tolerance for
# "this player's score matches the residual" is per position, set from measured
# accuracy (offense 94.7-97.1%, kickers 100%, D/ST 91.0-96.8%).
TOL = {'K': 0.05, 'QB': 0.05, 'RB': 0.05, 'WR': 0.05, 'TE': 0.05, 'D/ST': 1.0}
MAX_TUPLES = 20000


def build_holes(known, targets, scores):
    """(week, team) -> (residual, [open positions], set of known player ids)."""
    by_week_pos = collections.defaultdict(list)
    for (week, pid), (points, pos) in scores.items():
        by_week_pos[(week, pos)].append((points, pid))

    holes = {}
    for (week, team), rows in known.items():
        if all(r[3] for r in rows) or (week, team) not in targets:
            continue
        open_slots = 9 - len(rows)
        if open_slots < 1:
            continue
        residual = round(targets[(week, team)] - sum(r[2] for r in rows), 2)
        if residual <= 0:
            continue
        counts = collections.Counter(r[1] for r in rows)
        missing = [p for p, n in TEMPLATE.items()
                   for _ in range(max(0, n - counts.get(p, 0)))]
        while len(missing) < open_slots:
            missing.append('FLEX')
        if len(missing) > open_slots:
            continue                      # shape we cannot pin down
        holes[(week, team)] = (residual, missing, {r[0] for r in rows})
    return holes, by_week_pos


def candidates_for(week, position, residual, on_roster, elsewhere, by_week_pos):
    wanted = FLEXIBLE if position == 'FLEX' else (position,)
    tol = max(TOL.get(p, 0.05) for p in wanted)
    out = []
    for pos in wanted:
        for points, pid in by_week_pos.get((week, pos), ()):
            if abs(points - residual) > tol or pid in on_roster or pid in elsewhere:
                continue
            out.append((pid, points, pos))
    return out


def tuples_for(week, positions, residual, on_roster, elsewhere, by_week_pos):
    """Assignments of players to >1 open slots whose scores sum to the residual."""
    if len(positions) == 1:
        return [(c,) for c in candidates_for(week, positions[0], residual,
                                             on_roster, elsewhere, by_week_pos)]
    if len(positions) > 2:
        return []                         # 3+ open slots: enumeration blows up
    first, second = positions
    tol = max(TOL.get(p, 0.05) for p in (FLEXIBLE if first == 'FLEX' else (first,)))
    pool_a = candidates_for(week, first, residual, on_roster, elsewhere, by_week_pos) \
        if False else None
    # any split of the residual, so filter by "not more than the residual" instead
    def pool(position):
        wanted = FLEXIBLE if position == 'FLEX' else (position,)
        out = []
        for pos in wanted:
            for points, pid in by_week_pos.get((week, pos), ()):
                if pid in on_roster or pid in elsewhere:
                    continue
                if points > residual + tol or points < -tol:
                    continue
                out.append((pid, points, pos))
        return out

    a, b = pool(first), pool(second)
    out, seen = [], set()
    for pid_a, pts_a, pos_a in a:
        need = residual - pts_a
        for pid_b, pts_b, pos_b in b:
            if pid_b == pid_a or abs(pts_b - need) > tol:
                continue
            key = tuple(sorted((pid_a, pid_b)))
            if key in seen:
                continue
            seen.add(key)
            out.append(((pid_a, pts_a, pos_a), (pid_b, pts_b, pos_b)))
            if len(out) >= MAX_TUPLES:
                return out
    return out


def viterbi(states_by_week, emission, lam):
    """Min-cost path through per-week state lists. Returns (path, total cost)."""
    weeks = sorted(states_by_week)
    if not weeks:
        return {}, 0.0
    first = weeks[0]
    cost = {i: emission[(first, s)] for i, s in enumerate(states_by_week[first])}
    back = {i: None for i in cost}
    prev_states = states_by_week[first]

    trail = [(first, dict(cost), dict(back), prev_states)]
    for week in weeks[1:]:
        states = states_by_week[week]
        new_cost, new_back = {}, {}
        for j, state in enumerate(states):
            best, arg = None, None
            for i, old in enumerate(prev_states):
                # a held slot costs nothing; any change costs lambda per changed player
                changed = len(set(p for p, _pt, _po in state)
                              ^ set(p for p, _pt, _po in old)) // 2
                c = cost[i] + lam * changed
                if best is None or c < best:
                    best, arg = c, i
            new_cost[j] = best + emission[(week, state)]
            new_back[j] = arg
        cost, back, prev_states = new_cost, new_back, states
        trail.append((week, dict(cost), dict(back), states))

    end = min(cost, key=cost.get)
    total = cost[end]
    path, idx = {}, end
    for week, _c, bk, states in reversed(trail):
        path[week] = states[idx]
        idx = bk[idx]
        if idx is None and week != trail[0][0]:
            idx = 0
    return path, total


def solve(season, known, targets, scores, beta, lam, max_repairs=10):
    """Assign players to every hole. Returns [(week, team, pid, pos, points, prob, meta)]."""
    holes, by_week_pos = build_holes(known, targets, scores)
    if not holes:
        return []

    pool = lineup_model.load_pool(season)
    production = lineup_model.production_index(scores)
    position_of = {pid: pos for (_w, pid), (_pts, pos) in scores.items()}
    starts = collections.defaultdict(set)
    team_starts = collections.defaultdict(collections.Counter)
    started_anywhere = collections.defaultdict(set)
    for (week, team), rows in known.items():
        for pid, _s, _p, _c in rows:
            starts[(team, week)].add(pid)
            team_starts[team][pid] += 1
            started_anywhere[week].add(pid)
    weeks_in_season = sorted({w for w, _t in known})

    drafted = collections.defaultdict(set)

    # cluster = (team, positions-signature); its chain runs over the weeks it appears
    clusters = collections.defaultdict(dict)
    for (week, team), (residual, positions, on_roster) in holes.items():
        clusters[(team, tuple(sorted(positions)))][week] = (residual, positions, on_roster)

    banned = collections.defaultdict(set)          # (week) -> pids taken by another team
    assignment = {}

    for _ in range(max_repairs):
        assignment, path_cost = {}, {}
        for (team, _sig), weeks in clusters.items():
            states_by_week, emission = {}, {}
            for week, (residual, positions, on_roster) in sorted(weeks.items()):
                elsewhere = (started_anywhere[week] - on_roster) | banned[(week, team)]
                states = tuples_for(week, positions, residual, on_roster,
                                    elsewhere, by_week_pos)
                if not states:
                    continue
                cover = collections.Counter()
                for state in states:
                    for pid, _pt, _po in state:
                        cover[pid] += 1
                ctx = {'pool': pool, 'team': team, 'week': week, 'starts': starts,
                       'team_starts': team_starts, 'weeks': len(weeks_in_season),
                       'drafted': drafted, 'cover': cover, 'production': production, 'position_of': position_of,
                       'is_flex': 'FLEX' in positions}
                pids = [s[0][0] for s in states]
                X = np.array([featurise(pid, ctx) for pid in pids])
                probs = predict(X, beta)
                for state, p in zip(states, probs):
                    emission[(week, state)] = -np.log(max(p, 1e-9))
                states_by_week[week] = states
            if not states_by_week:
                continue
            path, total = viterbi(states_by_week, emission, lam)
            for week, state in path.items():
                assignment[(week, team)] = state
                path_cost[(week, team)] = total

        # exclusivity repair: one player cannot start for two teams in the same week
        claims = collections.defaultdict(list)
        for (week, team), state in assignment.items():
            for pid, _pt, _po in state:
                claims[(week, pid)].append(team)
        conflicts = {k: v for k, v in claims.items() if len(v) > 1}
        if not conflicts:
            break
        for (week, pid), teams in conflicts.items():
            keep = min(teams, key=lambda t: path_cost.get((week, t), 1e9))
            for team in teams:
                if team != keep:
                    banned[(week, team)].add(pid)

    out = []
    for (week, team), state in sorted(assignment.items()):
        for pid, points, pos in state:
            out.append({'season': season, 'week': week, 'team_id': team,
                        'player_id': pid, 'slot': pos, 'points': points,
                        'slots': len(state)})
    return out
