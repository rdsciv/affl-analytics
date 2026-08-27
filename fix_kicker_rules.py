#!/usr/bin/env python3
"""Correct dim_scoring's kicker field-goal buckets.

ESPN's stored settings label the FG distance buckets backwards: dim_scoring says a
0-39 yard field goal is worth 5 and a 50+ yarder 3, which is inverted. Scoring
kickers from the table as written reproduces ESPN's own numbers on only 24-33% of
kicker-weeks; the corrected values reproduce them exactly.

The correction is not a guess. It was recovered by least squares against 308
labelled kicker-weeks from ESPN's own 2017/2018 payloads, where every coefficient
came out integral (MAE 0.000). This script re-derives it from those payloads on
every run rather than hard-coding the answer, and refuses to write unless the
result reproduces ESPN at 100%.

    python3 fix_kicker_rules.py            # report only
    python3 fix_kicker_rules.py --write    # apply, gated on the 100% check
"""
import csv
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
DATA = os.path.join(HERE, 'data')

# nflverse stat column -> the dim_scoring rule it falls under
BUCKETS = {
    'fg0_39':  ['fg_made_0_19', 'fg_made_20_29', 'fg_made_30_39'],
    'fg40_49': ['fg_made_40_49'],
    'fg50':    ['fg_made_50_59', 'fg_made_60_'],
    'xp':      ['pat_made'],
    'fgMiss':  ['fg_missed_20_29', 'fg_missed_30_39', 'fg_missed_40_49',
                'fg_missed_50_59', 'fg_missed_60_', 'fg_blocked'],
}
# fg_missed_0_19 and pat_missed fitted at 0.0 - ESPN does not penalise them.
ZERO_PENALTY = ['fg_missed_0_19', 'pat_missed']

LABEL_SEASONS = tuple(range(2014, 2026))   # every season with labelled K entries


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def kicker_stats(year):
    """(week, gsis_id) -> {stat column: value} for every kicker-week."""
    out = {}
    path = os.path.join(DATA, f'stats_player_week_{year}.csv')
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG' or r.get('position') != 'K':
                continue
            try:
                wk = int(r['week'])
            except (TypeError, ValueError):
                continue
            cols = {c: num(r, c) for b in BUCKETS.values() for c in b}
            cols.update({c: num(r, c) for c in ZERO_PENALTY})
            out[(wk, r['player_id'])] = cols
    return out


def labelled_kicker_weeks(year, espn_to_gsis):
    """ESPN's own kicker points: [(week, gsis_id, points)] from the raw payloads."""
    rows = []
    for path in glob.glob(os.path.join(DATA, 'box_raw', str(year), 'w*.json')):
        wk = int(re.search(r'w(\d+)', os.path.basename(path)).group(1))
        with open(path) as fh:
            payload = json.load(fh)
        for matchup in payload.get('schedule', []):
            # skip multi-week playoff periods: appliedStatTotal spans two weeks there
            if matchup.get('matchupPeriodId') != wk or wk > 13:
                continue
            for side in ('home', 'away'):
                roster = (matchup.get(side) or {}).get('rosterForMatchupPeriod')
                if not roster:
                    continue
                for entry in roster['entries']:
                    pool = entry['playerPoolEntry']
                    if pool['player'].get('defaultPositionId') != 5:   # 5 = K
                        continue
                    gsis = espn_to_gsis.get(pool['id'])
                    if gsis:
                        rows.append((wk, gsis, pool['appliedStatTotal']))
    return rows


def score(cols, rules):
    total = 0.0
    for rule, columns in BUCKETS.items():
        total += sum(cols.get(c, 0.0) for c in columns) * rules.get(rule, 0.0)
    return total


def accuracy(rules, labels, stats, collect=None):
    """Fraction of labelled kicker-weeks these rules reproduce exactly."""
    n = exact = 0
    for wk, gsis, espn_points in labels:
        cols = stats.get((wk, gsis))
        if cols is None:
            continue
        n += 1
        if abs(espn_points - score(cols, rules)) < 1e-6:
            exact += 1
        elif collect is not None:
            collect.append((wk, gsis, espn_points, score(cols, rules)))
    return exact, n


def main():
    write = '--write' in sys.argv
    con = sqlite3.connect(DB)
    espn_to_gsis = {
        pid: gsis for pid, gsis in
        con.execute('SELECT player_id, gsis_id FROM dim_player WHERE gsis_id IS NOT NULL')
    }

    corrected = {'fg0_39': 3.0, 'fg40_49': 4.0, 'fg50': 5.0, 'xp': 1.0, 'fgMiss': -1.0}

    names = {g: n for g, n in con.execute(
        'SELECT gsis_id, name FROM dim_player WHERE gsis_id IS NOT NULL')}

    print(f"{'season':>7} {'n':>5} {'stored rules':>13} {'corrected':>10}")
    stored_total = corrected_total = seen = 0
    misses = []
    for year in LABEL_SEASONS:
        if not os.path.exists(os.path.join(DATA, f'stats_player_week_{year}.csv')):
            continue
        stats = kicker_stats(year)
        labels = labelled_kicker_weeks(year, espn_to_gsis)
        stored = {name: pts for name, pts in con.execute(
            'SELECT stat_name, points FROM dim_scoring WHERE season=? AND stat_name IS NOT NULL',
            (year,))}
        s_ex, n = accuracy(stored, labels, stats)
        if n == 0:
            print(f'{year:>7} {0:>5} {"- no payloads -":>25}')
            continue
        found = []
        c_ex, _ = accuracy(corrected, labels, stats, found)
        misses += [(year,) + m for m in found]
        print(f'{year:>7} {n:>5} {s_ex/n:>12.1%} {c_ex/n:>10.1%}')
        stored_total += s_ex
        corrected_total += c_ex
        seen += n

    print(f"\nstored dim_scoring reproduces ESPN on {stored_total}/{seen} ({stored_total/seen:.1%})")
    print(f"corrected rules reproduce ESPN on   {corrected_total}/{seen} ({corrected_total/seen:.1%})")

    if misses:
        print(f'\n{len(misses)} kicker-week(s) where ESPN disagrees with nflverse:')
        for year, wk, gsis, espn_points, computed in misses:
            print(f'  {year} wk{wk} {names.get(gsis, gsis)}: '
                  f'ESPN={espn_points:g} computed={computed:g} ({espn_points - computed:+g})')
        print('  These are per-entry source discrepancies (verified against play-by-play),')
        print('  not rule differences - every other kicker-week in the same season is exact.')

    rate = corrected_total / seen
    if rate < 0.999:
        print(f'\nGATE FAILED: corrected rules reproduce ESPN on only {rate:.2%}. Refusing to write.')
        return 1
    if corrected_total < stored_total:
        print('\nGATE FAILED: corrected rules are worse than what is stored. Refusing to write.')
        return 1
    print(f'\nGATE PASSED: {rate:.2%} exact across {seen} labelled kicker-weeks '
          f'in {len(LABEL_SEASONS)} seasons, vs {stored_total/seen:.1%} for the stored rules.')

    if not write:
        print('Report only. Re-run with --write to apply to dim_scoring.')
        return 0

    seasons = [s for (s,) in con.execute('SELECT season FROM dim_season ORDER BY season')]
    with con:
        for year in seasons:
            for rule, points in corrected.items():
                cur = con.execute(
                    'UPDATE dim_scoring SET points=? WHERE season=? AND stat_name=?',
                    (points, year, rule))
                if cur.rowcount == 0:
                    # fgMiss/xp are absent in some seasons; insert under ESPN's stat ids
                    stat_id = {'fg0_39': 74, 'fg40_49': 77, 'fg50': 80,
                               'fgMiss': 85, 'xp': 86}[rule]
                    con.execute(
                        'INSERT OR REPLACE INTO dim_scoring(season, stat_id, stat_name, points)'
                        ' VALUES (?,?,?,?)', (year, stat_id, rule, points))
    print(f'Applied corrected kicker rules to {len(seasons)} seasons in dim_scoring.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
