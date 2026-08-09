#!/usr/bin/env python3
"""Fetch NFL per-player cap hits from Spotrac team cap tables.

Politeness: Spotrac's robots.txt sets `Crawl-delay: 5` for `User-agent: *` and
allows `/`. The paths we use (`/nfl/{team}/cap/_/year/{YYYY}`) are not in its
disallow list -- note that `/*/_/sort/`, `/*/_/position/`, `/*/_/type/` and
`/*/_/dir/` ARE disallowed, so never add those. We sleep 5s between requests,
send a real UA, and cache every page so a re-run costs nothing.

    python3 fetch_spotrac.py 2025            # one season
    python3 fetch_spotrac.py 2023 2024 2025  # several
"""
import os
import re
import sys
import time
import json
import html
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'data', 'spotrac')
CRAWL_DELAY = 5           # from robots.txt
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

# Spotrac slug -> the abbreviation nflverse/ESPN use
TEAMS = {
    'arizona-cardinals': 'ARI', 'atlanta-falcons': 'ATL', 'baltimore-ravens': 'BAL',
    'buffalo-bills': 'BUF', 'carolina-panthers': 'CAR', 'chicago-bears': 'CHI',
    'cincinnati-bengals': 'CIN', 'cleveland-browns': 'CLE', 'dallas-cowboys': 'DAL',
    'denver-broncos': 'DEN', 'detroit-lions': 'DET', 'green-bay-packers': 'GB',
    'houston-texans': 'HOU', 'indianapolis-colts': 'IND', 'jacksonville-jaguars': 'JAX',
    'kansas-city-chiefs': 'KC', 'las-vegas-raiders': 'LV', 'los-angeles-chargers': 'LAC',
    'los-angeles-rams': 'LAR', 'miami-dolphins': 'MIA', 'minnesota-vikings': 'MIN',
    'new-england-patriots': 'NE', 'new-orleans-saints': 'NO', 'new-york-giants': 'NYG',
    'new-york-jets': 'NYJ', 'philadelphia-eagles': 'PHI', 'pittsburgh-steelers': 'PIT',
    'san-francisco-49ers': 'SF', 'seattle-seahawks': 'SEA', 'tampa-bay-buccaneers': 'TB',
    'tennessee-titans': 'TEN', 'washington-commanders': 'WSH',
}

def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 50_000:
        return False                      # cached
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=45) as r:
        body = r.read()
    open(dest, 'wb').write(body)
    time.sleep(CRAWL_DELAY)
    return True

TAG = re.compile(r'<[^>]+>')
LINK = re.compile(r'<a[^>]*/nfl/player/[^>]*>(.*?)</a>', re.S)

def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(TAG.sub(' ', s))).strip()

def money(s):
    """Spotrac writes negatives in parentheses, e.g. ($209,804,281)."""
    if not s:
        return None
    neg = s.strip().startswith('(')
    m = re.search(r'\$([\d,]+)', s)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(',', ''))
    except ValueError:
        return None
    return -v if neg else v

def pct(s):
    m = re.search(r'([\d.]+)\s*%', s or '')
    return float(m.group(1)) / 100 if m else None

# header label -> our field
WANT = {
    'cap hit': 'cap_hit',
    'cap hit pct league cap': 'cap_pct',
    'dead cap': 'dead_cap',
    'base p5 salary': 'base_salary',
    'signing bonus proration': 'signing_bonus',
}

def parse(path, team, season):
    """Header-driven so a column re-order upstream can't silently shift values."""
    src = open(path, errors='ignore').read()
    out = []
    for tbl in re.findall(r'<table[^>]*>(.*?)</table>', src, re.S):
        if '/nfl/player/' not in tbl:
            continue
        heads = [txt(h).lower() for h in re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.S)]
        idx = {WANT[h]: i for i, h in enumerate(heads) if h in WANT}
        if 'cap_hit' not in idx:
            continue
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S):
            if '/nfl/player/' not in row:
                continue
            raw = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)
            cells = [txt(c) for c in raw]
            link = LINK.search(row)
            name = txt(link.group(1)) if link else ''
            if not name:
                continue
            pos = cells[1] if len(cells) > 1 and re.fullmatch(r'[A-Z]{1,3}', cells[1]) else None
            def cell(field):
                i = idx.get(field)
                return cells[i] if i is not None and i < len(cells) else None
            out.append({
                'season': season, 'nfl_team': team, 'player_name': name, 'position': pos,
                'cap_hit': money(cell('cap_hit')),
                'cap_pct': pct(cell('cap_pct')),
                'dead_cap': money(cell('dead_cap')),
                'base_salary': money(cell('base_salary')),
                'signing_bonus': money(cell('signing_bonus')),
            })
    # a player can show up in both the active and dead-money tables; keep the
    # row with a real cap hit
    best = {}
    for r in out:
        k = r['player_name']
        if k not in best or (r['cap_hit'] or 0) > (best[k]['cap_hit'] or 0):
            best[k] = r
    return [r for r in best.values() if r['cap_hit'] is not None]

def main():
    years = [int(a) for a in sys.argv[1:]] or [2025]
    os.makedirs(CACHE, exist_ok=True)
    for season in years:
        rows, fetched = [], 0
        for slug, abbr in TEAMS.items():
            url = f'https://www.spotrac.com/nfl/{slug}/cap/_/year/{season}'
            dest = os.path.join(CACHE, f'{season}_{slug}.html')
            try:
                if fetch(url, dest):
                    fetched += 1
            except Exception as e:
                print(f'  {season} {abbr}: FETCH FAIL {type(e).__name__}')
                continue
            got = parse(dest, abbr, season)
            rows.extend(got)
            print(f'  {season} {abbr}: {len(got)} players', flush=True)
        out = os.path.join(HERE, 'data', f'cap_{season}.json')
        json.dump(rows, open(out, 'w'))
        print(f'{season}: {len(rows)} cap rows ({fetched} pages fetched, rest cached) -> {out}')

if __name__ == '__main__':
    main()
