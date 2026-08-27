#!/usr/bin/env python3
"""Load D/ST scoring rules into dim_scoring.

dim_scoring carries no defensive rules before 2020. This reads them out of the
`appliedStats` breakdown ESPN itself returns in data/box_raw (2018+), where each
statId's points-per-unit is directly observable, and records them with provenance:

    espn_appliedstats  2018-2025  read from ESPN's own scoring output
    backfilled         2014-2017  ESPN never stored rules for these seasons

The backfill is an assumption - that the rules were unchanged - but a tested one:
validate_dst.py reproduces those seasons' own D/ST point totals at 91-97% exact
and 96-98% within a point, out of sample.

    python3 load_dst_rules.py            # report only
    python3 load_dst_rules.py --write
"""
import collections
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')

STAT_NAMES = {
    89: 'dstPA0', 90: 'dstPA1_6', 91: 'dstPA7_13', 92: 'dstPA14_17',
    123: 'dstPA28_34', 124: 'dstPA35_45', 125: 'dstPA46plus',
    128: 'dstYA0_99', 129: 'dstYA100_199', 130: 'dstYA200_299', 131: 'dstYA300_349',
    132: 'dstYA350_399', 133: 'dstYA400_449', 134: 'dstYA450_499',
    135: 'dstYA500_549', 136: 'dstYA550plus',
    93: 'dstDefTD', 95: 'dstInt', 96: 'dstFumRec', 97: 'dstBlockedKick',
    98: 'dstSafety', 99: 'dstSack',
    101: 'dstKrTD', 102: 'dstPrTD', 103: 'dstFumRetTD', 104: 'dstIntRetTD',
}
READ_SEASONS = range(2018, 2026)
BACKFILL_SEASONS = range(2014, 2018)


def observed_rules():
    """statId -> {points-per-unit: times seen}, from ESPN's appliedStats."""
    seen = collections.defaultdict(collections.Counter)
    entries = 0
    for season in READ_SEASONS:
        for path in glob.glob(os.path.join(HERE, 'data', 'box_raw', str(season), 'w*.json')):
            week = int(re.search(r'w(\d+)', os.path.basename(path)).group(1))
            with open(path) as fh:
                payload = json.load(fh)
            for matchup in payload.get('schedule', []):
                if matchup.get('matchupPeriodId') != week:
                    continue
                for side in ('home', 'away'):
                    roster = (matchup.get(side) or {}).get('rosterForMatchupPeriod')
                    if not roster:
                        continue
                    for entry in roster['entries']:
                        player = entry['playerPoolEntry']['player']
                        if player.get('defaultPositionId') != 16:
                            continue
                        for block in player.get('stats', []) or []:
                            applied = block.get('appliedStats') or {}
                            raw = block.get('stats') or {}
                            if not applied:
                                continue
                            entries += 1
                            for stat_id, points in applied.items():
                                value = raw.get(stat_id)
                                if value:
                                    seen[int(stat_id)][round(points / value, 3)] += 1
                            break
    return seen, entries


def main():
    write = '--write' in sys.argv
    seen, entries = observed_rules()
    print(f'Read {entries} D/ST entries carrying an appliedStats breakdown '
          f'({READ_SEASONS.start}-{READ_SEASONS.stop - 1}).\n')

    rules, ambiguous = {}, []
    for stat_id, counts in sorted(seen.items()):
        if len(counts) != 1:
            ambiguous.append((stat_id, dict(counts)))
            continue
        rules[stat_id] = next(iter(counts))

    if ambiguous:
        print('AMBIGUOUS statIds - refusing to write:')
        for stat_id, counts in ambiguous:
            print(f'  {stat_id}: {counts}')
        return 1

    named = {s: v for s, v in rules.items() if s in STAT_NAMES}
    unknown = {s: v for s, v in rules.items() if s not in STAT_NAMES}
    print(f"{'statId':>7} {'name':<16} {'points':>7}  n")
    for stat_id, points in sorted(named.items()):
        print(f'{stat_id:>7} {STAT_NAMES[stat_id]:<16} {points:>+7g}  '
              f'{sum(seen[stat_id].values())}')
    if unknown:
        print(f'\nunmapped statIds seen (not written): {unknown}')

    print(f'\n{len(named)} rules, each with exactly one points-per-unit value '
          f'across all {READ_SEASONS.stop - READ_SEASONS.start} seasons.')
    if not write:
        print('Report only. Re-run with --write to load into dim_scoring.')
        return 0

    con = sqlite3.connect(DB)
    cols = {r[1] for r in con.execute('PRAGMA table_info(dim_scoring)')}
    with con:
        if 'source' not in cols:
            con.execute("ALTER TABLE dim_scoring ADD COLUMN source TEXT DEFAULT 'espn'")
            print("added dim_scoring.source (existing rows default to 'espn')")
        written = 0
        for seasons, source in ((READ_SEASONS, 'espn_appliedstats'),
                                (BACKFILL_SEASONS, 'backfilled')):
            for season in seasons:
                if not con.execute('SELECT 1 FROM dim_season WHERE season=?',
                                   (season,)).fetchone():
                    continue
                for stat_id, points in named.items():
                    con.execute(
                        'INSERT OR REPLACE INTO dim_scoring'
                        '(season, stat_id, stat_name, points, source) VALUES (?,?,?,?,?)',
                        (season, stat_id, STAT_NAMES[stat_id], points, source))
                    written += 1
    print(f'Wrote {written} D/ST rule rows.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
