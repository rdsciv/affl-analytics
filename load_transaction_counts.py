#!/usr/bin/env python3
"""Load per-team, per-week acquisition counts.

SPEC.md says the transaction feed does not exist before 2018, and mTransactions2
does return nothing for those seasons. But league_YYYY.json carries
`teams[].transactionCounter.matchupAcquisitionTotals` - how many acquisitions each
team made in each matchup period - for every season including 2014-2017, and
nothing in the pipeline has ever read it.

This does not say WHO was added, so it cannot rebuild a roster on its own. What it
gives is a per-week count, which turns roster continuity from a soft prior into a
countable one.

IMPORTANT CAVEAT, measured rather than assumed: the per-week counts do NOT always
sum to the team's declared season total. They are short by 9-23 acquisitions per
season from 2014 to 2021, and agree exactly only from 2022 on. So some
acquisitions are not attributed to any matchup period - most likely pre-season
adds made before week 1.

A zero-acquisition week is therefore STRONG evidence the roster was unchanged, not
proof of it. Any downstream solver must treat these counts as a lower bound on
churn, not an exact budget. Note also that from 2019 ESPN omits zero-count periods
entirely rather than storing a zero, so a missing row means no acquisitions.

    python3 load_transaction_counts.py            # report only
    python3 load_transaction_counts.py --write
"""
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_transaction_count (
  season          INTEGER NOT NULL,
  matchup_period  INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  acquisitions    INTEGER NOT NULL,
  PRIMARY KEY (season, matchup_period, team_id)
)
"""


def load(con, write=False):
    """Load per-team, per-week acquisition counts. Returns rows written.

    Called from build_db.py so the table survives a rebuild; nothing else creates
    it, and the pre-2018 roster solver spec depends on it.
    """
    staged = []
    print(f"{'season':>7} {'teams':>6} {'rows':>6} {'total adds':>11} "
          f"{'zero-add weeks':>15} {'season total':>13} {'agrees':>7}")
    for path in sorted(glob.glob(os.path.join(HERE, 'data', 'league_*.json'))):
        season = int(re.search(r'league_(\d+)\.json', os.path.basename(path)).group(1))
        with open(path) as fh:
            league = json.load(fh)
        rows, zero, declared, summed = [], 0, 0, 0
        for team in league.get('teams', []):
            counter = team.get('transactionCounter') or {}
            totals = counter.get('matchupAcquisitionTotals') or {}
            declared += counter.get('acquisitions', 0)
            for period, count in totals.items():
                rows.append((season, int(period), team['id'], int(count)))
                summed += int(count)
                zero += (int(count) == 0)
        if not rows:
            continue
        # the per-week counts should account for the team's declared season total
        agrees = 'yes' if summed == declared else f'off by {summed - declared:+d}'
        print(f'{season:>7} {len(league.get("teams", [])):>6} {len(rows):>6} '
              f'{summed:>11} {zero:>15} {declared:>13} {agrees:>7}')
        staged += rows

    print(f'\n{len(staged)} rows staged')
    if not write:
        print('Report only. Re-run with --write to load.')
        return 0
    with con:
        con.execute(SCHEMA)
        con.execute('DELETE FROM fact_transaction_count')
        con.executemany(
            'INSERT OR REPLACE INTO fact_transaction_count'
            '(season, matchup_period, team_id, acquisitions) VALUES (?,?,?,?)', staged)
    print(f'Wrote {len(staged)} rows to fact_transaction_count.')
    return len(staged)


def main():
    con = sqlite3.connect(os.environ.get('AFFL_DB') or DB)
    load(con, write='--write' in sys.argv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
