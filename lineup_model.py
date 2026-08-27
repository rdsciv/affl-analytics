#!/usr/bin/env python3
"""A conditional-logit model for identifying the starter ESPN deleted.

The previous solver was a hand-ordered cascade: filter to an exact score match,
then break ties by continuity, then by popularity. The ordering was invented, the
weights were implicit, and its confidence labels were not probabilities.

The problem is a discrete choice: within one open slot, several players score
exactly the residual and EXACTLY ONE of them actually started. That is what
conditional logit models. Each candidate i gets a utility b.x_i and

    P(i is the starter) = exp(b.x_i) / sum_j exp(b.x_j)

The weights b are learned, not asserted, by maximising the log-likelihood of the
true starter across thousands of real choice sets - and because the denominator
runs over that slot's candidates, the model is calibrated per slot rather than in
the abstract.

Training data is free: 2017 and 2018 are complete and verified, so holes can be
punched and the answer is known. Evaluation is always on the season NOT trained
on.

Features, all observable for 2014-2016:
    pct_started     ESPN's season-specific share of leagues starting the player
    pct_owned       season-specific ownership
    adp             average draft position, inverted (earlier pick = stronger)
    prev_week       this team started him the previous week
    next_week       this team started him the following week
    season_starts   share of the season he started for this team
    drafted_here    this team drafted him
    cluster_cover   weeks in this team's run of holes his scores could fill
    is_flex         he is filling a FLEX rather than a named slot
"""
import collections
import json
import math
import os
import sqlite3

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

FEATURES = ['pct_started', 'pct_owned', 'adp', 'prev_week', 'next_week',
            'season_starts', 'drafted_here', 'cluster_cover', 'is_flex',
            'season_points', 'games_scored', 'pos_rank', 'flex_fit']


def load_pool(season):
    path = os.path.join(HERE, 'data', f'player_pool_{season}.json')
    if not os.path.exists(path):
        return {}
    out = {}
    for player in json.load(open(path)):
        own = player.get('ownership') or {}
        adp = own.get('averageDraftPosition') or 0.0
        out[player['id']] = (
            own.get('percentStarted') or 0.0,
            own.get('percentOwned') or 0.0,
            adp,
        )
    return out


# Who actually occupies a FLEX slot, measured from ESPN's own 2018-2025 data:
# WR 53.0%, RB 46.4%, TE 0.6%. RB/WR/TE are all *eligible* for the FLEX, so the
# candidate pool for a FLEX hole is roughly a third tight ends - but a tight end is
# almost never the player who was actually flexed. Without this the model treats
# eligibility as if it were likelihood.
FLEX_USAGE = {'WR': 0.530, 'RB': 0.464, 'TE': 0.006}


def production_index(scores):
    """pid -> (season points, weeks scored, rank within position as 0..1)."""
    totals, games, position = {}, {}, {}
    for (_week, pid), (points, pos) in scores.items():
        totals[pid] = totals.get(pid, 0.0) + points
        games[pid] = games.get(pid, 0) + 1
        position[pid] = pos
    by_pos = {}
    for pid, pos in position.items():
        by_pos.setdefault(pos, []).append((totals[pid], pid))
    rank = {}
    for pos, rows in by_pos.items():
        rows.sort(reverse=True)
        for i, (_t, pid) in enumerate(rows):
            rank[pid] = i / max(1, len(rows) - 1)
    return {pid: (totals[pid], games[pid], rank[pid]) for pid in totals}


def featurise(pid, ctx):
    """Feature vector for one candidate in one choice set."""
    started, owned, adp = ctx['pool'].get(pid, (0.0, 0.0, 0.0))
    # Season-long production separates a real starting tight end from a fringe one
    # who happened to match the residual once. Ownership only covers ~1,000 of the
    # 7,800 players in the pool; this covers everyone who scored at all.
    season_points, games, pos_rank = ctx['production'].get(pid, (0.0, 0.0, 1.0))
    # only informative for a FLEX hole; a named slot admits one position anyway
    if ctx['is_flex']:
        position = ctx.get('position_of', {}).get(pid)
        flex_fit = math.log(FLEX_USAGE.get(position, 0.01))
    else:
        flex_fit = 0.0
    team, week = ctx['team'], ctx['week']
    prev = 1.0 if pid in ctx['starts'].get((team, week - 1), ()) else 0.0
    nxt = 1.0 if pid in ctx['starts'].get((team, week + 1), ()) else 0.0
    season_starts = ctx['team_starts'][team].get(pid, 0) / max(1, ctx['weeks'])
    drafted = 1.0 if pid in ctx['drafted'].get(team, ()) else 0.0
    cover = ctx['cover'].get(pid, 0) / 8.0
    return [
        math.log1p(started),
        math.log1p(owned),
        -math.log1p(adp) if adp else 0.0,   # earlier ADP = stronger
        prev,
        nxt,
        season_starts,
        drafted,
        cover,
        1.0 if ctx['is_flex'] else 0.0,
        math.log1p(max(0.0, season_points)) / 5.0,
        games / 17.0,
        -pos_rank,                       # 0 = best at the position, 1 = worst
        flex_fit,
    ]


def fit(choice_sets, epochs=400, lr=0.5, l2=1e-3, seed=0):
    """Maximise conditional-logit log-likelihood by gradient ascent."""
    rng = np.random.default_rng(seed)
    beta = rng.normal(0, 0.01, len(FEATURES))
    for _ in range(epochs):
        grad = np.zeros_like(beta)
        for X, truth in choice_sets:
            u = X @ beta
            u -= u.max()
            p = np.exp(u)
            p /= p.sum()
            grad += X[truth] - p @ X          # d/db of log P(true)
        grad = grad / max(1, len(choice_sets)) - l2 * beta
        beta += lr * grad
    return beta


def predict(X, beta):
    u = X @ beta
    u -= u.max()
    p = np.exp(u)
    return p / p.sum()


def report(beta):
    order = np.argsort(-np.abs(beta))
    print(f"\n{'feature':>15} {'weight':>8}")
    for i in order:
        print(f'{FEATURES[i]:>15} {beta[i]:>+8.3f}')
