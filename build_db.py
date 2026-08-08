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
              'dim_member', 'dim_season'):
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
                         fnum(r, 'passing_epa') + fnum(r, 'rushing_epa') + fnum(r, 'receiving_epa')))
    con.executemany("""INSERT OR REPLACE INTO fact_nfl_week
        (season, week, gsis_id, opponent, pass_yards, pass_tds, completions, attempts,
         rush_yards, rush_tds, carries, rec_yards, rec_tds, receptions, targets,
         air_yards, target_share, wopr, epa)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
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
    npl, nrw = load_players_and_rosters(con)
    print(f'  players {npl:,} · roster-weeks {nrw:,}')
    print(f'  matchup sides {load_matchups(con):,}')
    print(f'  draft picks {load_drafts(con):,}')
    print(f'  transactions {load_transactions(con):,}')
    tr, it = load_trades(con)
    print(f'  trades {tr:,} ({it:,} items)')
    print(f'  nfl player-weeks {load_nfl_weeks(con):,}')
    print(f'  contracts {load_contracts(con):,}')
    con.commit()
    con.execute('ANALYZE')
    con.commit()
    print(f'\naffl.db {"created" if fresh else "rebuilt"} — {os.path.getsize(DB)/1048576:.1f} MB')
    check(con)

if __name__ == '__main__':
    main()
