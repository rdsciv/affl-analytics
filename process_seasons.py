#!/usr/bin/env python3
"""Per-season processing: lineups, player profiles, draft boards, transactions.

Writes one compact bundle per year to site/years/{year}.json plus a small
site/index_years.json manifest the front end reads first. Splitting by year keeps
initial page load small — the front end lazy-loads only the season being viewed.

Data availability (see fetch.py): drafts 2014+, lineups & transactions 2018+.
"""
import json
import csv
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
SITE = os.path.join(HERE, 'site')
YEARS_DIR = os.path.join(SITE, 'years')

REG_WEEKS_DEFAULT = 13
STARTER_SLOTS_EXCLUDE = {'BN', 'IR'}

PRO = {0: 'FA', 1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN',
       8: 'DET', 9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA',
       16: 'MIN', 17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI',
       23: 'PIT', 24: 'LAC', 25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR',
       30: 'JAX', 33: 'BAL', 34: 'HOU'}

def dst_name(pid):
    """ESPN encodes D/ST as playerId = -16000 - proTeamId."""
    if pid is None or pid > -16000 or pid < -16040:
        return None
    ab = PRO.get(-16000 - pid)
    return f'{ab} D/ST' if ab else None

def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d[0] if isinstance(d, list) else d

def fnum(row, key):
    try:
        return float(row.get(key, '') or 0)
    except (ValueError, TypeError):
        return 0.0

# ------------------------------------------------------------------ nflverse
def load_nflverse(year):
    """-> (espn_id->gsis, gsis->week->row, espn_id->meta w/ name+pos fallback)"""
    e2g, meta = {}, {}
    rpath = f'{DATA}/roster_{year}.csv'
    if os.path.exists(rpath):
        with open(rpath) as f:
            for row in csv.DictReader(f):
                eid = row.get('espn_id')
                if not eid:
                    continue
                if row.get('gsis_id'):
                    e2g[eid] = row['gsis_id']
                hs = row.get('headshot_url') or ''
                if hs:
                    hs = hs.replace('f_auto,q_auto', 'c_fill,g_face,h_200,w_200,f_auto,q_auto')
                meta[eid] = {'nfl': row.get('team', ''), 'hs': hs,
                             'name': (row.get('full_name') or '').strip(),
                             'pos': (row.get('position') or '').strip()}
    stats = defaultdict(dict)
    spath = f'{DATA}/stats_player_week_{year}.csv'
    if os.path.exists(spath):
        with open(spath) as f:
            for row in csv.DictReader(f):
                if row.get('season_type') != 'REG':
                    continue
                try:
                    wk = int(row['week'])
                except (ValueError, KeyError):
                    continue
                stats[row['player_id']][wk] = row
    return e2g, stats, meta

# ------------------------------------------------------------------ optimum
def optimal_points(entries, slot_counts):
    """entries: list of (pos, pts). Greedy over fixed slots then flex."""
    by = defaultdict(list)
    for pos, pts in entries:
        by[pos].append(pts)
    for k in by:
        by[k].sort(reverse=True)
    used = defaultdict(int)
    total = 0.0
    for pos, n in (('QB', slot_counts.get('QB', 1)), ('RB', slot_counts.get('RB', 2)),
                   ('WR', slot_counts.get('WR', 2)), ('TE', slot_counts.get('TE', 1)),
                   ('DST', slot_counts.get('DST', 1)), ('K', slot_counts.get('K', 1))):
        take = by[pos][:n]
        total += sum(take)
        used[pos] = len(take)
    for _ in range(slot_counts.get('FLEX', 1)):
        best, bpos = 0.0, None
        for pos in ('RB', 'WR', 'TE'):
            pool = by[pos][used[pos]:used[pos] + 1]
            if pool and pool[0] > best:
                best, bpos = pool[0], pos
        if bpos:
            total += best
            used[bpos] += 1
    return round(total, 2)

def slot_counts_from_settings(league):
    lsc = ((league or {}).get('settings') or {}).get('rosterSettings', {}).get('lineupSlotCounts', {})
    m = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0, 'DST': 0, 'K': 0, 'FLEX': 0}
    for sid, n in (lsc or {}).items():
        n = int(n)
        if n <= 0:
            continue
        sid = int(sid)
        if sid == 0: m['QB'] += n
        elif sid == 2: m['RB'] += n
        elif sid == 4: m['WR'] += n
        elif sid == 6: m['TE'] += n
        elif sid == 16: m['DST'] += n
        elif sid == 17: m['K'] += n
        elif sid in (3, 5, 7, 23): m['FLEX'] += n
    for k, v in (('QB', 1), ('RB', 2), ('WR', 2), ('TE', 1), ('DST', 1), ('K', 1), ('FLEX', 1)):
        if not m[k]:
            m[k] = v
    return m

# ------------------------------------------------------------------ per year
def process_year(year, league, season_teams):
    box = load(f'{DATA}/box_{year}.json') or {'weeks': {}, 'players': {}}
    draft = load(f'{DATA}/draft_{year}.json') or {'picks': []}
    txd = load(f'{DATA}/tx_{year}.json') or {'tx': []}
    e2g, nflstats, nflmeta = load_nflverse(year)

    sched = ((league or {}).get('settings') or {}).get('scheduleSettings', {})
    reg_weeks = sched.get('matchupPeriodCount', REG_WEEKS_DEFAULT)
    slots = slot_counts_from_settings(league)

    sbp = box.get('players', {})
    pmeta = {}   # pid -> {name,pos,nfl,hs}
    for pid, v in sbp.items():
        m = nflmeta.get(pid, {})
        pmeta[int(pid)] = {'name': v[0], 'pos': v[1],
                           'nfl': m.get('nfl') or v[2] or '', 'hs': m.get('hs', '')}
    # Any player referenced only by a draft pick or a transaction (never rostered
    # in a scored lineup) has no boxscore entry, and seasons before 2018 have no
    # lineups at all. Resolve those from the nflverse roster so no id leaks to UI.
    extra_ids = [p.get('pid') for p in draft.get('picks', [])]
    for t in txd.get('tx', []):
        for i in t.get('items') or []:
            extra_ids.append(i.get('pid'))
    for pid in extra_ids:
        if pid is None or pid in pmeta:
            continue
        d = dst_name(pid)
        if d:
            pmeta[pid] = {'name': d, 'pos': 'DST', 'nfl': d.split()[0], 'hs': ''}
            continue
        m = nflmeta.get(str(pid))
        if m and m.get('name'):
            pmeta[pid] = {'name': m['name'], 'pos': m.get('pos') or '?',
                          'nfl': m.get('nfl', ''), 'hs': m.get('hs', '')}

    # Seasons before 2018 have no stored lineups, but the league file still has
    # the schedule with final scores — synthesise roster-less weeks so every year
    # has a real scoreboard instead of an empty page.
    if not box.get('weeks') and league:
        synth = defaultdict(list)
        for g in league.get('schedule', []):
            h, a = g.get('home'), g.get('away')
            if not h or not a:
                continue
            hp = round(h.get('totalPoints') or 0, 1)
            ap = round(a.get('totalPoints') or 0, 1)
            if not hp and not ap:
                continue
            synth[str(g['matchupPeriodId'])].append({
                'tier': g.get('playoffTierType', 'NONE'),
                'home': {'tid': h['teamId'], 'pts': hp, 'roster': []},
                'away': {'tid': a['teamId'], 'pts': ap, 'roster': []},
            })
        box['weeks'] = dict(synth)

    # ---- flatten lineups ----
    # rows: week, tid, pid, slot, pts, started
    rows = []
    has_rosters = False
    for wk_s, games in box.get('weeks', {}).items():
        wk = int(wk_s)
        for g in games:
            for side in ('home', 'away'):
                s = g[side]
                if s['roster']:
                    has_rosters = True
                for pid, slot, pts in s['roster']:
                    rows.append((wk, s['tid'], pid, slot, pts, slot not in STARTER_SLOTS_EXCLUDE))

    team_ids = sorted({t['id'] for t in (league or {}).get('teams', [])})

    # ---- lineup IQ ----
    week_team = defaultdict(list)
    for wk, tid, pid, slot, pts, started in rows:
        week_team[(wk, tid)].append((pid, slot, pts, started))
    iq = {}
    if has_rosters:
        acc = {tid: {'a': 0.0, 'o': 0.0, 'perfect': 0, 'weeks': 0} for tid in team_ids}
        for (wk, tid), ents in week_team.items():
            if wk > reg_weeks or tid not in acc:
                continue
            actual = round(sum(p for _, _, p, st in ents if st), 2)
            opt = optimal_points([(pmeta.get(pid, {}).get('pos', '?'), p) for pid, _, p, _ in ents], slots)
            b = acc[tid]
            b['a'] += actual; b['o'] += opt; b['weeks'] += 1
            if opt - actual < 0.005:
                b['perfect'] += 1
        for tid, b in acc.items():
            if b['weeks']:
                iq[tid] = {'teamId': tid, 'actual': round(b['a'], 1), 'optimal': round(b['o'], 1),
                           'eff': round(b['a'] / b['o'], 4) if b['o'] else 0,
                           'wasted': round(b['o'] - b['a'], 1), 'perfect': b['perfect']}

    # ---- player profiles ----
    plog = defaultdict(dict)
    for wk, tid, pid, slot, pts, started in rows:
        plog[pid][wk] = (pts, started, tid, slot)
    drafted_by = {p['pid']: {'teamId': p['tid'], 'bid': p['bid'], 'round': p['round'],
                             'overall': p['overall'], 'keeper': p['keeper']}
                  for p in draft.get('picks', []) if p.get('pid')}

    players = []
    for pid, log in plog.items():
        tot = round(sum(v[0] for v in log.values()), 1)
        st = [v for v in log.values() if v[1]]
        st_pts = round(sum(v[0] for v in st), 1)
        n_st = len(st)
        if tot < 5 and not n_st:
            continue
        scores = [v[0] for v in st]
        boom = bust = 0
        cons = None
        if len(scores) >= 3:
            mean = sum(scores) / len(scores)
            if mean > 0:
                boom = sum(1 for x in scores if x >= 1.5 * mean)
                bust = sum(1 for x in scores if x <= 0.5 * mean)
                sd = (sum((x - mean) ** 2 for x in scores) / len(scores)) ** 0.5
                cons = round(max(0.0, 1 - sd / mean), 2)
        gsis = e2g.get(str(pid))
        epa_t = wopr_s = wopr_n = tsh_s = tsh_n = 0.0
        wk_arr = []
        for wk in sorted(log):
            pts, started, tid, slot = log[wk]
            srow = nflstats.get(gsis, {}).get(wk) if gsis else None
            opp = srow.get('opponent_team', '') if srow else ''
            yds = td = tgt = epa_w = None
            if srow:
                yds = int(fnum(srow, 'passing_yards') + fnum(srow, 'rushing_yards') + fnum(srow, 'receiving_yards'))
                td = int(fnum(srow, 'passing_tds') + fnum(srow, 'rushing_tds') + fnum(srow, 'receiving_tds'))
                tgt = int(fnum(srow, 'targets'))
                epa_w = round(fnum(srow, 'passing_epa') + fnum(srow, 'rushing_epa') + fnum(srow, 'receiving_epa'), 1)
                if started and wk <= reg_weeks:
                    epa_t += epa_w
                    w = fnum(srow, 'wopr')
                    if w: wopr_s += w; wopr_n += 1
                    t = fnum(srow, 'target_share')
                    if t: tsh_s += t; tsh_n += 1
            wk_arr.append([wk, pts, 1 if started else 0, tid, slot, opp, yds, td, tgt, epa_w])
        st_by = defaultdict(float)
        for wk, (pts, started, tid, slot) in log.items():
            if started:
                st_by[tid] += pts
        m = pmeta.get(pid, {'name': f'#{pid}', 'pos': '?', 'nfl': '', 'hs': ''})
        players.append({
            'pid': pid, 'name': m['name'], 'pos': m['pos'], 'nfl': m['nfl'], 'hs': m['hs'],
            'tot': tot, 'stPts': st_pts, 'starts': n_st,
            'ppg': round(st_pts / n_st, 1) if n_st else 0,
            'boom': boom, 'bust': bust, 'cons': cons,
            'epa': round(epa_t, 1) if gsis else None,
            'wopr': round(wopr_s / wopr_n, 2) if wopr_n else None,
            'tsh': round(tsh_s / tsh_n, 3) if tsh_n else None,
            'draft': drafted_by.get(pid), 'wk': wk_arr,
            'mainTeam': max(st_by, key=st_by.get) if st_by else wk_arr[-1][3],
        })
    players.sort(key=lambda x: -x['tot'])

    # ---- draft board (names resolved where possible) ----
    rostered_pts = defaultdict(float)
    for wk, tid, pid, slot, pts, started in rows:
        rostered_pts[pid] += pts
    board = []
    for p in draft.get('picks', []):
        pid = p.get('pid')
        m = pmeta.get(pid)
        board.append({
            'pid': pid, 'tid': p['tid'], 'bid': p['bid'], 'round': p['round'],
            'pick': p['pick'], 'overall': p['overall'], 'keeper': p['keeper'],
            'name': (m or {}).get('name') or (f'Player {pid}' if pid else '—'),
            'pos': (m or {}).get('pos', '?'), 'nfl': (m or {}).get('nfl', ''),
            'pts': round(rostered_pts.get(pid, 0), 1) if pid in rostered_pts else None,
        })
    board.sort(key=lambda x: (x['overall'] or 0))
    auction = any(b['bid'] for b in board)

    # ---- transactions & trades ----
    # ESPN records traded players on the TRADE_PROPOSAL and emits TRADE_ACCEPT as
    # a bare status event carrying relatedTransactionId, so accepts must be joined
    # back to their proposal to recover who actually moved.
    by_id = {t['id']: t for t in txd.get('tx', [])}

    def named(items):
        out = []
        for i in items:
            pid = i.get('pid')
            if pid is None:
                continue
            m = pmeta.get(pid, {})
            out.append({'pid': pid, 'from': i.get('from'), 'to': i.get('to'),
                        'name': m.get('name') or f'Player {pid}',
                        'pos': m.get('pos', '?')})
        return out

    moves, trades, accepts = [], [], []
    proposals = [x for x in txd.get('tx', []) if x['type'] == 'TRADE_PROPOSAL' and x.get('items')]
    per_team = defaultdict(lambda: {'waiver': 0, 'fa': 0, 'drop': 0, 'trades': 0,
                                    'proposed': 0, 'declined': 0, 'vetoed': 0, 'spent': 0})
    counts = defaultdict(int)

    for t in txd.get('tx', []):
        typ = t['type']
        counts[typ] += 1
        pt = per_team[t['tid']]
        if typ in ('WAIVER', 'FREEAGENT'):
            items = named(t.get('items', []))
            adds = [i for i in items if i['to'] == t['tid']]
            drops = [i for i in items if i['from'] == t['tid']]
            if typ == 'WAIVER':
                pt['waiver'] += 1
                pt['spent'] += t['bid'] or 0
            else:
                pt['fa'] += 1
            pt['drop'] += len(drops)
            if adds or drops:
                moves.append({'type': typ, 'tid': t['tid'], 'wk': t['wk'],
                              'bid': t['bid'] or 0, 'date': t['date'],
                              'add': adds, 'drop': drops})
        elif typ == 'TRADE_PROPOSAL':
            pt['proposed'] += 1
        elif typ == 'TRADE_DECLINE':
            pt['declined'] += 1
        elif typ == 'TRADE_VETO':
            pt['vetoed'] += 1
        elif typ == 'TRADE_ACCEPT':
            accepts.append(t)

    # Resolve each accept to the players that moved. ESPN's relatedTransactionId
    # often points at a superseded counter-offer, so fall back to the nearest
    # earlier proposal involving that team. Trades are then deduped by the exact
    # set of players moved, since a single trade can emit several accept events.
    WINDOW_MS = 7 * 86400000

    def resolve(a):
        if a.get('items'):
            return a['items']
        rel = by_id.get(a.get('rel'))
        if rel and rel.get('items'):
            return rel['items']
        best = None
        for p in proposals:
            if not (a['date'] and p['date']) or not (0 <= a['date'] - p['date'] <= WINDOW_MS):
                continue
            teams = {i.get('from') for i in p['items']} | {i.get('to') for i in p['items']}
            if a['tid'] not in teams:
                continue
            gap = a['date'] - p['date']
            if best is None or gap < best[0]:
                best = (gap, p['items'])
        return best[1] if best else []

    seen_trades = set()
    for a in accepts:
        items = named(resolve(a))
        sides = defaultdict(list)
        for i in items:
            if i['to']:
                sides[i['to']].append(i)
        if len(sides) < 2:
            continue
        sig = (a['wk'], frozenset(i['pid'] for i in items))
        if sig in seen_trades:
            continue
        seen_trades.add(sig)
        trades.append({'wk': a['wk'], 'date': a['date'],
                       'sides': [{'tid': tid, 'got': v} for tid, v in sides.items()]})
    trades.sort(key=lambda t: (t['date'] or 0))

    for tr in trades:
        for s in tr['sides']:
            per_team[s['tid']]['trades'] += 1
    moves.sort(key=lambda m: (m['date'] or 0))

    # This league runs waiver priority, not FAAB, so bids are all zero — flag it
    # so the UI can drop the money columns instead of showing a wall of $0.
    uses_faab = any(m['bid'] for m in moves)

    add_counts = defaultdict(int)
    for m in moves:
        for a in m['add']:
            add_counts[a['pid']] += 1
    top_adds = [{'pid': pid, 'n': n,
                 'name': pmeta.get(pid, {}).get('name', f'Player {pid}'),
                 'pos': pmeta.get(pid, {}).get('pos', '?')}
                for pid, n in sorted(add_counts.items(), key=lambda x: -x[1])[:10]]

    # ================= dashboard analytics (per season) =================
    # These used to be computed for 2025 only, which froze the dashboard's lower
    # half on that year no matter which season was picked. Everything below is
    # derived from this season's own data.
    tinfo = {t['id']: t for t in (season_teams or [])}
    n_teams = len(tinfo) or len(team_ids) or 1

    # ---- position DNA: where each team's started points came from ----
    dna = defaultdict(lambda: defaultdict(float))
    for wk, tid, pid, slot, pts, started in rows:
        if started and wk <= reg_weeks:
            dna[tid][pmeta.get(pid, {}).get('pos', '?')] += pts
    pos_dna = {str(tid): {p: round(v, 1) for p, v in d.items()} for tid, d in dna.items()}

    # ---- per-team NFL advanced totals from started players ----
    adv = defaultdict(lambda: {'epa': 0.0, 'air': 0.0, 'wopr': 0.0, 'woprN': 0,
                               'matched': 0, 'starts': 0})
    for wk, tid, pid, slot, pts, started in rows:
        if not started or wk > reg_weeks:
            continue
        pos = pmeta.get(pid, {}).get('pos', '?')
        if pos == 'DST':
            continue
        a = adv[tid]
        a['starts'] += 1
        gsis = e2g.get(str(pid))
        st = nflstats.get(gsis, {}).get(wk) if gsis else None
        if not st:
            continue
        a['matched'] += 1
        a['epa'] += fnum(st, 'passing_epa') + fnum(st, 'rushing_epa') + fnum(st, 'receiving_epa')
        a['air'] += fnum(st, 'receiving_air_yards')
        w = fnum(st, 'wopr')
        if w:
            a['wopr'] += w
            a['woprN'] += 1
    franchise_adv = sorted(
        [{'teamId': tid, 'epa': round(a['epa'], 1), 'air': int(a['air']),
          'wopr': round(a['wopr'] / a['woprN'], 3) if a['woprN'] else 0,
          'matchRate': round(a['matched'] / max(1, a['starts']), 3)}
         for tid, a in adv.items()],
        key=lambda x: -x['epa'])

    # ---- started points per (team, player) -> MVPs, spotlight, waiver value ----
    started_by = defaultdict(float)
    for wk, tid, pid, slot, pts, started in rows:
        if started:
            started_by[(tid, pid)] += pts
    mvps = {}
    for (tid, pid), pts in started_by.items():
        if tid not in mvps or pts > mvps[tid]['pts']:
            m = pmeta.get(pid, {})
            mvps[tid] = {'pid': pid, 'name': m.get('name', '?'),
                         'pos': m.get('pos', '?'), 'pts': round(pts, 1)}

    by_player = defaultdict(float)
    for (tid, pid), pts in started_by.items():
        by_player[pid] += pts
    pidx = {p['pid']: p for p in players}
    spotlight = []
    for pid, pts in sorted(by_player.items(), key=lambda x: -x[1]):
        p = pidx.get(pid)
        if not p or p['pos'] in ('DST', 'K'):
            continue
        spotlight.append({'name': p['name'], 'pos': p['pos'], 'teamId': p['mainTeam'],
                          'pts': round(pts, 1), 'ppg': p['ppg'], 'epa': p['epa'],
                          'wopr': p['wopr'], 'tsh': p['tsh']})
        if len(spotlight) >= 12:
            break

    # ---- draft value: steals, busts, per-team efficiency ----
    auction_draft = auction
    named_board = [b for b in board if b['pid'] and b['pts'] is not None]
    for b in named_board:
        b['ppd'] = round(b['pts'] / max(1, b['bid'] or 1), 2)
    steals = sorted([b for b in named_board if (b['bid'] or 0) >= 1 or not auction_draft],
                    key=lambda x: -x['ppd'])[:8]
    busts = sorted([b for b in named_board if (b['bid'] or 0) >= 20],
                   key=lambda x: x['ppd'])[:8] if auction_draft else \
            sorted([b for b in named_board if (b['overall'] or 99) <= 24],
                   key=lambda x: x['pts'])[:8]
    spend = defaultdict(lambda: [0, 0.0])
    for b in board:
        spend[b['tid']][0] += b['bid'] or 0
        spend[b['tid']][1] += b['pts'] or 0
    draft_eff = sorted([{'teamId': t, 'spent': v[0], 'pts': round(v[1], 1),
                         'ppd': round(v[1] / max(1, v[0]), 2)} for t, v in spend.items()],
                       key=lambda x: -x['ppd'])

    # ---- what-if: standings if everyone started a perfect lineup ----
    whatif_rows = []
    if has_rosters:
        wk_opt, wk_act = {}, {}
        for (wk, tid), ents in week_team.items():
            if wk > reg_weeks:
                continue
            wk_opt[(tid, wk)] = optimal_points(
                [(pmeta.get(pid, {}).get('pos', '?'), p) for pid, _, p, _ in ents], slots)
            wk_act[(tid, wk)] = round(sum(p for _, _, p, st in ents if st), 2)
        wif = defaultdict(lambda: {'w': 0, 'l': 0})
        act = defaultdict(lambda: {'w': 0, 'l': 0})
        for wk_s, games in box.get('weeks', {}).items():
            wk = int(wk_s)
            if wk > reg_weeks:
                continue
            for g in games:
                h, a = g['home']['tid'], g['away']['tid']
                if (h, wk) not in wk_opt or (a, wk) not in wk_opt:
                    continue
                ho, ao = wk_opt[(h, wk)], wk_opt[(a, wk)]
                if ho != ao:
                    wif[h if ho > ao else a]['w'] += 1
                    wif[a if ho > ao else h]['l'] += 1
                hp, ap = g['home']['pts'], g['away']['pts']
                if hp != ap:
                    act[h if hp > ap else a]['w'] += 1
                    act[a if hp > ap else h]['l'] += 1
        ids = [t for t in tinfo] or sorted(wif)
        pf = {t: tinfo.get(t, {}).get('pf', 0) for t in ids}
        act_order = sorted(ids, key=lambda t: (-act[t]['w'], -pf[t]))
        opt_order = sorted(ids, key=lambda t: (-wif[t]['w'], -(iq.get(t, {}).get('optimal', 0))))
        whatif_rows = sorted([{
            'teamId': t, 'actW': act[t]['w'], 'actL': act[t]['l'],
            'optW': wif[t]['w'], 'optL': wif[t]['l'],
            'actRank': act_order.index(t) + 1, 'optRank': opt_order.index(t) + 1,
        } for t in ids], key=lambda x: x['optRank'])

    # ---- waiver value: undrafted players' started points ----
    drafted_ids = {b['pid'] for b in board if b['pid']}
    waiver_by_team = defaultdict(float)
    for wk, tid, pid, slot, pts, started in rows:
        if started and wk <= reg_weeks and pid not in drafted_ids:
            waiver_by_team[tid] += pts
    waiver_players = defaultdict(float)
    for (tid, pid), pts in started_by.items():
        if pid not in drafted_ids:
            waiver_players[pid] += pts
    waiver_top = []
    for pid, pts in sorted(waiver_players.items(), key=lambda x: -x[1])[:8]:
        p = pidx.get(pid) or pmeta.get(pid, {})
        waiver_top.append({'name': p.get('name', '?'), 'pos': p.get('pos', '?'),
                           'stPts': round(pts, 1), 'nfl': p.get('nfl', ''),
                           'teamId': (pidx.get(pid) or {}).get('mainTeam')})

    # ---- manager report card: the three true skills, luck kept separate ----
    report = []
    if has_rosters:
        def ranks(pairs, high_is_good=True):
            srt = sorted(pairs, key=lambda x: -x[1] if high_is_good else x[1])
            return {tid: i + 1 for i, (tid, _) in enumerate(srt)}
        ids = [t for t in tinfo] or sorted(iq)
        dr = {d['teamId']: d['ppd'] for d in draft_eff}
        draft_rank = ranks([(t, dr.get(t, 0)) for t in ids])
        lineup_rank = ranks([(t, iq.get(t, {}).get('eff', 0)) for t in ids])
        waiver_rank = ranks([(t, waiver_by_team.get(t, 0)) for t in ids])
        luck_rank = ranks([(t, tinfo.get(t, {}).get('luck', 0)) for t in ids])

        def grade(rank):
            pct = (rank - 1) / max(1, n_teams - 1)
            for cut, g in ((0.09, 'A+'), (0.2, 'A'), (0.32, 'B+'), (0.45, 'B'),
                           (0.6, 'C+'), (0.75, 'C'), (0.88, 'D'), (2, 'F')):
                if pct <= cut:
                    return g
        GPA = {'A+': 4.3, 'A': 4.0, 'B+': 3.3, 'B': 3.0, 'C+': 2.3, 'C': 2.0, 'D': 1.0, 'F': 0.0}
        GOOD = {'draft': 'drafted like a genius', 'lineup': 'set lineups like a surgeon',
                'waiver': 'owned the waiver wire'}
        BAD = {'draft': 'lit auction money on fire', 'lineup': 'benched the wrong guys',
               'waiver': 'ignored free agents'}
        for t in ids:
            gd, gl, gw = grade(draft_rank[t]), grade(lineup_rank[t]), grade(waiver_rank[t])
            gpa = round((GPA[gd] + GPA[gl] + GPA[gw]) / 3, 2)
            skill = {'draft': draft_rank[t], 'lineup': lineup_rank[t], 'waiver': waiver_rank[t]}
            best, worst = min(skill, key=skill.get), max(skill, key=skill.get)
            top_third, bot_third = max(2, n_teams // 3), n_teams - max(2, n_teams // 3)
            if skill[best] <= top_third and skill[worst] >= bot_third:
                verdict = f'{GOOD[best].capitalize()}, but {BAD[worst]}.'
            elif gpa >= 3.5:
                verdict = 'Complete performance across the board.'
            elif gpa >= 2.5:
                verdict = 'Solid fundamentals, no fatal flaw.'
            else:
                verdict = 'A rebuilding year on every front.'
            report.append({'teamId': t, 'gDraft': gd, 'gLineup': gl, 'gWaiver': gw,
                           'gLuck': grade(luck_rank[t]), 'gpa': gpa, 'verdict': verdict,
                           'waiverPts': round(waiver_by_team.get(t, 0), 1)})
        report.sort(key=lambda x: -x['gpa'])

    # ---- scoreboard (drop roster arrays where empty to save bytes) ----
    weeks_out = {}
    for wk_s, games in box.get('weeks', {}).items():
        weeks_out[wk_s] = [{
            'tier': g['tier'],
            'home': {'tid': g['home']['tid'], 'pts': g['home']['pts'], 'roster': g['home']['roster']},
            'away': {'tid': g['away']['tid'], 'pts': g['away']['pts'], 'roster': g['away']['roster']},
        } for g in games]

    bundle = {
        'year': year,
        'regWeeks': reg_weeks,
        'hasRosters': has_rosters,
        'hasTx': bool(moves or trades),
        'auctionDraft': auction,
        'slots': slots,
        'weeks': weeks_out,
        'pmeta': {str(k): [v['name'], v['pos'], v['nfl'], v['hs']] for k, v in pmeta.items()},
        'players': players,
        'lineupIQ': sorted(iq.values(), key=lambda x: -x['eff']),
        'draft': {'auction': auction, 'board': board},
        'moves': moves,
        'trades': trades,
        'usesFaab': uses_faab,
        'topAdds': top_adds,
        'posDNA': pos_dna,
        'franchiseAdv': franchise_adv,
        'mvps': {str(k): v for k, v in mvps.items()},
        'spotlight': spotlight,
        'draftValue': {'steals': steals, 'busts': busts, 'teamEff': draft_eff},
        'whatif': whatif_rows,
        'waiver': waiver_top,
        'report': report,
        'txCounts': dict(counts),
        'txByTeam': {str(k): v for k, v in per_team.items()},
    }
    os.makedirs(YEARS_DIR, exist_ok=True)
    path = os.path.join(YEARS_DIR, f'{year}.json')
    json.dump(bundle, open(path, 'w'))
    return {
        'year': year, 'hasRosters': has_rosters, 'hasTx': bool(moves or trades),
        'auctionDraft': auction, 'players': len(players),
        'games': sum(len(v) for v in weeks_out.values()),
        'trades': len(trades), 'tx': len(moves), 'picks': len(board),
        'kb': round(os.path.getsize(path) / 1024, 1),
    }

def main():
    site = json.load(open(os.path.join(SITE, 'data.json')))
    years = sorted(int(y) for y in site['seasons'])
    manifest = []
    for year in years:
        league = load(f'{DATA}/league_{year}.json')
        info = process_year(year, league, site['seasons'][str(year)]['teams'])
        manifest.append(info)
        flags = []
        if info['hasRosters']: flags.append('lineups')
        if info['hasTx']: flags.append('tx')
        flags.append('auction' if info['auctionDraft'] else 'snake')
        print(f"  {year}: {info['games']:>3} games, {info['players']:>3} players, "
              f"{info['picks']:>3} picks, {info['trades']:>2} trades, "
              f"{info['tx']:>4} tx, {info['kb']:>6}KB  [{', '.join(flags)}]")
    json.dump({'years': manifest}, open(os.path.join(SITE, 'index_years.json'), 'w'))
    total = sum(m['kb'] for m in manifest)
    print(f"wrote site/years/*.json ({total:.0f}KB total) + site/index_years.json")

if __name__ == '__main__':
    main()
