#!/usr/bin/env python3
"""Recover the starters ESPN deleted from 2014-2016 lineups.

WRITES ONLY TO affl_reconstruct.db. Nothing here is fact and none of it may reach
affl.db.

The setup, after loading every starter ESPN still returns:

  * 92% of starter slots are already known, so for a team-week missing a starter
    we know the other 6-8 players, the exact residual R the missing slot must
    account for, and which POSITION is missing.
  * A candidate must therefore be a player at that position whose actual week-N
    score is exactly R. That alone is usually a handful of players.

What separates them is continuity, which is now measurable because the
surrounding weeks are known:

  anchored   the same team started this player in BOTH the previous and the
             following week. To be wrong, the manager must have dropped and
             re-added the same player around a week he was not started - while
             someone else at the same position scored exactly R. Kickers and
             defences are held for weeks at a time, which is why this is
             strongest exactly where the holes are.
  adjacent   started by this team in one neighbouring week.
  rostered   started by this team at some other point in the season.
  free       never seen on this team - weakest, an in-week pickup.

Exclusivity prunes first: a player started by ANOTHER team that week cannot also
have been on this roster.

A slot is CERTAIN only when exactly one candidate survives every filter. Where
several survive they are ranked and stored as PROBABLE with the count, so nothing
is silently promoted.
"""
import collections
import os
import sqlite3
import sys

import json

import build_candidate_scores

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, 'affl.db')
FORK = os.path.join(HERE, 'affl_reconstruct.db')
SEASONS = (2014, 2015, 2016)
TEMPLATE = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'D/ST': 1}
FLEXIBLE = ('RB', 'WR', 'TE')
TOLERANCE = 0.05

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_roster_week_reconstructed (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  slot            TEXT    NOT NULL,
  points          REAL    NOT NULL,
  confidence      TEXT    NOT NULL,   -- CERTAIN | PROBABLE
  evidence        TEXT    NOT NULL,   -- anchored | adjacent | rostered | free
  solutions_found INTEGER NOT NULL,
  method          TEXT    NOT NULL,
  PRIMARY KEY (season, week, team_id, player_id)
)
"""


def ownership_prior(season):
    """espn player id -> how widely started that season, from ESPN's own pool.

    ESPN keeps historical ownership per season (percentStarted, percentOwned and
    ADP are all season-specific - a 2014 backup shows 0.09% owned with a 170 ADP).
    Among players actually started in 2014 the median percentOwned is 0.22; among
    everyone else it is 0.00. When several players at a position happen to score
    exactly the residual, this is what separates the plausible starter from the
    practice-squad name who matched by arithmetic accident.
    """
    path = os.path.join(HERE, 'data', f'player_pool_{season}.json')
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        pool = json.load(fh)
    out = {}
    for player in pool:
        own = player.get('ownership') or {}
        out[player['id']] = (own.get('percentStarted') or 0.0,
                             own.get('percentOwned') or 0.0)
    return out


def evidence_rank(started_by_team, team, week, pid):
    prev = pid in started_by_team.get((team, week - 1), ())
    nxt = pid in started_by_team.get((team, week + 1), ())
    if prev and nxt:
        return 0, 'anchored'
    if prev or nxt:
        return 1, 'adjacent'
    for (t, _w), players in started_by_team.items():
        if t == team and pid in players:
            return 2, 'rostered'
    return 3, 'free'


def solve_season(con, season, scores):
    known = collections.defaultdict(list)      # (week, team) -> [(pid, pos, pts)]
    for week, team, pid, slot, pts, complete in con.execute(
            'SELECT week, team_id, player_id, slot, points, lineup_complete'
            '  FROM fact_roster_week WHERE season=? AND started=1', (season,)):
        known[(week, team)].append((pid, slot, pts, complete))
    targets = {(w, t): p for w, t, p in con.execute(
        'SELECT week, team_id, points FROM fact_matchup WHERE season=?', (season,))}
    return solve(season, known, targets, scores)


def solve(season, known, targets, scores, prior=None):
    """Core solver. `known` maps (week, team) -> [(pid, slot, points, complete)].

    Kept free of database access so the ablation harness can drive exactly this
    code with holes punched in a season whose truth we already have.
    """
    started_by_team = collections.defaultdict(set)
    started_anywhere = collections.defaultdict(set)   # week -> {pid}
    for (week, team), rows in known.items():
        for pid, _slot, _pts, _c in rows:
            started_by_team[(team, week)].add(pid)
            started_anywhere[week].add(pid)

    if prior is None:
        prior = ownership_prior(season)

    by_week_pos = collections.defaultdict(list)       # (week, pos) -> [(pts, pid)]
    for (week, pid), (pts, pos) in scores.items():
        by_week_pos[(week, pos)].append((pts, pid))

    results, stats, pending = [], collections.Counter(), []
    for (week, team), rows in sorted(known.items()):
        if all(c for _p, _s, _pt, c in rows):
            continue                                   # lineup already complete
        target = targets.get((week, team))
        if target is None:
            continue
        residual = round(target - sum(r[2] for r in rows), 2)
        counts = collections.Counter(r[1] for r in rows)
        missing = []
        for pos, need in TEMPLATE.items():
            missing += [pos] * max(0, need - counts.get(pos, 0))
        filled = sum(counts.values())
        flex_used = sum(max(0, counts.get(p, 0) - TEMPLATE[p]) for p in FLEXIBLE)
        slots_open = 9 - filled
        stats['partial team-weeks'] += 1

        if residual <= 0 or slots_open <= 0:
            stats['no residual to explain'] += 1
            continue
        if slots_open > 2:
            stats['3+ slots open - skipped'] += 1
            continue

        # Positions still to fill. Named gaps are known; any remaining open slot
        # after those is the FLEX, which any RB/WR/TE can occupy.
        open_positions = list(missing)
        while len(open_positions) < slots_open:
            open_positions.append('FLEX')
        if len(open_positions) > slots_open:
            stats['ambiguous open position - skipped'] += 1
            continue

        on_roster = {r[0] for r in rows}
        elsewhere = started_anywhere[week] - on_roster

        def eligible(position):
            wanted = FLEXIBLE if position == 'FLEX' else (position,)
            out = []
            for pos in wanted:
                for pts, pid in by_week_pos.get((week, pos), ()):
                    if pid in on_roster or pid in elsewhere:
                        continue
                    out.append((pts, pid, pos))
            return out

        # Enumerate assignments of players to the open slots summing to R.
        solutions = []
        if slots_open == 1:
            for pts, pid, pos in eligible(open_positions[0]):
                if abs(pts - residual) <= TOLERANCE:
                    solutions.append(((pid, pts, pos),))
        else:
            first, second = open_positions
            pool_b = eligible(second)
            for pts_a, pid_a, pos_a in eligible(first):
                if pts_a > residual + TOLERANCE:
                    continue
                need = residual - pts_a
                for pts_b, pid_b, pos_b in pool_b:
                    if pid_b == pid_a or abs(pts_b - need) > TOLERANCE:
                        continue
                    pair = tuple(sorted(((pid_a, pts_a, pos_a), (pid_b, pts_b, pos_b))))
                    solutions.append(pair)
            solutions = list(dict.fromkeys(solutions))

        if not solutions:
            stats['no candidate matches residual'] += 1
            continue

        # Rank whole solutions by their best continuity evidence.
        def score_solution(solution):
            ranks = [evidence_rank(started_by_team, team, week, pid)[0]
                     for pid, _pts, _pos in solution]
            return (sum(ranks), max(ranks))

        solutions.sort(key=score_solution)
        pending.append((week, team, slots_open, open_positions, residual, solutions))

    # ---- second pass: solve each team+position CLUSTER jointly -----------------
    #
    # ESPN's holes cluster - one team missing its kicker across eight weeks. Solved
    # week by week those are eight independent guesses. Solved together they are
    # nearly determined, because managers HOLD kickers and defences: the right
    # answer is the assignment using the FEWEST distinct players. A candidate whose
    # weekly scores happen to match the residual in five of the eight weeks is
    # overwhelmingly more likely than five unrelated players who each match once.
    cluster = collections.defaultdict(list)
    for item in pending:
        week, team, slots_open, open_positions, residual, solutions = item
        if slots_open == 1:
            cluster[(team, open_positions[0])].append(item)

    coverage = {}          # (team, week, pid) -> how many weeks that pid can cover
    for (team, position), items in cluster.items():
        if len(items) < 2:
            continue
        can_cover = collections.Counter()
        for week, _t, _n, _p, _r, solutions in items:
            for solution in solutions:
                can_cover[solution[0][0]] += 1
        for week, _t, _n, _p, _r, solutions in items:
            for solution in solutions:
                pid = solution[0][0]
                coverage[(team, week, pid)] = can_cover[pid]

    for week, team, slots_open, open_positions, residual, solutions in pending:
        def rank_solution(solution):
            base = score_solution(solution)
            # more weeks covered by the same player = fewer implied transactions
            covers = max(coverage.get((team, week, pid), 0) for pid, _p, _o in solution)
            # widely-started players first when everything else ties
            popularity = sum(prior.get(pid, (0.0, 0.0))[0] + prior.get(pid, (0.0, 0.0))[1]
                             for pid, _p, _o in solution)
            return (-covers,) + base + (-popularity,)

        # Confidence is decided BEFORE the popularity prior is applied. CERTAIN has
        # to mean the constraints narrowed it to one player, not that a tiebreaker
        # picked a favourite - otherwise the label carries no information and the
        # measured accuracy of the tier collapses.
        def rank_without_prior(solution):
            covers = max(coverage.get((team, week, pid), 0) for pid, _p, _o in solution)
            return (-covers,) + score_solution(solution)

        narrowed = min(rank_without_prior(s) for s in solutions)
        contenders = [s for s in solutions if rank_without_prior(s) == narrowed]
        confidence = 'CERTAIN' if len(contenders) == 1 else 'PROBABLE'
        contenders.sort(key=rank_solution)   # among genuine ties, the prior chooses
        tied = contenders
        stats[f'solved:{confidence}'] += 1
        stats[f'slots_open={slots_open}'] += 1
        covers = max(coverage.get((team, week, pid), 0) for pid, _p, _o in tied[0])
        for pid, pts, pos in tied[0]:
            _rank, label = evidence_rank(started_by_team, team, week, pid)
            if covers >= 3 and label == 'free':
                label = 'held'          # recurs across the cluster: a held starter
            stats[f'evidence:{label}'] += 1
            results.append((season, week, team, pid, pos, pts, confidence, label,
                            len(tied), 'residual+exclusivity+continuity+cluster'))
    return results, stats


def main():
    write = '--write' in sys.argv
    con = sqlite3.connect(MAIN)
    all_results, totals = [], collections.Counter()
    for season in SEASONS:
        scores = build_candidate_scores.all_scores(con, season)
        results, stats = solve_season(con, season, scores)
        all_results += results
        totals.update(stats)
        certain = stats.get('solved:CERTAIN', 0)
        probable = stats.get('solved:PROBABLE', 0)
        print(f'{season}: {stats["partial team-weeks"]:>3} partial team-weeks -> '
              f'{certain:>3} CERTAIN, {probable:>3} PROBABLE')

    print('\nbreakdown across 2014-2016:')
    for key in sorted(totals):
        print(f'   {key:38s} {totals[key]}')

    if not write:
        print('\nReport only. Re-run with --write to load into affl_reconstruct.db.')
        return 0
    fork = sqlite3.connect(FORK)
    with fork:
        fork.execute(SCHEMA)
        # rewrite from scratch: re-runs must not accumulate answers from earlier
        # solver versions, which would silently inflate coverage
        fork.execute('DELETE FROM fact_roster_week_reconstructed WHERE season IN '
                     '(%s)' % ','.join(str(s) for s in SEASONS))
        fork.executemany(
            'INSERT OR REPLACE INTO fact_roster_week_reconstructed VALUES (?,?,?,?,?,?,?,?,?,?)',
            all_results)
    print(f'\nWrote {len(all_results)} reconstructed starters to affl_reconstruct.db')
    return 0


if __name__ == '__main__':
    sys.exit(main())
