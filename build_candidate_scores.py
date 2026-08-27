#!/usr/bin/env python3
"""Weekly fantasy points for EVERY scoreable player, 2014-2017.

This is the candidate universe the lineup solver searches. A missing starter can
only be a player whose actual week-N score equals the residual, so we need every
player's score, not just the ones we know started.

Three engines, each already validated against ESPN's own numbers:
  offense  fact_nfl_week + dim_scoring, BUCKET yardage   94.7-97.1% exact
  kickers  FG distance buckets, corrected rules          100.0% exact
  D/ST     dst_scoring.py from play-by-play              91.0-96.8% exact
"""
import csv
import math
import os
import sqlite3

import dst_scoring

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
# ESPN D/ST player ids are -16000 minus the pro team id
ESPN_PRO_TEAM = {
    1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET',
    9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC', 13: 'OAK', 14: 'STL', 15: 'MIA',
    16: 'MIN', 17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI',
    23: 'PIT', 24: 'SD', 25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WAS', 29: 'CAR',
    30: 'JAX', 33: 'BAL', 34: 'HOU',
}


def offense_scores(con, season):
    """(week, espn_player_id) -> (points, position) for QB/RB/WR/TE."""
    rules = {n: p for n, p in con.execute(
        'SELECT stat_name, points FROM dim_scoring WHERE season=? AND stat_name IS NOT NULL',
        (season,))}
    gsis_to_espn = {}
    position = {}
    for pid, gsis, pos in con.execute(
            'SELECT player_id, gsis_id, position FROM dim_player WHERE gsis_id IS NOT NULL'):
        gsis_to_espn[gsis] = pid
        position[pid] = pos
    out = {}
    for row in con.execute(
            'SELECT week, gsis_id, pass_yards, pass_tds, interceptions, rush_yards,'
            ' rush_tds, rec_yards, rec_tds, fumbles_lost, two_pt'
            '  FROM fact_nfl_week WHERE season=?', (season,)):
        week, gsis = row[0], row[1]
        pid = gsis_to_espn.get(gsis)
        if pid is None or position.get(pid) not in ('QB', 'RB', 'WR', 'TE'):
            continue
        v = [x or 0 for x in row[2:]]
        points = (math.floor(v[0] / 25) + math.floor(v[3] / 10) + math.floor(v[5] / 10)
                  + v[1] * rules.get('passTD', 0) + v[2] * rules.get('passInt', 0)
                  + v[4] * rules.get('rushTD', 0) + v[6] * rules.get('recTD', 0)
                  + v[7] * rules.get('fumLost', 0) + v[8] * rules.get('rush2pt', 0))
        out[(week, pid)] = (points, position[pid])
    return out


def kicker_scores(con, season):
    rules = {n: p for n, p in con.execute(
        'SELECT stat_name, points FROM dim_scoring WHERE season=? AND stat_name IS NOT NULL',
        (season,))}
    gsis_to_espn = {g: p for p, g in con.execute(
        'SELECT player_id, gsis_id FROM dim_player WHERE gsis_id IS NOT NULL')}
    out = {}
    with open(os.path.join(DATA, f'stats_player_week_{season}.csv'), newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG' or r.get('position') != 'K':
                continue
            pid = gsis_to_espn.get(r['player_id'])
            if pid is None:
                continue
            g = lambda k: float(r.get(k) or 0)
            points = ((g('fg_made_0_19') + g('fg_made_20_29') + g('fg_made_30_39')) * rules.get('fg0_39', 3)
                      + g('fg_made_40_49') * rules.get('fg40_49', 4)
                      + (g('fg_made_50_59') + g('fg_made_60_')) * rules.get('fg50', 5)
                      + (g('fg_missed_20_29') + g('fg_missed_30_39') + g('fg_missed_40_49')
                         + g('fg_missed_50_59') + g('fg_missed_60_') + g('fg_blocked'))
                      * rules.get('fgMiss', -1)
                      + g('pat_made') * rules.get('xp', 1))
            out[(int(r['week']), pid)] = (points, 'K')
    return out


def dst_scores(season):
    out = {}
    team_to_espn = {code: -16000 - pro for pro, code in ESPN_PRO_TEAM.items()}
    for (week, team), points in dst_scoring.season_scores(season).items():
        pid = team_to_espn.get(team)
        if pid is not None:
            out[(week, pid)] = (points, 'D/ST')
    return out


def all_scores(con, season):
    """(week, espn_player_id) -> (points, position) across every scoreable player."""
    scores = offense_scores(con, season)
    scores.update(kicker_scores(con, season))
    scores.update(dst_scores(season))
    return scores


if __name__ == '__main__':
    con = sqlite3.connect(os.path.join(HERE, 'affl.db'))
    for season in (2014, 2015, 2016):
        s = all_scores(con, season)
        by_pos = {}
        for (_w, _p), (_pts, pos) in s.items():
            by_pos[pos] = by_pos.get(pos, 0) + 1
        print(f'{season}: {len(s)} player-weeks scored  {by_pos}')
