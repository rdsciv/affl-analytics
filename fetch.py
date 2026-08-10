#!/usr/bin/env python3
"""Fetch every season of AFFL data from ESPN, compacting as we go.

Raw weekly boxscores are ~2.5 MB each; storing 8 seasons x 17 weeks raw would be
~340 MB. Instead each week is reduced to (playerId, slot, points) on fetch, so a
whole season of lineups lands in ~250 KB.

Availability discovered empirically:
  drafts        2014-2025   (leagueHistory for <=2017, seasons/ for >=2018)
  lineups       2018-2025   (ESPN does not retain rosters before 2018)
  transactions  2018-2025

Credentials come from .env — see .env.example.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')

def env(path):
    out = {}
    if not os.path.exists(path):
        sys.exit('error: .env not found. Copy .env.example to .env and fill it in.')
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
    return out

CFG = env(os.path.join(HERE, '.env'))
LEAGUE = CFG.get('ESPN_LEAGUE_ID', '51418')
SEASON = int(CFG.get('ESPN_SEASON', '2025'))
COOKIE = f"SWID={CFG['ESPN_SWID']}; espn_s2={CFG['ESPN_S2']}"
BASE = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl'

FIRST_YEAR = 2014
ROSTER_FIRST_YEAR = 2018   # ESPN retains weekly lineups from here on
MAX_WEEK = 17

POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}
SLOT = {0: 'QB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE', 6: 'TE', 7: 'OP',
        16: 'D/ST', 17: 'K', 20: 'BN', 21: 'IR', 23: 'FLEX'}
PRO = {0: 'FA', 1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN',
       8: 'DET', 9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA',
       16: 'MIN', 17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI',
       23: 'PIT', 24: 'LAC', 25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR',
       30: 'JAX', 33: 'BAL', 34: 'HOU'}

def url_for(year, views, extra=''):
    v = '&'.join(f'view={x}' for x in views)
    if year >= ROSTER_FIRST_YEAR:
        return f'{BASE}/seasons/{year}/segments/0/leagues/{LEAGUE}?{v}{extra}'
    return f'{BASE}/leagueHistory/{LEAGUE}?seasonId={year}&{v}{extra}'

def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'Cookie': COOKIE, 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
                return d[0] if isinstance(d, list) else d
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == tries - 1:
                raise
        except Exception:
            if attempt == tries - 1:
                raise
    return None

# ---------------------------------------------------------------- league core
def fetch_league(year):
    d = get(url_for(year, ['mTeam', 'mSettings', 'mStandings', 'mMatchup']))
    if d:
        json.dump(d, open(f'{DATA}/league_{year}.json', 'w'))
    return year, bool(d)

# ---------------------------------------------------------------- lineups
def fetch_week(year, wk):
    d = get(url_for(year, ['mMatchup', 'mMatchupScore'], f'&scoringPeriodId={wk}'))
    if not d:
        return wk, [], {}
    games, players = [], {}
    for g in d.get('schedule', []):
        if g.get('matchupPeriodId') != wk:
            continue
        sides = {}
        for side in ('home', 'away'):
            s = g.get(side)
            if not s:
                continue
            entries = []
            roster = s.get('rosterForCurrentScoringPeriod') or s.get('rosterForMatchupPeriod')
            if roster:
                for e in roster.get('entries', []):
                    ppe = e.get('playerPoolEntry') or {}
                    p = ppe.get('player') or {}
                    pid = p.get('id') or e.get('playerId')
                    if pid is None:
                        continue
                    entries.append([pid, SLOT.get(e.get('lineupSlotId'), '?'),
                                    round(ppe.get('appliedStatTotal') or 0, 1)])
                    if pid not in players and p.get('fullName'):
                        players[pid] = [p['fullName'],
                                        POS.get(p.get('defaultPositionId'), '?'),
                                        PRO.get(p.get('proTeamId'), '')]
            sides[side] = {'tid': s['teamId'],
                           'pts': round(s.get('totalPoints') or 0, 1),
                           'roster': entries}
        if 'home' in sides and 'away' in sides and (sides['home']['pts'] or sides['away']['pts']):
            games.append({'tier': g.get('playoffTierType', 'NONE'),
                          'home': sides['home'], 'away': sides['away']})
    return wk, games, players

def fetch_box_year(year):
    weeks, players = {}, {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for wk, games, pl in ex.map(lambda w: fetch_week(year, w), range(1, MAX_WEEK + 1)):
            if games:
                weeks[str(wk)] = games
            players.update(pl)
    out = {'year': year, 'weeks': weeks,
           'players': {str(k): v for k, v in players.items()}}
    json.dump(out, open(f'{DATA}/box_{year}.json', 'w'))
    n_ros = sum(1 for gs in weeks.values() for g in gs
                if g['home']['roster'] or g['away']['roster'])
    return year, len(weeks), sum(len(g) for g in weeks.values()), n_ros, len(players)

# ---------------------------------------------------------------- draft
def fetch_draft(year):
    d = get(url_for(year, ['mDraftDetail']))
    picks = ((d or {}).get('draftDetail') or {}).get('picks') or []
    out = []
    for p in picks:
        pid = p.get('playerId')
        if pid is None:
            ot = p.get('owningTeamIds') or {}
            pid = next(iter(ot), None) if isinstance(ot, dict) else None
        out.append({
            'pid': p.get('playerId'), 'tid': p.get('teamId'),
            'bid': p.get('bidAmount') or 0, 'round': p.get('roundId'),
            'pick': p.get('roundPickNumber'), 'overall': p.get('overallPickNumber'),
            'keeper': bool(p.get('keeper')),
            'nominatedBy': p.get('nominatingTeamId'),
        })
    json.dump({'year': year, 'picks': out}, open(f'{DATA}/draft_{year}.json', 'w'))
    return year, len(out), sum(1 for p in out if p['bid'])

# ---------------------------------------------------------------- transactions
KEEP_TX = {'WAIVER', 'FREEAGENT', 'TRADE_ACCEPT', 'TRADE_PROPOSAL', 'TRADE_DECLINE',
           'TRADE_VETO', 'TRADE_UPHOLD', 'DRAFT'}

def fetch_tx_week(year, wk):
    d = get(url_for(year, ['mTransactions2'], f'&scoringPeriodId={wk}'))
    out = []
    for t in (d or {}).get('transactions') or []:
        typ = t.get('type')
        if typ not in KEEP_TX:
            continue
        items = []
        for it in t.get('items') or []:
            items.append({'pid': it.get('playerId'), 'act': it.get('type'),
                          'from': it.get('fromTeamId'), 'to': it.get('toTeamId')})
        out.append({'id': t.get('id'), 'type': typ, 'tid': t.get('teamId'),
                    'wk': t.get('scoringPeriodId'), 'bid': t.get('bidAmount') or 0,
                    'date': t.get('proposedDate'),
                    # ESPN puts the traded players on the PROPOSAL and emits
                    # TRADE_ACCEPT as a bare status event pointing back at it.
                    'rel': t.get('relatedTransactionId'),
                    'items': items})
    return out

def fetch_tx_year(year):
    all_tx = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for chunk in ex.map(lambda w: fetch_tx_week(year, w), range(1, MAX_WEEK + 1)):
            all_tx.extend(chunk)
    seen, uniq = set(), []
    for t in all_tx:
        if t['id'] in seen:
            continue
        seen.add(t['id'])
        uniq.append(t)
    uniq.sort(key=lambda t: (t['date'] or 0))
    json.dump({'year': year, 'tx': uniq}, open(f'{DATA}/tx_{year}.json', 'w'))
    trades = sum(1 for t in uniq if t['type'] == 'TRADE_ACCEPT')
    return year, len(uniq), trades

# ---------------------------------------------------------------- nflverse
def fetch_nflverse(year):
    got = []
    for kind, rel in (('stats_player_week', 'stats_player'), ('roster', 'rosters')):
        u = f'https://github.com/nflverse/nflverse-data/releases/download/{rel}/{kind}_{year}.csv'
        dest = f'{DATA}/{kind}_{year}.csv'
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=180) as r, open(dest, 'wb') as f:
                f.write(r.read())
            got.append(f'{kind}={os.path.getsize(dest)//1024}KB')
        except Exception as e:
            got.append(f'{kind}=FAIL({type(e).__name__})')
    return year, ', '.join(got)

# ---------------------------------------------------------------- main
def main():
    os.makedirs(DATA, exist_ok=True)
    years = list(range(FIRST_YEAR, SEASON + 1))
    roster_years = [y for y in years if y >= ROSTER_FIRST_YEAR]
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if only in ('all', 'league'):
        print('== league core ==')
        with ThreadPoolExecutor(max_workers=4) as ex:
            for y, ok in ex.map(fetch_league, years):
                print(f'  {y}: {"ok" if ok else "MISSING"}')

    if only in ('all', 'draft'):
        print('== drafts ==')
        with ThreadPoolExecutor(max_workers=4) as ex:
            for y, n, auction in ex.map(fetch_draft, years):
                print(f'  {y}: {n} picks{" (auction)" if auction else " (snake)"}')

    if only in ('all', 'box'):
        print('== lineups (2018+) ==')
        for y in roster_years:
            y, nw, ng, nros, npl = fetch_box_year(y)
            print(f'  {y}: {nw} weeks, {ng} games, {nros} with rosters, {npl} players')

    if only in ('all', 'tx'):
        print('== transactions (2018+) ==')
        for y in roster_years:
            y, n, trades = fetch_tx_year(y)
            print(f'  {y}: {n} transactions, {trades} completed trades')

    if only in ('all', 'nflverse'):
        # every season, not just those with ESPN lineups: pre-2018 fantasy points
        # are computed from these stats (see v_player_season_calc)
        print('== nflverse ==')
        with ThreadPoolExecutor(max_workers=3) as ex:
            for y, msg in ex.map(fetch_nflverse, years):
                print(f'  {y}: {msg}')

    print('done')

if __name__ == '__main__':
    main()
