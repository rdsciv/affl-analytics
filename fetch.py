#!/usr/bin/env python3
"""Fetch every season of AFFL data from ESPN, compacting as we go.

Raw weekly boxscores are ~2.5 MB each; storing 8 seasons x 17 weeks raw would be
~340 MB. Instead each week is reduced to (playerId, slot, points) on fetch, so a
whole season of lineups lands in ~250 KB.

Availability discovered empirically:
  drafts        2014-2025   (leagueHistory for <=2017, seasons/ for >=2018)
  lineups       2018-2025   (ESPN does not retain rosters before 2018)
  transactions  2018-2025

ESPN credentials come from .env — see .env.example. Public nflverse pulls
(pbp / ngs / weekly stats) do not need .env.

Savant (https://nflsavant.com/) is a Cloudflare UI over the same nflverse PBP.
`/pbp_data.php?year=YYYY` 301s to the homepage — it is not a file. Live PBP
CSVs sit on R2 (`PBP_SAVANT_R2`, ~112–115 MB, 372 nflfastR cols, 2013–2025)
at the same grain as the nflverse release files we already cache. We do not
download the R2 copies. `/fantasy` is a comparison UI (std / half / ppr);
AFFL XFP is computed here from dim_scoring, never imported from Savant FP.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')

# Savant's advertised PBP window. AFFL itself starts 2014.
PBP_FIRST_YEAR = 2013
PBP_LAST_YEAR = 2025
NGS_FIRST_YEAR = 2016
NFLVERSE_UA = 'affl-analytics/1.0 (+https://github.com/rdsciv/affl-analytics)'
NFLVERSE_SLEEP = 0.75

# Documented sources. Fetch uses nflverse gzip (~18MB). R2 is the live Savant
# public file; do not commit those 110MB CSVs.
PBP_NFLVERSE = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.csv.gz'
PBP_NFLVERSE_CSV = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.csv'
PBP_SAVANT_R2 = 'https://pub-e9a6e73e336047fba26374ae44334139.r2.dev/pbp-{year}.csv'
PBP_SAVANT_PHP = 'https://nflsavant.com/pbp_data.php?year={year}'  # 301 homepage
PBP_SAVANT = PBP_SAVANT_PHP  # kept so older callers still resolve
NGS_NFLVERSE = 'https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_{kind}.csv.gz'

def env(path):
    out = {}
    if not os.path.exists(path):
        return None
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
    return out

def espn_cfg():
    cfg = env(os.path.join(HERE, '.env'))
    if not cfg:
        sys.exit('error: .env not found. Copy .env.example to .env and fill it in.')
    missing = [k for k in ('ESPN_SWID', 'ESPN_S2') if not cfg.get(k)]
    if missing:
        sys.exit('error: .env is missing ' + ', '.join(missing))
    return cfg

CFG = None
LEAGUE = '51418'
SEASON = PBP_LAST_YEAR
COOKIE = ''
BASE = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl'

def bind_espn():
    global CFG, LEAGUE, SEASON, COOKIE
    CFG = espn_cfg()
    LEAGUE = CFG.get('ESPN_LEAGUE_ID', '51418')
    SEASON = int(CFG.get('ESPN_SEASON', str(PBP_LAST_YEAR)))
    COOKIE = f"SWID={CFG['ESPN_SWID']}; espn_s2={CFG['ESPN_S2']}"

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
def _force():
    return '--force' in sys.argv


def write_manifest(entries):
    path = os.path.join(DATA, 'nflverse_manifest.json')
    prev = {}
    if os.path.exists(path):
        try:
            prev = json.load(open(path))
        except json.JSONDecodeError:
            prev = {}
    files = prev.get('files') or {}
    for e in entries:
        files[e['dest']] = e
    out = {
        'note': 'Savant UI is Cloudflare-protected; files come from nflverse releases.',
        'savant_pbp_r2': PBP_SAVANT_R2,
        'savant_pbp_php': PBP_SAVANT_PHP,
        'savant_pbp_php_status': '301 to homepage — not a file',
        'savant_fantasy': 'https://nflsavant.com/fantasy is a comparison UI (std/half/ppr). AFFL XFP uses dim_scoring.',
        'savant_pbp_template': PBP_SAVANT_R2,
        'savant_still_needs_browser': [
            'combine RAS (0-10) — not in nflverse',
            'explore query-builder leaderboards — derived views, not a bulk feed',
            'compare page snapshots — UI only',
        ],
        'files': files,
    }
    json.dump(out, open(path, 'w'), indent=2, sort_keys=True)


def download_cached(url, dest, min_bytes=64, timeout=180):
    """Skip a local cache hit unless --force. Returns (ok, detail)."""
    if os.path.exists(dest) and os.path.getsize(dest) >= min_bytes and not _force():
        return True, f'cached {os.path.getsize(dest)//1024}KB'
    tmp = dest + '.part'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': NFLVERSE_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, 'wb') as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(tmp, dest)
        return True, f'{os.path.getsize(dest)//1024}KB'
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, f'FAIL({type(e).__name__}: {e})'


def fetch_nflverse(year):
    got, manifest = [], []
    for kind, rel, name in (
            ('stats_player_week', 'stats_player', 'stats_player_week'),
            ('roster', 'rosters', 'roster')):
        u = f'https://github.com/nflverse/nflverse-data/releases/download/{rel}/{name}_{year}.csv'
        dest = f'{DATA}/{name}_{year}.csv'
        ok, detail = download_cached(u, dest, min_bytes=1024)
        got.append(f'{name}={detail}')
        manifest.append({'year': year, 'kind': name, 'url': u, 'dest': dest,
                         'ok': ok, 'via': 'nflverse'})
        time.sleep(NFLVERSE_SLEEP)
    write_manifest(manifest)
    return year, ', '.join(got)


def fetch_pbp_year(year):
    """Prefer nflverse csv.gz (~18MB). Savant PHP is documented, not used."""
    dest_gz = f'{DATA}/play_by_play_{year}.csv.gz'
    dest_csv = f'{DATA}/play_by_play_{year}.csv'
    url_gz = PBP_NFLVERSE.format(year=year)
    ok, detail = download_cached(url_gz, dest_gz, min_bytes=100_000, timeout=300)
    used = url_gz
    dest = dest_gz
    if not ok:
        url_csv = PBP_NFLVERSE_CSV.format(year=year)
        ok, detail = download_cached(url_csv, dest_csv, min_bytes=100_000, timeout=300)
        used, dest = url_csv, dest_csv
    write_manifest([{
        'year': year, 'kind': 'pbp', 'url': used, 'dest': dest,
        'ok': ok, 'via': 'nflverse',
        'savant_r2': PBP_SAVANT_R2.format(year=year),
        'savant_php': PBP_SAVANT_PHP.format(year=year),
    }])
    time.sleep(NFLVERSE_SLEEP)
    return year, ('ok' if ok else 'FAIL'), used, detail


def fetch_ngs():
    """One file per stat type covers 2016–present (week 0 = season summary)."""
    got, manifest = [], []
    for kind in ('passing', 'rushing', 'receiving'):
        u = NGS_NFLVERSE.format(kind=kind)
        dest = f'{DATA}/ngs_{kind}.csv.gz'
        ok, detail = download_cached(u, dest, min_bytes=1000)
        got.append(f'{kind}={detail}')
        manifest.append({'kind': f'ngs_{kind}', 'url': u,
                         'dest': dest, 'ok': ok, 'via': 'nflverse',
                         'years': '2016-present'})
        time.sleep(NFLVERSE_SLEEP)
    write_manifest(manifest)
    return ', '.join(got)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(DATA, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only = args[0] if args else 'all'
    year_filter = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    needs_espn = only in ('all', 'league', 'draft', 'box', 'tx')
    if needs_espn:
        bind_espn()
    season_end = SEASON if CFG else PBP_LAST_YEAR
    years = list(range(FIRST_YEAR, season_end + 1))
    roster_years = [y for y in years if y >= ROSTER_FIRST_YEAR]
    pbp_years = list(range(PBP_FIRST_YEAR, PBP_LAST_YEAR + 1))
    if year_filter is not None:
        years = [year_filter] if year_filter in years else [year_filter]
        roster_years = [y for y in years if y >= ROSTER_FIRST_YEAR]
        pbp_years = [year_filter]

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
        print('== nflverse weekly stats + rosters ==')
        nfl_years = years if only == 'nflverse' or year_filter else list(range(FIRST_YEAR, PBP_LAST_YEAR + 1))
        for y in nfl_years:
            y, msg = fetch_nflverse(y)
            print(f'  {y}: {msg}')

    if only in ('all', 'pbp', 'savant'):
        print('== nflverse play-by-play (Savant range 2013–2025) ==')
        print('   source: nflverse pbp release (csv.gz); Savant PHP is Cloudflare-blocked')
        for y in pbp_years:
            y, status, url, detail = fetch_pbp_year(y)
            print(f'  {y}: {status} {detail}')
            print(f'       {url}')

    if only in ('all', 'ngs', 'savant'):
        print('== nflverse nextgen_stats (2016–present, one file per type) ==')
        print(f'  {fetch_ngs()}')

    print('done')

if __name__ == '__main__':
    main()
