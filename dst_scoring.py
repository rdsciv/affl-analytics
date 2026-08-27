#!/usr/bin/env python3
"""Compute weekly D/ST fantasy points from nflverse play-by-play.

Why this exists: dim_scoring carries no defensive rules at all before 2020, yet
D/ST started every week and averaged 7.4 points in 2018. Without this module the
pre-2018 backfill has an unscoreable ~8 points per team-week.

The rules are not guessed. ESPN's 2018+ payloads carry an `appliedStats` block -
the per-stat points breakdown beside the raw stats - so RULES below is read
directly out of ESPN's own scoring output (1,385 D/ST entries, 2018-2025, every
statId mapping to exactly one value, identical in all eight seasons). Tier
boundaries were derived empirically from the range of the raw stat when each tier
fired, not assumed.

Each play-by-play input below was validated against ESPN's own weekly raw stat
for the same statId on 2018 (190 D/ST weeks):

    sack 100.0%   INT 100.0%   fumble rec 100.0%   blocked kick 100.0%
    safety 99.5%  yards allowed 98.4%   def/ST TD 98.9%   points allowed 96.3%

A third non-obvious definition: on kickoffs nflverse sets posteam to the RECEIVING
team, so a kick-return touchdown has td_team == posteam and is invisible to the
natural "scorer != posteam" test. Return TDs need the return_touchdown flag too.

Two definitions are non-obvious and were established by measurement:
  * A fumble recovery is team-centric - recovering an opponent's fumble whether
    on defense OR special teams. The natural `fumble_lost & defteam` reading
    scores only 93.7%; this scores 100%.
  * Points allowed excludes only what the opponent's DEFENCE returned for a score
    (pick-six, fumble-six) - those points were conceded by this team's offence, not
    its defence. Kick and punt return TDs are still charged. Using the raw final
    score scores 87.4%; excluding defensive returns only scores 96.3%; excluding
    every non-offensive score over-subtracts and regresses it again.
"""
import csv
import gzip
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PBP = os.path.join(HERE, 'data', 'pbp')

# statId -> points, read from ESPN's appliedStats. Stable across 2018-2025.
RULES = {
    'sack': 1.0,        # 99
    'int': 2.0,         # 95
    'fumrec': 2.0,      # 96
    'safety': 2.0,      # 98
    'blocked_kick': 2.0,  # 97
    'td': 6.0,          # 93 / 101 / 102 / 103 / 104
}
# (upper bound inclusive, points). Boundaries derived from the observed range of
# statId 120 / 127 when each tier statId fired.
PA_TIERS = [(0, 5.0), (6, 4.0), (13, 3.0), (17, 1.0), (27, 0.0),
            (34, -1.0), (45, -3.0), (10 ** 9, -5.0)]
YA_TIERS = [(99, 5.0), (199, 3.0), (299, 2.0), (349, 0.0), (399, -1.0),
            (449, -3.0), (499, -5.0), (549, -6.0), (10 ** 9, -7.0)]

SCRIMMAGE = ('pass', 'run', 'qb_kneel', 'qb_spike')


def _tier(value, tiers):
    for bound, points in tiers:
        if value <= bound:
            return points
    return tiers[-1][1]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def team_weeks(season):
    """(week, team) -> dict of validated D/ST scoring inputs for one season."""
    stats = {}
    finals = {}

    def slot(week, team):
        if not team:
            return None
        return stats.setdefault((week, team), {
            'sack': 0.0, 'int': 0.0, 'fumrec': 0.0, 'safety': 0.0,
            'blocked_kick': 0.0, 'td': 0.0, 'yards_allowed': 0.0,
            'nonoffensive_points': 0.0,
        })

    with gzip.open(os.path.join(PBP, f'play_by_play_{season}.csv.gz'),
                   'rt', newline='') as fh:
        for row in csv.DictReader(fh):
            if row.get('season_type') != 'REG':
                continue
            try:
                week = int(row['week'])
            except (TypeError, ValueError, KeyError):
                continue

            finals[row['game_id']] = (
                row['home_team'], row['away_team'],
                _num(row['total_home_score']), _num(row['total_away_score']), week)

            offense, defense = row.get('posteam'), row.get('defteam')
            play = row.get('play_type') or ''

            if offense and defense:
                d = slot(week, defense)
                d['sack'] += _num(row['sack'])
                d['int'] += _num(row['interception'])
                d['safety'] += _num(row['safety'])
                if play in SCRIMMAGE and _num(row.get('two_point_attempt')) != 1:
                    d['yards_allowed'] += _num(row['yards_gained'])

            # team-centric: recovering an opponent's fumble, defence or special teams
            recovered = row.get('fumble_recovery_1_team') or ''
            fumbled = row.get('fumbled_1_team') or ''
            if recovered and fumbled and recovered != fumbled:
                slot(week, recovered)['fumrec'] += 1

            # A D/ST is credited with any touchdown its offence did not score:
            # defensive returns (scorer != posteam) and kick returns. On kickoffs
            # nflverse sets posteam to the RECEIVING team, so a kick-return TD has
            # scorer == posteam and is only caught by the return_touchdown flag.
            scorer = row.get('td_team') or ''
            if scorer and _num(row['touchdown']) == 1 and offense:
                if scorer != offense or _num(row.get('return_touchdown')) == 1:
                    slot(week, scorer)['td'] += 1
                # Only a turnover returned by the DEFENCE relieves the opposing
                # defence of those points. A kick or punt return TD is still
                # charged to the conceding team's points allowed - measured, and
                # the reason this is separate from the credit above.
                if scorer != offense and play in ('pass', 'run'):
                    slot(week, scorer)['nonoffensive_points'] += 6
            if _num(row['safety']) == 1 and defense:
                slot(week, defense)['nonoffensive_points'] += 2

            for blocked in (row.get('field_goal_result') == 'blocked',
                            row.get('extra_point_result') == 'blocked',
                            (row.get('punt_blocked') or '') not in ('', '0', '0.0')):
                if blocked and defense:
                    slot(week, defense)['blocked_kick'] += 1

    for _, (home, away, home_pts, away_pts, week) in finals.items():
        for team, conceded, opponent in ((home, away_pts, away), (away, home_pts, home)):
            d = slot(week, team)
            if d is not None:
                d['points_allowed'] = conceded
                d['opponent'] = opponent
    return stats


def score(entry, opponent_entry):
    """Fantasy points for one D/ST team-week."""
    total = sum(entry[k] * v for k, v in RULES.items())
    # ESPN charges a defence only with points its own side conceded on offence
    conceded = entry.get('points_allowed', 0.0)
    if opponent_entry:
        conceded -= opponent_entry.get('nonoffensive_points', 0.0)
    return (total + _tier(conceded, PA_TIERS)
            + _tier(entry['yards_allowed'], YA_TIERS))


def season_scores(season):
    """(week, team) -> fantasy points, for every team-week in a season."""
    stats = team_weeks(season)
    out = {}
    for key, entry in stats.items():
        week, _ = key
        opponent = entry.get('opponent')
        out[key] = score(entry, stats.get((week, opponent)) if opponent else None)
    return out
