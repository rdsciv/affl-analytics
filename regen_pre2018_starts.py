#!/usr/bin/env python3
"""Regenerate site/pre2018_starts.json from the warehouse.

Why: the existing file labels EVERY pre-2018 starter "QB" - all 1,508 player-weeks
in 2014, and the same in 2015-2017. That is not a guess gone wrong, it is ESPN's
`lineupSlotId` being returned as 0 for every pre-2018 entry, and slot 0 is QB.
Whoever built the file mapped the raw id through a slot-name table and got QB for
everyone, so the site shows kickers and defences starting at quarterback.

fact_roster_week now carries the real position, derived from
`player.defaultPositionId` and validated against 2018 truth at 1710/1710 - every
disagreement there was a FLEX/same-position swap, never a cross-position error.
This rewrites the file from that.

Shape is preserved exactly: {year: {player_id: {week: {tid, slot, pts}}}}

    python3 regen_pre2018_starts.py            # report only
    python3 regen_pre2018_starts.py --write
"""
import collections
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'site', 'pre2018_starts.json')
SEASONS = ('2014', '2015', '2016', '2017')


def main(write=None, con=None):
    write = ('--write' in sys.argv) if write is None else write
    con = con or sqlite3.connect(os.environ.get('AFFL_DB')
                                 or os.path.join(HERE, 'affl.db'))
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}

    # dim_player uses DST where the lineup template uses D/ST
    position = {str(pid): ('D/ST' if pos in ('DST', 'D/ST') else pos)
                for pid, pos in con.execute(
                    'SELECT player_id, position FROM dim_player WHERE position IS NOT NULL')}

    new, kept, relabelled = {}, 0, 0
    for season in SEASONS:
        rows = con.execute(
            'SELECT player_id, week, team_id, slot, points FROM fact_roster_week'
            ' WHERE season=? AND started=1', (int(season),)).fetchall()
        by_player = collections.defaultdict(dict)
        for pid, week, tid, slot, pts in rows:
            by_player[str(pid)][str(week)] = {'pts': pts, 'slot': slot, 'tid': tid}

        # The warehouse does not cover every team-week: the handful of internally
        # contradictory ones stay excluded on purpose. The old file covers some of
        # them, so keep that coverage rather than regressing the site - but merge at
        # TEAM-WEEK grain, not player-week.
        #
        # Merging per player-week was wrong once the two-week playoff periods were
        # recovered into fact_roster_week: the old file already held its own,
        # differently-derived rows for those weeks, so every player the warehouse
        # happened not to list got added on top of a lineup that was already
        # complete. That double-counted 22 team-weeks across 2014-2016, all in
        # week 15. Where the warehouse has a team-week at all, its set is the
        # verified one and nothing may be added to it.
        have = {(str(wk), tid) for _, wk, tid, _, _ in rows}
        for pid, weeks in (old.get(season) or {}).items():
            if not isinstance(weeks, dict):
                continue
            for week, row in weeks.items():
                if not isinstance(row, dict) or (week, row.get('tid')) in have:
                    continue
                fixed = dict(row)
                fixed['slot'] = position.get(pid, row.get('slot') or '-')
                by_player[pid][week] = fixed
                kept += 1
                relabelled += fixed['slot'] != row.get('slot')
        new[season] = dict(by_player)
    print(f'carried {kept} player-weeks forward from the old file '
          f'({relabelled} of them relabelled from the zeroed slot id)\n')

    print(f"{'season':>7} {'players':>9} {'player-weeks':>13} {'slot labels':>40}")
    for season in SEASONS:
        weeks = sum(len(v) for v in new[season].values())
        labels = collections.Counter(
            r['slot'] for v in new[season].values() for r in v.values())
        print(f'{season:>7} {len(new[season]):>9} {weeks:>13} '
              f'{dict(labels.most_common()) }')

    print('\nBEFORE (the file being replaced):')
    for season in SEASONS:
        if season not in old:
            continue
        labels = collections.Counter(
            r.get('slot') for v in old[season].values() if isinstance(v, dict)
            for r in v.values() if isinstance(r, dict))
        print(f'{season:>7} {dict(labels.most_common())}')

    # sanity: every rewritten team-week must still sum to the score ESPN reported
    bad = 0
    for season in SEASONS:
        totals = collections.Counter()
        for pid, weeks in new[season].items():
            for week, row in weeks.items():
                totals[(int(week), row['tid'])] += row['pts']
        for (week, tid), total in totals.items():
            row = con.execute(
                'SELECT points FROM fact_matchup WHERE season=? AND week=? AND team_id=?',
                (int(season), week, tid)).fetchone()
            complete = con.execute(
                'SELECT MIN(lineup_complete) FROM fact_roster_week'
                ' WHERE season=? AND week=? AND team_id=? AND started=1',
                (int(season), week, tid)).fetchone()[0]
            if row and complete and abs(row[0] - total) > 0.11:
                bad += 1
    print(f'\ncomplete team-weeks that fail to reconcile after the rewrite: {bad}')
    if bad:
        print('GATE FAILED - refusing to write.')
        return 1
    print('GATE PASSED')

    if not write:
        print('\nReport only. Re-run with --write.')
        return 0
    with open(OUT, 'w') as fh:
        json.dump(new, fh, separators=(',', ':'))
    print(f'\nWrote {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
