#!/usr/bin/env python3
"""Load the pre-2018 weekly starters ESPN still returns, into fact_roster_week.

Nothing here is inferred. Every row comes from an entry ESPN actually returned in
data/box_raw, and a team-week is only loaded when it proves itself complete:

    appliedStatTotal == the team's known score for that week
    the lineup is legal - no position over its cap, at most 9 starters

That equality is the completeness proof: if ESPN dropped an entry that scored
anything, the roster sums short. Such team-weeks are still loaded - the surviving
entries are players ESPN told us started, with exact points, and incomplete is not
the same as wrong - but they are flagged lineup_complete = 0 so nothing downstream
mistakes a partial lineup for a full one. A lineup that OUTSCORES the team is
impossible and is rejected outright. A lineup of fewer than 9 can still pass, because a manager may leave a
slot empty and an empty slot scores nothing - the points are complete either way,
though an unknown zero-scoring starter cannot be ruled out in those cases.

Two limits, both recorded rather than papered over:

  * The rosterForMatchupPeriod block this reads contains STARTERS ONLY -
    sum(entries) == appliedStatTotal in every season tested (170/170, 170/170,
    204/204) - so fact_roster_week carries no pre-2018 bench and no weekly bench
    can be inferred. The same payload's teams[].roster block DOES carry a full
    roster with bench and real lineupSlotId values, but it is a single late-season
    snapshot repeated in every weekly file, not a weekly series. That is loaded
    separately by load_pre2018_bench.py into fact_roster_snapshot_pre2018.
  * lineupSlotId is zeroed throughout this block (it survives in teams[].roster,
    but that is the snapshot, not the week), so slots are derived from
    defaultPositionId. Position is recovered exactly - validated against
    2018 truth, where every disagreement was a FLEX/same-position swap and none
    was a cross-position error. Which of two same-position starters ESPN labelled
    FLEX is NOT recoverable, so slot holds the real position and slot_source
    records that. "Did this team flex a WR" is still exactly answerable by
    comparing position counts to the template.

    python3 load_pre2018_lineups.py            # report only
    python3 load_pre2018_lineups.py --write
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

POSITION = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST'}
TEMPLATE = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'D/ST': 1}
STARTERS = 9                      # 7 named slots + FLEX
ROUNDING = 0.05                   # fact_matchup stores one decimal
SEASONS = (2014, 2015, 2016, 2017)


def candidate_team_weeks(season):
    """Yield (matchup_period, team_id, entries, applied, reported_total), deduped.

    ESPN attaches rosterForMatchupPeriod to whichever matchup contains the scoring
    period that was requested, so a two-NFL-week playoff round shows up in two
    weekly files: w14.json and w15.json both carry period 14, w16/w17 both carry
    period 15. Those duplicate payloads are byte-identical (verified 10/10 per
    season, 2014-2016), so the first wins.

    Keying on matchupPeriodId instead of the filename is what makes period 15
    reachable at all - it lives only in w16.json/w17.json, which a filename match
    could never see. fact_matchup already stores these rounds under week = period
    (2014 week 14 holds the combined weeks 14+15 score), so loading at period
    grain agrees with the matchup table rather than inventing a new convention.
    """
    pattern = os.path.join(HERE, 'data', 'box_raw', str(season), 'w*.json')
    seen = set()
    for path in sorted(glob.glob(pattern),
                       key=lambda p: int(re.search(r'w(\d+)', os.path.basename(p)).group(1))):
        with open(path) as fh:
            payload = json.load(fh)
        if isinstance(payload, list):
            payload = payload[0]
        for matchup in payload.get('schedule', []):
            period = matchup.get('matchupPeriodId')
            if period is None:
                continue
            for side in ('home', 'away'):
                entry = matchup.get(side) or {}
                roster = entry.get('rosterForMatchupPeriod')
                tid = entry.get('teamId')
                if not roster or not roster.get('entries') or tid is None:
                    continue
                if (period, tid) in seen:
                    continue
                seen.add((period, tid))
                yield (period, tid, roster['entries'],
                       roster.get('appliedStatTotal'), entry.get('totalPoints'))


def period_spans(con, season):
    """-> {matchup_period: how many NFL weeks it covers}.

    Playoff rounds in 2014-2016 run two NFL weeks (period 14 = weeks 14+15,
    period 15 = weeks 16+17). A manager fields a lineup in each of those weeks,
    so the round's roster legitimately holds up to twice the starters - two QBs,
    two defenses - and every cap below has to scale by this number.
    """
    spans = collections.defaultdict(set)
    for period, scoring_period in con.execute(
            'SELECT matchup_period, scoring_period FROM fact_team_scoring_period '
            'WHERE season=?', (season,)):
        spans[period].add(scoring_period)
    return {p: len(weeks) for p, weeks in spans.items()}


def multi_week_periods(con, season):
    """Matchup periods covering more than one NFL week."""
    return {p for p, n in period_spans(con, season).items() if n > 1}


def load(con, write=False):
    """Load the pre-2018 starters into an open connection. Returns rows written.

    build_db.py wipes fact_roster_week on every run, so the rebuild has to call
    this or the 2014-2017 recovery is destroyed. Kept callable rather than
    CLI-only for exactly that reason.
    """
    print(f"{'season':>7} {'team-wks':>9} {'complete':>9} {'partial':>8} "
          f"{'playoff-rnd':>11} {'rejected':>9}")
    staged, summary = [], []
    for season in SEASONS:
        draft_order = {pid: overall for pid, overall in con.execute(
            'SELECT player_id, overall FROM fact_draft_pick WHERE season=?', (season,))}
        targets = {(w, t): p for w, t, p in con.execute(
            'SELECT week, team_id, points FROM fact_matchup WHERE season=?', (season,))}
        # Multi-week playoff rounds are loaded, not skipped: fact_matchup stores
        # them under week = period, and the same completeness proof applies, so
        # they reconcile exactly like any other team-week. Tracked only to report
        # how much of the load is playoff rounds.
        spans = period_spans(con, season)
        seen = loaded = short = spanned = unreconciled = 0

        for week, team, entries, applied, reported in candidate_team_weeks(season):
            seen += 1
            span = spans.get(week, 1)
            if span > 1:
                spanned += 1
            # The team's own totalPoints is the target. fact_matchup must agree where
            # it has a row, but a playoff bye legitimately has no matchup row at all.
            target = reported if reported is not None else targets.get((week, team))
            matchup_total = targets.get((week, team))
            if target is None:
                unreconciled += 1
                continue
            if matchup_total is not None and abs(matchup_total - target) > ROUNDING:
                unreconciled += 1
                continue
            complete = applied is not None and abs(applied - target) <= ROUNDING
            if applied is None or applied - target > ROUNDING:
                # a lineup cannot outscore the team - something is wrong with the row
                unreconciled += 1
                continue
            if not complete:
                short += 1

            rows, counts, staged_entries = [], collections.Counter(), []
            for entry in entries:
                pool = entry['playerPoolEntry']
                position = POSITION.get(pool['player'].get('defaultPositionId'))
                if position is None:
                    staged_entries = []
                    break
                counts[position] += 1
                staged_entries.append((pool['id'], position, pool['appliedStatTotal']))

            # Exactly one starter can occupy the FLEX. Where a position is over its
            # template count, one of those players was in the FLEX - the lineup is
            # otherwise illegal, and showing (say) two TEs misrepresents it.
            #
            # WHICH of them ESPN labelled FLEX is not recoverable: tested against
            # 1,579 real FLEX decisions in 2018-2025, draft order predicts it 49.9%
            # of the time and points-based rules do worse than chance. So the pick
            # here is an arbitrary tiebreak - later-drafted, then lower-scoring - and
            # slot_source records that, so nothing downstream mistakes it for fact.
            flex_pid = None
            if span == 1:
                surplus_position = next(
                    (p for p in ('RB', 'WR', 'TE') if counts.get(p, 0) > TEMPLATE[p]), None)
                if surplus_position:
                    peers = [e for e in staged_entries if e[1] == surplus_position]
                    flex_pid = min(peers, key=lambda e: (-draft_order.get(e[0], 9999), e[2]))[0]

            for pid, position, points in staged_entries:
                is_flex = pid == flex_pid
                if span > 1:
                    # A two-week round aggregates two separate lineups, so there is no
                    # single slot chart to recover - which week a player filled, and
                    # which of them took the FLEX, is simply not in the payload. Record
                    # the position and say so, rather than inventing a lineup.
                    slot, source = position, 'derived_position_multiweek'
                else:
                    slot = 'FLEX' if is_flex else position
                    source = 'derived_flex_arbitrary' if is_flex else 'derived_position'
                rows.append((season, week, team, pid, slot,
                             points, 1, 1 if complete else 0, source))
            # The lineup must be LEGAL, not full. A manager may leave a slot empty,
            # and an empty slot still reconciles because it scores nothing. What
            # cannot happen is a position exceeding its cap (plus the single FLEX).
            flexible = ('RB', 'WR', 'TE')
            over = any(counts[p] > (n + (1 if p in flexible else 0)) * span
                       for p, n in TEMPLATE.items())
            unknown = set(counts) - set(TEMPLATE)
            if not rows or over or unknown or len(rows) > STARTERS * span:
                unreconciled += 1
                continue
            staged += rows
            if complete:
                loaded += 1

        summary.append((season, seen, loaded, short, spanned, unreconciled))
        print(f'{season:>7} {seen:>9} {loaded:>7} {short:>6} {spanned:>11} {unreconciled:>13}')

    print(f'\n{len(staged)} starter rows staged from '
          f'{sum(s[2] for s in summary)} verified team-weeks')

    existing = {s for (s,) in con.execute(
        'SELECT DISTINCT season FROM fact_roster_week WHERE season IN (2014,2015,2016,2017)')}
    if existing:
        print(f'NOTE: fact_roster_week already holds rows for {sorted(existing)}; '
              f'they will be replaced.')

    if not write:
        print('Report only. Re-run with --write to load.')
        return 0

    cols = {r[1] for r in con.execute('PRAGMA table_info(fact_roster_week)')}
    with con:
        if 'slot_source' not in cols:
            con.execute("ALTER TABLE fact_roster_week ADD COLUMN slot_source TEXT "
                        "DEFAULT 'espn'")
            print("added fact_roster_week.slot_source (existing rows default to 'espn')")
        if 'lineup_complete' not in cols:
            con.execute('ALTER TABLE fact_roster_week ADD COLUMN lineup_complete '
                        'INTEGER DEFAULT 1')
            print('added fact_roster_week.lineup_complete (existing rows default to 1)')
        con.execute('DELETE FROM fact_roster_week WHERE season IN (2014,2015,2016,2017)')
        con.executemany(
            'INSERT OR REPLACE INTO fact_roster_week'
            '(season, week, team_id, player_id, slot, points, started,'
            ' lineup_complete, slot_source) VALUES (?,?,?,?,?,?,?,?,?)', staged)
    print(f'Wrote {len(staged)} rows to fact_roster_week.')
    return len(staged)


def main():
    con = sqlite3.connect(DB)
    load(con, write='--write' in sys.argv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
