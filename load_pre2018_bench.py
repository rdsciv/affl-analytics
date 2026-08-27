#!/usr/bin/env python3
"""Load ESPN's late-season roster snapshot for 2014-2017, bench included.

`load_pre2018_lineups.py` reads `schedule[].{home,away}.rosterForMatchupPeriod`,
which holds STARTERS ONLY. The same payload also carries `teams[].roster`, and
that block is different in three ways that matter:

  * it is the FULL roster - bench entries are present (lineupSlotId 20)
  * `lineupSlotId` is REAL here, not zeroed as it is in the weekly starter block,
    so slots come straight off ESPN rather than being derived from position
  * `appliedStatTotal` is 0.0 for every entry, so it carries no points

The catch is that it is one snapshot, not a weekly series: the identical block
appears in all 17 weekly files (asserted below, not assumed). It corresponds to a
late-season week, so this loader dates it by matching its non-bench player set
against the starters already recovered into fact_roster_week. Measured result:

    season  teams  dated
      2014     10      4
      2015     10      4
      2016     10      0     <- expected; report it, do not work around it
      2017     12     11

A team whose snapshot cannot be placed still gets its rows, with dated_week NULL.
Roster membership is a season fact either way; only the week is unknown. Nothing
downstream may treat an undated snapshot as a week.

Writes fact_roster_snapshot_pre2018, never fact_roster_week - see the schema
comment and CONTRACTS.md for why the two must not be merged.

    python3 load_pre2018_bench.py            # report only
    python3 load_pre2018_bench.py --write
"""
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('AFFL_DB') or os.path.join(HERE, 'affl.db')
SEASONS = (2014, 2015, 2016, 2017)

# Real lineupSlotId values, present only in the teams[].roster block. 21 (IR) does
# not occur in any pre-2018 season; if it ever appears, KeyError is the right
# outcome - a silent 'BE' would misreport an injured-reserve stash as a bench call.
SLOT = {0: 'QB', 2: 'RB', 4: 'WR', 6: 'TE', 16: 'D/ST', 17: 'K', 20: 'BE', 23: 'FLEX'}
BENCH = {'BE'}


def season_files(season):
    pattern = os.path.join(HERE, 'data', 'box_raw', str(season), 'w*.json')
    return sorted(glob.glob(pattern),
                  key=lambda p: int(re.search(r'w(\d+)', os.path.basename(p)).group(1)))


def snapshot(season):
    """-> {team_id: [(player_id, slot_id)]}, proven identical across every file.

    The claim that this block is one repeated snapshot is load-bearing: if ESPN had
    in fact shipped a per-week roster, taking the first file would silently discard
    sixteen weeks of bench. So compare every file and refuse to guess.
    """
    seen = None
    for path in season_files(season):
        with open(path) as fh:
            payload = json.load(fh)
        if isinstance(payload, list):
            payload = payload[0]
        here = {}
        for team in payload.get('teams', []):
            entries = (team.get('roster') or {}).get('entries') or []
            if not entries:
                continue
            here[team['id']] = sorted(
                (e['playerId'], e.get('lineupSlotId')) for e in entries)
        if not here:
            continue
        if seen is None:
            seen = here
        elif here != seen:
            raise SystemExit(
                f'{season}: teams[].roster differs between weekly files. This loader '
                f'assumes one repeated snapshot; it is not one. Stop and re-model '
                f'before loading anything.')
    return seen or {}


def date_snapshot(con, season, team, non_bench):
    """-> the week this snapshot is from, or None.

    Exact set equality against a recovered lineup is the proof. Where ESPN truncated
    that lineup (lineup_complete = 0) the recovered set is a subset of what was
    really started, so subset containment is the strongest statement available and
    is accepted - but only for those weeks, and the last such match wins because
    the snapshot is late-season.
    """
    subset_hit = None
    for week, in con.execute(
            'SELECT DISTINCT week FROM fact_roster_week '
            'WHERE season=? AND team_id=? ORDER BY week', (season, team)):
        rows = con.execute(
            'SELECT player_id, lineup_complete FROM fact_roster_week '
            'WHERE season=? AND week=? AND team_id=? AND started=1',
            (season, week, team)).fetchall()
        if not rows:
            continue
        got = {r[0] for r in rows}
        if got == non_bench:
            return week
        if not rows[0][1] and got and got <= non_bench:
            subset_hit = week
    return subset_hit


def load(con, write=False):
    """Load the snapshots into an open connection. Returns rows written.

    build_db.py recreates the schema and reloads every fact table on each run, so
    this is called from there rather than being CLI-only.
    """
    print(f"{'season':>7} {'teams':>6} {'players':>8} {'bench':>6} {'dated':>6}  weeks")
    staged, totals = [], []
    for season in SEASONS:
        snap = snapshot(season)
        players = bench = dated = 0
        weeks = []
        for team in sorted(snap):
            entries = snap[team]
            non_bench = {pid for pid, sid in entries if SLOT[sid] not in BENCH}
            week = date_snapshot(con, season, team, non_bench)
            if week is not None:
                dated += 1
                weeks.append(week)
            for pid, sid in entries:
                slot = SLOT[sid]
                staged.append((season, team, pid, slot,
                               0 if slot in BENCH else 1, week))
                players += 1
                bench += slot in BENCH
        totals.append((season, len(snap), players, bench, dated))
        span = ','.join(f'w{w}' for w in sorted(set(weeks))) or '-'
        print(f'{season:>7} {len(snap):>6} {players:>8} {bench:>6} {dated:>6}  {span}')

    undated = sum(t[1] - t[4] for t in totals)
    print(f'\n{len(staged)} snapshot rows staged; '
          f'{sum(t[4] for t in totals)} team snapshots dated, {undated} not placed')
    for season, teams, _, _, dated in totals:
        if dated == 0:
            print(f'NOTE: {season} dated 0 of {teams} snapshots - its roster block '
                  f'does not match any recovered lineup. Expected for 2016.')

    if not write:
        print('Report only. Re-run with --write to load.')
        return 0

    with con:
        con.execute('DELETE FROM fact_roster_snapshot_pre2018')
        con.executemany(
            'INSERT OR REPLACE INTO fact_roster_snapshot_pre2018'
            '(season, team_id, player_id, slot, started, dated_week)'
            ' VALUES (?,?,?,?,?,?)', staged)
    print(f'Wrote {len(staged)} rows to fact_roster_snapshot_pre2018.')
    return len(staged)


def main():
    con = sqlite3.connect(DB)
    load(con, write='--write' in sys.argv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
