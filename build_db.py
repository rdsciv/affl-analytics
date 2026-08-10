#!/usr/bin/env python3
"""Load every source into affl.db.

Reads the same cached inputs fetch.py produces (data/*.json, data/*.csv) and
lands them in the relational schema, which then becomes the single source of
truth for metrics. Idempotent: safe to re-run, rebuilds from scratch.

    python3 build_db.py            # rebuild everything
    python3 build_db.py --check    # run verification queries only
"""
import csv
import json
import os
import sqlite3
import sys
from collections import defaultdict

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
              'fact_matchup', 'fact_roster_week', 'fact_nfl_week', 'fact_contract',
              'fact_cap_hit', 'player_season', 'dim_player', 'dim_team',
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

def load_players_and_rosters(con):
    players, pseason, rws = {}, [], []
    for year in range(2014, 2026):
        box = load(f'{DATA}/box_{year}.json')
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
    return len(rows) + filled

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
    ("contracts", "SELECT COUNT(*) FROM fact_contract"),
    ("scoring rules", "SELECT COUNT(*) FROM dim_scoring"),
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
    print(f'  contracts {load_contracts(con):,}')
    ncap, nmatch = load_cap_hits(con)
    print(f'  cap hits {ncap:,} ({nmatch:,} resolved to an AFFL-known player)')
    con.commit()
    con.execute('ANALYZE')
    con.commit()
    print(f'\naffl.db {"created" if fresh else "rebuilt"} — {os.path.getsize(DB)/1048576:.1f} MB')
    check(con)

if __name__ == '__main__':
    main()
