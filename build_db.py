#!/usr/bin/env python3
"""Load every source into affl.db.

Reads the same cached inputs fetch.py produces (data/*.json, data/*.csv) and
lands them in the relational schema, which then becomes the single source of
truth for metrics. Idempotent: safe to re-run, rebuilds from scratch.

    python3 build_db.py            # rebuild everything
    python3 build_db.py --check    # run verification queries only
"""
import csv
import gzip
import json
import os
import sqlite3
import sys
from collections import defaultdict

from affl_xfp import AFFL_SKILL_RULES, week_xfp
from pbp_agg import aggregate_pbp, pbp_path

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
DB = os.path.join(HERE, 'affl.db')
SITE = os.path.join(HERE, 'site')

SLOT = {0: 'QB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE', 6: 'TE', 7: 'OP',
        16: 'D/ST', 17: 'K', 20: 'BN', 21: 'IR', 23: 'FLEX'}
BENCH = {'BN', 'IR'}

def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d[0] if isinstance(d, list) else d

def fnum(row, key):
    try:
        return float(row.get(key) or 0)
    except (ValueError, TypeError):
        return 0.0

# --------------------------------------------------------------------- schema
def init(con):
    con.executescript(open(os.path.join(HERE, 'schema.sql')).read())

def wipe(con):
    for t in ('fact_trade_item', 'fact_trade', 'fact_transaction', 'fact_draft_pick',
              'fact_matchup', 'fact_roster_week', 'fact_nfl_week', 'fact_pbp_agg',
              'fact_ngs', 'fact_contract',
              'fact_cap_hit', 'fact_player_season_points', 'fact_player_xfp',
              'player_season',
              'dim_player', 'dim_team',
              'dim_member', 'dim_scoring', 'dim_season'):
        con.execute(f'DELETE FROM {t}')

# ------------------------------------------------------------------ load core
def load_seasons_and_teams(con, site):
    """dim_season / dim_member / dim_team come from the already-anonymised
    site/data.json, so no ESPN SWID ever reaches the database."""
    con.executemany('INSERT OR REPLACE INTO dim_member(member_id, display_name, is_active) VALUES (?,?,?)',
                    [(mid, name, 0) for mid, name in site['members'].items()])
    active = set(site.get('activeOwners') or [])
    con.executemany('UPDATE dim_member SET is_active = 1 WHERE member_id = ?',
                    [(a,) for a in active])

    for yr_s, s in site['seasons'].items():
        year = int(yr_s)
        bundle = load(os.path.join(SITE, 'years', f'{year}.json')) or {}
        slots = bundle.get('slots') or {}
        con.execute("""INSERT OR REPLACE INTO dim_season
            (season, reg_weeks, playoff_teams, team_count, auction_draft,
             has_rosters, has_tx, uses_faab,
             slot_qb, slot_rb, slot_wr, slot_te, slot_flex, slot_dst, slot_k)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (year, max(s['regWeeks']) if s.get('regWeeks') else 13,
             s.get('playoffTeams'), len(s['teams']),
             int(bool(bundle.get('auctionDraft'))), int(bool(bundle.get('hasRosters'))),
             int(bool(bundle.get('hasTx'))), int(bool(bundle.get('usesFaab'))),
             slots.get('QB'), slots.get('RB'), slots.get('WR'), slots.get('TE'),
             slots.get('FLEX'), slots.get('DST'), slots.get('K')))

        con.executemany("""INSERT OR REPLACE INTO dim_team
            (season, team_id, member_id, name, abbrev, logo, wins, losses, ties,
             points_for, points_against, playoff_seed, final_rank)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(year, t['id'], t.get('owner'), t['name'], t.get('abbrev'), t.get('logo'),
              t.get('wins'), t.get('losses'), t.get('ties'), t.get('pf'), t.get('pa'),
              t.get('playoffSeed'), t.get('finalRank')) for t in s['teams']])

def box_from_year_bundle(bundle):
    """Rebuild the compact box shape from a committed site/years bundle.

    Needed when data/box_*.json is not in the tree (gitignored) but the
    season JSON already has weekly lineups.
    """
    players = {}
    for pid_s, v in (bundle.get('pmeta') or {}).items():
        if isinstance(v, (list, tuple)) and v:
            players[str(pid_s)] = [v[0], v[1] if len(v) > 1 else '?',
                                   v[2] if len(v) > 2 else '']
    for p in bundle.get('players') or []:
        pid = str(p.get('pid'))
        if pid and pid not in players:
            players[pid] = [p.get('name'), p.get('pos'), p.get('nfl') or '']
    return {'year': bundle.get('year'), 'weeks': bundle.get('weeks') or {},
            'players': players}


def load_players_and_rosters(con):
    players, pseason, rws = {}, [], []
    for year in range(2014, 2026):
        box = load(f'{DATA}/box_{year}.json')
        if not box:
            bundle = load(os.path.join(SITE, 'years', f'{year}.json'))
            box = box_from_year_bundle(bundle) if bundle else None
        if not box:
            continue
        for pid_s, v in box.get('players', {}).items():
            pid = int(pid_s)
            name, pos, nfl = v[0], v[1], (v[2] if len(v) > 2 else '')
            players.setdefault(pid, {'name': name, 'position': pos})
            pseason.append((year, pid, nfl))
        for wk_s, games in box.get('weeks', {}).items():
            wk = int(wk_s)
            for g in games:
                for side in ('home', 'away'):
                    s = g[side]
                    for pid, slot, pts in s['roster']:
                        rws.append((year, wk, s['tid'], pid, slot, pts,
                                    0 if slot in BENCH else 1))

    # nflverse ids + headshots, so contracts and box stats can join
    gsis, shots = {}, {}
    for year in range(2014, 2026):
        p = f'{DATA}/roster_{year}.csv'
        if not os.path.exists(p):
            continue
        for row in csv.DictReader(open(p)):
            eid = row.get('espn_id')
            if not eid:
                continue
            try:
                eid = int(eid)
            except ValueError:
                continue
            if row.get('gsis_id'):
                gsis[eid] = row['gsis_id']
            hs = row.get('headshot_url') or ''
            if hs and eid not in shots:
                shots[eid] = hs.replace('f_auto,q_auto',
                                        'c_fill,g_face,h_200,w_200,f_auto,q_auto')
            if eid not in players and (row.get('full_name') or '').strip():
                players[eid] = {'name': row['full_name'].strip(),
                                'position': (row.get('position') or '').strip()}

    otc = {}
    p = f'{DATA}/otc_players.csv'
    if os.path.exists(p):
        by_gsis = {r['gsis_id']: r['otc_id'] for r in csv.DictReader(open(p)) if r.get('gsis_id')}
        for eid, g in gsis.items():
            if g in by_gsis:
                otc[eid] = by_gsis[g]

    con.executemany("""INSERT OR REPLACE INTO dim_player
        (player_id, name, position, gsis_id, otc_id, headshot_url) VALUES (?,?,?,?,?,?)""",
        [(pid, v['name'], v['position'], gsis.get(pid), otc.get(pid), shots.get(pid))
         for pid, v in players.items()])
    con.executemany('INSERT OR REPLACE INTO player_season(season, player_id, nfl_team) VALUES (?,?,?)',
                    pseason)
    # a player can appear twice in a week if ESPN reports a mid-week move; keep the last
    con.executemany("""INSERT OR REPLACE INTO fact_roster_week
        (season, week, team_id, player_id, slot, points, started) VALUES (?,?,?,?,?,?,?)""", rws)
    return len(players), len(rws)

def load_matchups(con):
    rows = []
    for year in range(2014, 2026):
        box = load(f'{DATA}/box_{year}.json')
        league = load(f'{DATA}/league_{year}.json')
        reg = ((league or {}).get('settings') or {}).get('scheduleSettings', {}).get('matchupPeriodCount', 13)
        weeks = (box or {}).get('weeks') or {}
        if not weeks and league:                 # pre-2018: schedule only
            synth = defaultdict(list)
            for g in league.get('schedule', []):
                h, a = g.get('home'), g.get('away')
                if not h or not a:
                    continue
                hp, ap = round(h.get('totalPoints') or 0, 1), round(a.get('totalPoints') or 0, 1)
                if not hp and not ap:
                    continue
                synth[str(g['matchupPeriodId'])].append(
                    {'tier': g.get('playoffTierType', 'NONE'),
                     'home': {'tid': h['teamId'], 'pts': hp},
                     'away': {'tid': a['teamId'], 'pts': ap}})
            weeks = dict(synth)
        for wk_s, games in weeks.items():
            wk = int(wk_s)
            for g in games:
                h, a = g['home'], g['away']
                playoff = 1 if (g.get('tier', 'NONE') != 'NONE' or wk > reg) else 0
                rows.append((year, wk, h['tid'], a['tid'], h['pts'], a['pts'], 1, g.get('tier', 'NONE'), playoff))
                rows.append((year, wk, a['tid'], h['tid'], a['pts'], h['pts'], 0, g.get('tier', 'NONE'), playoff))
    con.executemany("""INSERT OR REPLACE INTO fact_matchup
        (season, week, team_id, opponent_id, points, opponent_points, is_home, tier, is_playoff)
        VALUES (?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_drafts(con):
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/draft_{year}.json')
        if not d:
            continue
        for p in d['picks']:
            if p.get('overall') is None:
                continue
            rows.append((year, p['overall'], p.get('round'), p.get('pick'),
                         p['tid'], p.get('pid'), p.get('bid') or 0, int(bool(p.get('keeper')))))
    con.executemany("""INSERT OR REPLACE INTO fact_draft_pick
        (season, overall, round, pick_in_round, team_id, player_id, bid, is_keeper)
        VALUES (?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_transactions(con):
    """Only waiver/free-agent moves, attributed by the transaction ITEM (the team
    that actually gained or lost the player) rather than the executing team."""
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/tx_{year}.json')
        if not d:
            continue
        for t in d['tx']:
            if t['type'] not in ('WAIVER', 'FREEAGENT'):
                continue
            for i in t.get('items') or []:
                pid = i.get('pid')
                if pid is None:
                    continue
                if i.get('to'):
                    rows.append((year, t['wk'], t.get('date'), t['type'], i['to'], pid, 'ADD', t.get('bid') or 0))
                if i.get('from'):
                    rows.append((year, t['wk'], t.get('date'), t['type'], i['from'], pid, 'DROP', 0))
    con.executemany("""INSERT INTO fact_transaction
        (season, week, ts, tx_type, team_id, player_id, direction, bid)
        VALUES (?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_trades(con):
    """Derived from roster movement, matching process_seasons.py: the transaction
    feed's team attribution is unusable because the commissioner executes for
    other managers."""
    n_tr = n_it = 0
    for year in range(2014, 2026):
        bundle = load(os.path.join(SITE, 'years', f'{year}.json'))
        if not bundle:
            continue
        for tr in bundle.get('trades', []):
            cur = con.execute('INSERT INTO fact_trade(season, week, ts) VALUES (?,?,?)',
                              (year, tr['wk'], tr.get('date')))
            tid = cur.lastrowid
            n_tr += 1
            received = {s['tid']: {g['pid'] for g in s['got']} for s in tr['sides']}
            for to_team, pids in received.items():
                for pid in pids:
                    frm = next((o for o in received if o != to_team), to_team)
                    con.execute("""INSERT INTO fact_trade_item
                        (trade_id, player_id, from_team_id, to_team_id) VALUES (?,?,?,?)""",
                        (tid, pid, frm, to_team))
                    n_it += 1
    return n_tr, n_it

def load_nfl_weeks(con):
    rows = []
    for year in range(2014, 2026):
        p = f'{DATA}/stats_player_week_{year}.csv'
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            if r.get('season_type') != 'REG':
                continue
            try:
                wk = int(r['week'])
            except (ValueError, KeyError):
                continue
            rows.append((year, wk, r['player_id'], r.get('opponent_team'),
                         fnum(r, 'passing_yards'), fnum(r, 'passing_tds'),
                         fnum(r, 'completions'), fnum(r, 'attempts'),
                         fnum(r, 'rushing_yards'), fnum(r, 'rushing_tds'), fnum(r, 'carries'),
                         fnum(r, 'receiving_yards'), fnum(r, 'receiving_tds'),
                         fnum(r, 'receptions'), fnum(r, 'targets'),
                         fnum(r, 'receiving_air_yards'), fnum(r, 'target_share'), fnum(r, 'wopr'),
                         fnum(r, 'passing_epa') + fnum(r, 'rushing_epa') + fnum(r, 'receiving_epa'),
                         fnum(r, 'passing_interceptions'),
                         fnum(r, 'sack_fumbles_lost') + fnum(r, 'rushing_fumbles_lost')
                           + fnum(r, 'receiving_fumbles_lost'),
                         fnum(r, 'passing_2pt_conversions') + fnum(r, 'rushing_2pt_conversions')
                           + fnum(r, 'receiving_2pt_conversions'),
                         fnum(r, 'sacks_suffered'), fnum(r, 'air_yards_share'),
                         fnum(r, 'racr'), fnum(r, 'pacr')))
    con.executemany("""INSERT OR REPLACE INTO fact_nfl_week
        (season, week, gsis_id, opponent, pass_yards, pass_tds, completions, attempts,
         rush_yards, rush_tds, carries, rec_yards, rec_tds, receptions, targets,
         air_yards, target_share, wopr, epa,
         interceptions, fumbles_lost, two_pt, sacks_suffered, air_yards_share, racr, pacr)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_pbp_agg(con):
    """Stream cached nflverse PBP into player-week facts. 2013 is fetched for
    Savant's advertised range; AFFL joins start 2014."""
    rows = []
    for year in range(2013, 2026):
        path = pbp_path(DATA, year)
        if not path:
            continue
        for r in aggregate_pbp(path):
            rows.append((
                r['season'], r['week'], r['gsis_id'],
                r['dropbacks'], r['pass_attempts'], r['completions'],
                r['pass_epa'], r['cpoe'], r['cpoe_n'],
                r['pass_air_yards'], r['pass_success'], r['pass_success_n'],
                r['pass_td'], r['pass_xtd'], r['rz_pass'], r['gl_pass'],
                r['rush_att'], r['rush_epa'], r['rush_success'], r['rush_success_n'],
                r['rush_td'], r['rush_xtd'], r['rz_rush'], r['gl_rush'],
                r['targets'], r['receptions'], r['rec_epa'],
                r['rec_air_yards'], r['rec_success'], r['rec_success_n'],
                r['rec_td'], r['rec_xtd'], r['rz_tgt'], r['gl_tgt'],
                r['xyac'], r['xyac_n'],
            ))
    con.executemany("""INSERT OR REPLACE INTO fact_pbp_agg
        (season, week, gsis_id, dropbacks, pass_attempts, completions,
         pass_epa, cpoe, cpoe_n, pass_air_yards, pass_success, pass_success_n,
         pass_td, pass_xtd, rz_pass, gl_pass,
         rush_att, rush_epa, rush_success, rush_success_n,
         rush_td, rush_xtd, rz_rush, gl_rush,
         targets, receptions, rec_epa, rec_air_yards, rec_success, rec_success_n,
         rec_td, rec_xtd, rz_tgt, gl_tgt, xyac, xyac_n)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows)
    return len(rows)

def load_ngs(con):
    rows = []
    for kind in ('passing', 'rushing', 'receiving'):
        path = f'{DATA}/ngs_{kind}.csv.gz'
        if not os.path.exists(path):
            continue
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                if (r.get('season_type') or 'REG') not in ('REG', ''):
                    continue
                gsis = r.get('player_gsis_id') or r.get('player_id') or ''
                if not gsis:
                    continue
                try:
                    year = int(float(r['season']))
                    wk = int(float(r['week']))
                except (KeyError, TypeError, ValueError):
                    continue
                if year < 2016:
                    continue
                vals = {c: (fnum(r, c) if r.get(c) not in (None, '', 'NA') else None)
                        for c in (
                            'avg_cushion', 'avg_separation', 'avg_intended_air_yards',
                            'catch_percentage', 'avg_yac', 'avg_expected_yac',
                            'avg_yac_above_expectation', 'avg_time_to_throw',
                            'aggressiveness', 'expected_completion_percentage',
                            'completion_percentage_above_expectation',
                            'efficiency', 'rush_yards_over_expected')}
                rows.append((year, wk, gsis, kind,
                             vals['avg_cushion'], vals['avg_separation'],
                             vals['avg_intended_air_yards'], vals['catch_percentage'],
                             vals['avg_yac'], vals['avg_expected_yac'],
                             vals['avg_yac_above_expectation'],
                             vals['avg_time_to_throw'], vals['aggressiveness'],
                             vals['expected_completion_percentage'],
                             vals['completion_percentage_above_expectation'],
                             vals['efficiency'], vals['rush_yards_over_expected']))
    con.executemany("""INSERT OR REPLACE INTO fact_ngs
        (season, week, gsis_id, stat_type, avg_cushion, avg_separation,
         avg_intended_air_yards, catch_percentage, avg_yac, avg_expected_yac,
         avg_yac_above_expectation, avg_time_to_throw, aggressiveness,
         expected_completion_percentage, completion_percentage_above_expectation,
         efficiency, rush_yards_over_expected)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_contracts(con):
    p = f'{DATA}/historical_contracts.csv'
    if not os.path.exists(p):
        return 0
    otc_to_gsis = {}
    op = f'{DATA}/otc_players.csv'
    if os.path.exists(op):
        otc_to_gsis = {r['otc_id']: r['gsis_id'] for r in csv.DictReader(open(op)) if r.get('gsis_id')}
    rows = []
    for r in csv.DictReader(open(p)):
        def num(k):
            try:
                return float(r[k]) if r.get(k) not in (None, '', 'NA') else None
            except ValueError:
                return None
        rows.append((r.get('otc_id'), otc_to_gsis.get(r.get('otc_id')),
                     r['player'], r.get('position'), r.get('team'),
                     int(r['year_signed']) if (r.get('year_signed') or '').isdigit() else None,
                     int(r['years']) if (r.get('years') or '').isdigit() else None,
                     num('value'), num('apy'), num('guaranteed'), num('apy_cap_pct'),
                     1 if r.get('is_active') == 'TRUE' else 0))
    con.executemany("""INSERT INTO fact_contract
        (otc_id, gsis_id, player_name, position, nfl_team, year_signed, years,
         value, apy, guaranteed, apy_cap_pct, is_active)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_cap_hits(con):
    """Spotrac cap tables. Resolve each row to an ESPN player_id by name within
    the same NFL team + season, which is how the AFFL roster join happens."""
    import glob, re

    def norm(n):
        n = (n or '').lower()
        n = re.sub(r"[.'`\u2019]", '', n)
        n = re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', n)
        return re.sub(r'\s+', ' ', n).strip()

    total = matched = 0
    for path in sorted(glob.glob(f'{DATA}/cap_*.json')):
        season = int(os.path.basename(path).split('_')[1].split('.')[0])
        # espn players active that season, indexed by (nfl_team, normalised name)
        idx, by_name = {}, defaultdict(list)
        for pid, name, team in con.execute("""
                SELECT p.player_id, p.name, ps.nfl_team
                  FROM dim_player p JOIN player_season ps
                    ON ps.player_id = p.player_id AND ps.season = ?""", (season,)):
            idx[(team or '', norm(name))] = pid
            by_name[norm(name)].append(pid)

        rows = []
        for r in json.load(open(path)):
            key = (r['nfl_team'], norm(r['player_name']))
            pid = idx.get(key)
            if pid is None:
                # fall back to a league-wide unique name (handles mid-season trades)
                cands = by_name.get(norm(r['player_name']) or '', [])
                pid = cands[0] if len(cands) == 1 else None
            if pid is not None:
                matched += 1
            rows.append((season, r['nfl_team'], r['player_name'], pid, r.get('position'),
                         r.get('cap_hit'), r.get('base_salary'), r.get('signing_bonus'),
                         r.get('dead_cap'), r.get('cap_pct')))
        total += len(rows)
        con.executemany("""INSERT OR REPLACE INTO fact_cap_hit
            (season, nfl_team, player_name, player_id, position, cap_hit,
             base_salary, signing_bonus, dead_cap, cap_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
    return total, matched

STAT_NAMES = {
    0: 'passAtt', 1: 'passComp', 3: 'passYds', 4: 'passTD', 19: 'pass2pt', 20: 'passInt',
    23: 'rushAtt', 24: 'rushYds', 25: 'rushTD', 26: 'rush2pt',
    41: 'recTgt', 42: 'recYds', 43: 'recTD', 44: 'rec2pt', 53: 'rec',
    63: 'fumRecTD', 72: 'fumLost',
    74: 'fg0_39', 77: 'fg40_49', 80: 'fg50', 85: 'fgMiss', 86: 'xp', 88: 'xpMiss',
    89: 'ptsAllowed0', 90: 'ptsAllowed1_6', 91: 'ptsAllowed7_13', 92: 'ptsAllowed14_17',
    93: 'defTD', 95: 'defInt', 96: 'defFumRec', 97: 'defBlk', 98: 'defSaf', 99: 'defSack',
    101: 'krTD', 102: 'prTD', 103: 'fumRetTD', 104: 'intRetTD',
    120: 'ptsAllowed28_34', 121: 'ptsAllowed35_45', 122: 'ptsAllowed46plus',
    123: 'ptsAllowed18_21', 124: 'ptsAllowed22_27',
    198: 'yardsAllowedBucket', 201: 'defTD2', 206: 'misc206', 209: 'misc209',
}

def load_scoring(con):
    """Scoring changes between seasons, so this is keyed by season and is the
    basis for recomputing points from raw stats (needed for pre-2018)."""
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/settings_{year}.json')
        if not d:
            continue
        sc = ((d.get('settings') or {}).get('scoringSettings') or {})
        for it in sc.get('scoringItems', []):
            pts = it.get('points') or 0
            if pts:
                rows.append((year, it['statId'], STAT_NAMES.get(it['statId']), pts))
    con.executemany("""INSERT OR REPLACE INTO dim_scoring
        (season, stat_id, stat_name, points) VALUES (?,?,?,?)""", rows)

    # ESPN's stored 2018 settings omit the yardage rules (statIds 3/24/42) even
    # though the league clearly used them -- recomputed points come out ~6-19
    # short without them. Backfill from the nearest season that has them; the
    # validation script proves the assumption (2018 goes 0.6% -> 99%+ exact).
    have = {(s, sid) for s, sid in con.execute('SELECT season, stat_id FROM dim_scoring')}
    seasons = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    filled = 0
    for season in seasons:
        for sid in (3, 24, 42):
            if (season, sid) in have:
                continue
            donor = min((s for s in seasons if (s, sid) in have),
                        key=lambda s: (abs(s - season), s), default=None)
            if donor is None:
                continue
            pts, name = con.execute(
                'SELECT points, stat_name FROM dim_scoring WHERE season=? AND stat_id=?',
                (donor, sid)).fetchone()
            con.execute("""INSERT OR REPLACE INTO dim_scoring
                (season, stat_id, stat_name, points) VALUES (?,?,?,?)""",
                (season, sid, name, pts))
            filled += 1
    if filled:
        print(f'    backfilled {filled} missing yardage rules from neighbouring seasons')

    # 2018 and earlier floor yardage to whole points; 2019+ is fractional.
    # Proven empirically -- see validate_scoring.py (2018: 96.2% exact bucketed
    # vs 6.6% fractional; 2019: the reverse).
    con.execute("UPDATE dim_season SET yardage_mode = 'BUCKET'     WHERE season <= 2018")
    con.execute("UPDATE dim_season SET yardage_mode = 'FRACTIONAL' WHERE season >= 2019")

    # Seed verified AFFL skill rules when ESPN settings dumps are missing, and
    # always force rec = 0 (this league is non-PPR).
    have = {(s, sid) for s, sid in con.execute('SELECT season, stat_id FROM dim_scoring')}
    seasons = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    seeded = 0
    for season in seasons:
        for sid, (name, pts) in AFFL_SKILL_RULES.items():
            if sid == 53 or (season, sid) not in have:
                con.execute("""INSERT OR REPLACE INTO dim_scoring
                    (season, stat_id, stat_name, points) VALUES (?,?,?,?)""",
                    (season, sid, name, pts))
                seeded += 1
    if seeded:
        print(f'    seeded {seeded} AFFL skill rules (rec forced to 0)')
    return len(rows) + filled + seeded

def load_player_season_points(con):
    """Season fantasy totals per player: ESPN's own where lineups exist, computed
    from nflverse under dim_scoring where they don't (pre-2018).

    Materialised because the equivalent view -- correlated subqueries over 208k
    player-weeks -- made the site export take minutes.
    """
    modes = dict(con.execute('SELECT season, yardage_mode FROM dim_season'))
    rules = defaultdict(dict)
    for season, sid, pts in con.execute('SELECT season, stat_id, points FROM dim_scoring'):
        rules[season][sid] = pts

    # 1) actual, from ESPN's own weekly points
    actual = {}
    for season, pid, tot in con.execute("""
            SELECT season, player_id, ROUND(SUM(points), 1)
              FROM fact_roster_week GROUP BY season, player_id"""):
        actual[(season, pid)] = tot

    # 2) computed, for skill players in seasons with no lineups
    gsis_to_pid = {}
    for pid, g, pos in con.execute(
            "SELECT player_id, gsis_id, position FROM dim_player WHERE gsis_id IS NOT NULL"):
        if pos in ('QB', 'RB', 'WR', 'TE'):
            gsis_to_pid[g] = pid

    computed = defaultdict(float)
    for row in con.execute("""
            SELECT season, gsis_id, pass_yards, pass_tds, interceptions, rush_yards,
                   rush_tds, rec_yards, rec_tds, receptions, fumbles_lost, two_pt
              FROM fact_nfl_week"""):
        season, g = row[0], row[1]
        pid = gsis_to_pid.get(g)
        if pid is None:
            continue
        k = rules.get(season, {})
        py, pt, i, ry, rt, cy, ct, rc, fl, tp = row[2:]
        if modes.get(season) == 'BUCKET':
            yards = int(py // 25) + int(ry // 10) + int(cy // 10)
        else:
            yards = py * k.get(3, 0) + ry * k.get(24, 0) + cy * k.get(42, 0)
        computed[(season, pid)] += (yards + pt * k.get(4, 0) + i * k.get(20, 0)
                                   + rt * k.get(25, 0) + ct * k.get(43, 0)
                                   + rc * k.get(53, 0) + fl * k.get(72, 0)
                                   + tp * k.get(26, 0))

    rows = [(s, p, t, 0) for (s, p), t in actual.items()]
    rows += [(s, p, round(t, 1), 1) for (s, p), t in computed.items()
             if (s, p) not in actual]
    con.executemany("""INSERT OR REPLACE INTO fact_player_season_points
        (season, player_id, total_points, is_computed) VALUES (?,?,?,?)""", rows)
    return sum(1 for r in rows if not r[3]), sum(1 for r in rows if r[3])

def load_player_xfp(con):
    """AFFL FP / XFP / FPOE + opportunity shares for skill players.

    FP is recomputed from fact_nfl_week under dim_scoring (not Savant /fantasy).
    XFP swaps TDs for pbp xTD and receiving yards for air + xYAC.
    """
    modes = dict(con.execute('SELECT season, yardage_mode FROM dim_season'))
    rules_by = defaultdict(dict)
    for season, sid, pts in con.execute('SELECT season, stat_id, points FROM dim_scoring'):
        rules_by[season][sid] = pts
    for season in modes:
        rules_by[season][53] = 0.0
        for sid, (_n, pts) in AFFL_SKILL_RULES.items():
            rules_by[season].setdefault(sid, pts)

    gsis_to_pid = {}
    for pid, g, pos in con.execute(
            "SELECT player_id, gsis_id, position FROM dim_player WHERE gsis_id IS NOT NULL"):
        if pos in ('QB', 'RB', 'WR', 'TE'):
            gsis_to_pid[g] = pid

    started = set(con.execute(
        "SELECT season, week, player_id FROM fact_roster_week WHERE started = 1"))

    pbp = {}
    for r in con.execute("""
            SELECT season, week, gsis_id, pass_xtd, rush_xtd, rec_xtd,
                   rec_air_yards, xyac, xyac_n,
                   rz_pass, rz_rush, rz_tgt, gl_pass, gl_rush, gl_tgt,
                   targets, rush_att, pass_attempts, dropbacks
              FROM fact_pbp_agg"""):
        pbp[(r[0], r[1], r[2])] = {
            'pass_xtd': r[3], 'rush_xtd': r[4], 'rec_xtd': r[5],
            'rec_air_yards': r[6], 'xyac': r[7], 'xyac_n': r[8],
            'rz_pass': r[9], 'rz_rush': r[10], 'rz_tgt': r[11],
            'gl_pass': r[12], 'gl_rush': r[13], 'gl_tgt': r[14],
            'targets': r[15], 'rush_att': r[16], 'pass_attempts': r[17],
            'dropbacks': r[18],
        }

    ngs_ryoe = {}
    for s, w, g, ryoe in con.execute("""
            SELECT season, week, gsis_id, rush_yards_over_expected
              FROM fact_ngs
             WHERE stat_type = 'rushing' AND week > 0
               AND rush_yards_over_expected IS NOT NULL"""):
        ngs_ryoe[(s, w, g)] = {'rush_yards_over_expected': ryoe}

    acc = {}
    def bucket(season, pid):
        return acc.setdefault((season, pid), {
            'games': 0, 'fp': 0.0, 'xfp': 0.0,
            'st_games': 0, 'st_fp': 0.0, 'st_xfp': 0.0,
            'wopr_s': 0.0, 'wopr_n': 0, 'tsh_s': 0.0, 'tsh_n': 0,
            'ay_s': 0.0, 'ay_n': 0, 'rz': 0.0, 'gl': 0.0,
            'xtd': 0.0, 'td': 0.0, 'tgt': 0.0, 'car': 0.0, 'opp': 0.0,
        })

    for row in con.execute("""
            SELECT season, week, gsis_id, pass_yards, pass_tds, interceptions,
                   rush_yards, rush_tds, carries, rec_yards, rec_tds, receptions,
                   targets, fumbles_lost, two_pt, wopr, target_share, air_yards_share
              FROM fact_nfl_week"""):
        season, week, gsis = row[0], row[1], row[2]
        pid = gsis_to_pid.get(gsis)
        if pid is None:
            continue
        box = {
            'pass_yards': row[3], 'pass_tds': row[4], 'interceptions': row[5],
            'rush_yards': row[6], 'rush_tds': row[7], 'rec_yards': row[9],
            'rec_tds': row[10], 'receptions': row[11],
            'fumbles_lost': row[13], 'two_pt': row[14],
        }
        pb = pbp.get((season, week, gsis))
        fp, xfp, _ = week_xfp(box, pb, rules_by[season],
                              modes.get(season, 'FRACTIONAL'),
                              ngs_ryoe.get((season, week, gsis)))
        a = bucket(season, pid)
        a['games'] += 1
        a['fp'] += fp
        a['xfp'] += xfp
        if (season, week, pid) in started:
            a['st_games'] += 1
            a['st_fp'] += fp
            a['st_xfp'] += xfp
        if row[15]:
            a['wopr_s'] += row[15]; a['wopr_n'] += 1
        if row[16]:
            a['tsh_s'] += row[16]; a['tsh_n'] += 1
        if row[17]:
            a['ay_s'] += row[17]; a['ay_n'] += 1
        carries = row[8] or 0
        targets = row[12] or 0
        attempts = (pb or {}).get('pass_attempts') or 0
        a['tgt'] += targets
        a['car'] += carries
        a['opp'] += targets + carries + attempts
        if pb:
            a['rz'] += (pb.get('rz_pass') or 0) + (pb.get('rz_rush') or 0) + (pb.get('rz_tgt') or 0)
            a['gl'] += (pb.get('gl_pass') or 0) + (pb.get('gl_rush') or 0) + (pb.get('gl_tgt') or 0)
            a['xtd'] += ((pb.get('pass_xtd') or 0) + (pb.get('rush_xtd') or 0)
                         + (pb.get('rec_xtd') or 0))
        a['td'] += (row[4] or 0) + (row[7] or 0) + (row[10] or 0)

    rows = []
    for (season, pid), a in acc.items():
        g = a['games'] or 1
        sg = a['st_games']
        rows.append((
            season, pid, a['games'],
            round(a['fp'], 1), round(a['xfp'], 1), round(a['fp'] - a['xfp'], 1),
            round(a['fp'] / g, 2), round(a['xfp'] / g, 2),
            sg,
            round(a['st_fp'], 1) if sg else None,
            round(a['st_xfp'], 1) if sg else None,
            round(a['st_fp'] - a['st_xfp'], 1) if sg else None,
            round(a['wopr_s'] / a['wopr_n'], 3) if a['wopr_n'] else None,
            round(a['tsh_s'] / a['tsh_n'], 3) if a['tsh_n'] else None,
            round(a['ay_s'] / a['ay_n'], 3) if a['ay_n'] else None,
            a['rz'], a['gl'], round(a['xtd'], 2),
            round(a['td'] - a['xtd'], 2),
            a['tgt'], a['car'], a['opp'],
        ))
    con.executemany("""INSERT OR REPLACE INTO fact_player_xfp
        (season, player_id, games, fp, xfp, fpoe, fp_g, xfp_g,
         st_games, st_fp, st_xfp, st_fpoe, wopr, target_share, air_yards_share,
         rz_opp, gl_opp, xtd, td_luck, targets, carries, opp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows), sum(1 for r in rows if r[8])

# ---------------------------------------------------------------- verification
CHECKS = [
    ("seasons", "SELECT COUNT(*) FROM dim_season"),
    ("members", "SELECT COUNT(*) FROM dim_member"),
    ("franchise-seasons", "SELECT COUNT(*) FROM dim_team"),
    ("players", "SELECT COUNT(*) FROM dim_player"),
    ("players w/ gsis", "SELECT COUNT(*) FROM dim_player WHERE gsis_id IS NOT NULL"),
    ("roster-weeks", "SELECT COUNT(*) FROM fact_roster_week"),
    ("matchup sides", "SELECT COUNT(*) FROM fact_matchup"),
    ("draft picks", "SELECT COUNT(*) FROM fact_draft_pick"),
    ("transactions", "SELECT COUNT(*) FROM fact_transaction"),
    ("trades", "SELECT COUNT(*) FROM fact_trade"),
    ("nfl player-weeks", "SELECT COUNT(*) FROM fact_nfl_week"),
    ("pbp player-weeks", "SELECT COUNT(*) FROM fact_pbp_agg"),
    ("ngs player-weeks", "SELECT COUNT(*) FROM fact_ngs"),
    ("contracts", "SELECT COUNT(*) FROM fact_contract"),
    ("scoring rules", "SELECT COUNT(*) FROM dim_scoring"),
    ("player-seasons", "SELECT COUNT(*) FROM fact_player_season_points"),
    ("player xfp", "SELECT COUNT(*) FROM fact_player_xfp"),
    ("cap hits", "SELECT COUNT(*) FROM fact_cap_hit"),
]

INTEGRITY = [
    ("every matchup side has a mirror",
     """SELECT COUNT(*) FROM fact_matchup a LEFT JOIN fact_matchup b
          ON b.season=a.season AND b.week=a.week AND b.team_id=a.opponent_id
        WHERE b.team_id IS NULL"""),
    ("no roster row points to an unknown team",
     """SELECT COUNT(*) FROM fact_roster_week r LEFT JOIN dim_team t
          ON t.season=r.season AND t.team_id=r.team_id WHERE t.team_id IS NULL"""),
    ("no roster row points to an unknown player",
     """SELECT COUNT(*) FROM fact_roster_week r LEFT JOIN dim_player p
          ON p.player_id=r.player_id WHERE p.player_id IS NULL"""),
    ("no ESPN SWID leaked into member ids",
     "SELECT COUNT(*) FROM dim_member WHERE member_id LIKE '{%'"),
]

def check(con):
    print('== row counts ==')
    for label, q in CHECKS:
        print(f'  {label:20} {con.execute(q).fetchone()[0]:>9,}')
    print('== integrity (all must be 0) ==')
    ok = True
    for label, q in INTEGRITY:
        n = con.execute(q).fetchone()[0]
        flag = 'ok' if n == 0 else 'FAIL'
        if n:
            ok = False
        print(f'  [{flag}] {label:44} {n}')
    return ok

def main():
    if '--check' in sys.argv:
        con = sqlite3.connect(DB)
        sys.exit(0 if check(con) else 1)

    site = json.load(open(os.path.join(SITE, 'data.json')))
    fresh = not os.path.exists(DB)
    con = sqlite3.connect(DB)
    init(con)
    wipe(con)

    load_seasons_and_teams(con, site)
    print(f'  scoring rules {load_scoring(con):,}')
    npl, nrw = load_players_and_rosters(con)
    print(f'  players {npl:,} · roster-weeks {nrw:,}')
    print(f'  matchup sides {load_matchups(con):,}')
    print(f'  draft picks {load_drafts(con):,}')
    print(f'  transactions {load_transactions(con):,}')
    tr, it = load_trades(con)
    print(f'  trades {tr:,} ({it:,} items)')
    print(f'  nfl player-weeks {load_nfl_weeks(con):,}')
    print(f'  pbp player-weeks {load_pbp_agg(con):,}')
    print(f'  ngs player-weeks {load_ngs(con):,}')
    print(f'  contracts {load_contracts(con):,}')
    na, nc = load_player_season_points(con)
    print(f'  player-seasons {na + nc:,} ({nc:,} computed from NFL stats)')
    nx, nxs = load_player_xfp(con)
    print(f'  player xfp {nx:,} ({nxs:,} with an AFFL start)')
    ncap, nmatch = load_cap_hits(con)
    print(f'  cap hits {ncap:,} ({nmatch:,} resolved to an AFFL-known player)')
    con.commit()
    con.execute('ANALYZE')
    con.commit()
    print(f'\naffl.db {"created" if fresh else "rebuilt"} — {os.path.getsize(DB)/1048576:.1f} MB')
    check(con)

if __name__ == '__main__':
    main()
