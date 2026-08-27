#!/usr/bin/env python3
"""Per-season processing: lineups, player profiles, draft boards, transactions.

Writes one compact bundle per year to site/years/{year}.json plus a small
site/index_years.json manifest the front end reads first. Splitting by year keeps
initial page load small — the front end lazy-loads only the season being viewed.

Data availability (see fetch.py): drafts 2014+, lineups & transactions 2018+.
"""
import json
import sys
import csv
import os
import re
from collections import defaultdict, Counter

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

POOL_POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}

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


def load_player_pool(year):
    """-> espn_id -> meta, from the ESPN player pool shipped with that draft.

    nflverse keys on espn_id, which is blank for a lot of pre-2018 players and
    absent entirely for anyone off an NFL roster by the time the feed was cut
    (Ray Rice in 2014). The pool is ESPN's own snapshot of everyone draftable
    that season, so it names every pick that nflverse cannot.

    Name and defaultPositionId are era-correct (position matches nflverse on
    99.1-99.7% of overlapping players). proTeamId is NOT: ESPN re-serves these
    archives with a later snapshot's club, so it disagrees with the season's
    real roster on 13-18% of players (Alex Smith reads WSH in 2017, a year
    before he was traded there). Team is therefore left blank for pool-only
    players rather than asserting the wrong era's club.
    """
    path = f'{DATA}/player_pool_{year}.json'
    if not os.path.exists(path):
        return {}
    pool = {}
    for p in json.load(open(path)):
        pid, name = p.get('id'), (p.get('fullName') or '').strip()
        if pid is None or not name:
            continue
        pool[pid] = {'name': name,
                     'pos': POOL_POS.get(p.get('defaultPositionId'), '?'),
                     'nfl': '', 'hs': ''}
    return pool


_CROSS_SEASON = None

def cross_season_meta(pid):
    """Last-resort name lookup across every other season's feeds.

    A player drafted in his rookie year can be missing from that season's roster
    file yet present in the next one (Bryce Young, drafted 2023, first appears in
    roster_2024). Name and position carry across seasons; pro team does not, so
    it stays blank rather than asserting the wrong era's club.
    """
    global _CROSS_SEASON
    if _CROSS_SEASON is None:
        _CROSS_SEASON = {}
        for year in range(2014, 2027):
            p = f'{DATA}/roster_{year}.csv'
            if not os.path.exists(p):
                continue
            for row in csv.DictReader(open(p)):
                eid, name = row.get('espn_id'), (row.get('full_name') or '').strip()
                if not eid or not name:
                    continue
                try:
                    eid = int(eid)
                except ValueError:
                    continue
                _CROSS_SEASON.setdefault(eid, {
                    'name': name, 'pos': (row.get('position') or '').strip() or '?',
                    'nfl': '', 'hs': ''})
            for eid, m in load_player_pool(year).items():
                _CROSS_SEASON.setdefault(eid, dict(m))
    return _CROSS_SEASON.get(pid)

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


def missing_team(tid):
    """FA / unset. ESPN uses 0 and -1 as drop-to-wire sentinels, not clubs."""
    return tid in (None, 0, -1, '')


def resolve_accept_items(accept, by_id):
    """Join TRADE_ACCEPT.rel → TRADE_PROPOSAL and fill one-sided from/to.

    ESPN often stores the players on the proposal and emits ACCEPT as a bare
    status event. One-sided rows (only from or only to) are completed from the
    proposal item with the same pid, or from the other party in the same deal.
    DROP-to-FA is not a trade leg.
    """
    if by_id is None:
        by_id = {}
    items = [dict(i) for i in (accept.get('items') or [])]
    rel = accept.get('rel')
    proposal = by_id.get(rel) if rel else None
    if proposal:
        prop_items = [dict(i) for i in (proposal.get('items') or [])]
        if not items:
            items = prop_items
        else:
            by_pid = {i.get('pid'): i for i in prop_items if i.get('pid') is not None}
            for i in items:
                p = by_pid.get(i.get('pid'))
                if not p:
                    continue
                if missing_team(i.get('from')) and not missing_team(p.get('from')):
                    i['from'] = p['from']
                if missing_team(i.get('to')) and not missing_team(p.get('to')):
                    i['to'] = p['to']
            have = {i.get('pid') for i in items}
            for p in prop_items:
                if p.get('pid') not in have:
                    items.append(p)

    parties = []
    seen = set()
    for i in items:
        for side in (i.get('from'), i.get('to')):
            if not missing_team(side) and side not in seen:
                seen.add(side)
                parties.append(side)

    out = []
    for i in items:
        if i.get('pid') is None:
            continue
        if (i.get('act') or '').upper() == 'DROP':
            continue
        frm, to = i.get('from'), i.get('to')
        if missing_team(frm) or missing_team(to):
            if len(parties) == 2:
                a, b = parties[0], parties[1]
                if not missing_team(frm) and missing_team(to):
                    to = b if frm == a else a if frm == b else None
                elif not missing_team(to) and missing_team(frm):
                    frm = b if to == a else a if to == b else None
        if missing_team(frm) or missing_team(to) or frm == to:
            continue
        i['from'] = frm
        i['to'] = to
        out.append(i)
    return out


def collect_accept_trades(tx_list, pmeta=None):
    """ACCEPT trades after proposal join + one-sided fill. No reconstruction."""
    pmeta = pmeta or {}
    by_id = {t['id']: t for t in tx_list if t.get('id')}
    seen_itemsets = set()
    trades = []
    accept_moves = set()
    for t in tx_list:
        if t.get('type') != 'TRADE_ACCEPT':
            continue
        items = resolve_accept_items(t, by_id)
        if not items:
            continue
        key = frozenset((i['pid'], i['from'], i['to']) for i in items)
        if key in seen_itemsets:
            continue
        seen_itemsets.add(key)
        sides = defaultdict(list)
        for i in items:
            m = pmeta.get(i['pid'], {})
            sides[i['to']].append({'pid': i['pid'], 'from': i['from'],
                                   'name': m.get('name', f"Player {i['pid']}"),
                                   'pos': m.get('pos', '?')})
            accept_moves.add((i['pid'], i['from'], i['to'], t.get('wk')))
        trades.append({'wk': t.get('wk'), 'date': t.get('date'),
                       'sides': [{'tid': tid, 'got': got} for tid, got in sides.items()]})
    return trades, accept_moves, by_id


def build_season_trades(year, tx_list, pmeta, draft_picks, roster_rows, moves):
    """ACCEPT join first; 2018+ roster-delta reconstruction for empty accepts.

    2014–17 have no ESPN tx log — do not invent trades from draft-only ownership.
    """
    trades, accept_moves, _by_id = collect_accept_trades(tx_list, pmeta)
    if year < 2018:
        return trades, accept_moves

    owner_by_week = defaultdict(dict)
    for p in draft_picks:
        pid = p.get('pid')
        if pid is not None:
            owner_by_week[pid][0] = p['tid']
    for wk, tid, pid, slot, pts, started in roster_rows:
        owner_by_week[pid][wk] = tid

    wire_events = set()
    for m in moves:
        dest = m['tid']
        for a in m.get('add') or []:
            add_team = a.get('to') if a.get('to') is not None else dest
            wire_events.add((a['pid'], m['wk'], add_team))

    transitions = []
    for pid, byw in owner_by_week.items():
        wks = sorted(byw)
        for a_wk, b_wk in zip(wks, wks[1:]):
            if byw[a_wk] == byw[b_wk]:
                continue
            dest = byw[b_wk]
            if (pid, b_wk, dest) in wire_events:
                continue
            if any((pid, byw[a_wk], dest, w) in accept_moves
                   for w in (b_wk - 1, b_wk, b_wk + 1)):
                continue
            transitions.append({'pid': pid, 'from': byw[a_wk], 'to': dest, 'wk': b_wk})

    feed_dates = []
    for t in tx_list:
        pids = {i['pid'] for i in (t.get('items') or []) if i.get('pid')}
        if pids and t.get('date'):
            feed_dates.append((pids, t.get('wk'), t['date']))

    def trade_date(pids, wk):
        best = None
        for fp, fwk, fdate in feed_dates:
            if not (pids & fp):
                continue
            gap = abs((fwk or 0) - wk)
            if gap <= 2 and (best is None or gap < best[0]):
                best = (gap, fdate)
        return best[1] if best else None

    by_week_pair = defaultdict(list)
    for tr in transitions:
        by_week_pair[(tr['wk'], frozenset((tr['from'], tr['to'])))].append(tr)

    for (wk, pair), items in sorted(by_week_pair.items(), key=lambda x: x[0][0]):
        sides = defaultdict(list)
        for i in items:
            m = pmeta.get(i['pid'], {})
            sides[i['to']].append({'pid': i['pid'], 'from': i['from'],
                                   'name': m.get('name', f"Player {i['pid']}"),
                                   'pos': m.get('pos', '?')})
        pids = {i['pid'] for i in items}
        trades.append({'wk': wk, 'date': trade_date(pids, wk),
                       'sides': [{'tid': tid, 'got': got} for tid, got in sides.items()]})
    return trades, accept_moves


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
    # lineups at all. Resolve those from the nflverse roster, then the season's
    # own ESPN player pool, then any other season, so no id leaks to the UI.
    pool = load_player_pool(year)
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
            continue
        m = pool.get(pid) or cross_season_meta(pid)
        if m:
            pmeta[pid] = dict(m)

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
    # A raw ESPN id on the draft board means every name source missed the pick.
    unnamed_picks = [b['pid'] for b in board if b['pid'] and b['pid'] not in pmeta]

    # ---- transactions & trades ----
    # ESPN records traded players on the TRADE_PROPOSAL and emits TRADE_ACCEPT as
    # a bare status event carrying relatedTransactionId, so accepts must be joined
    # back to their proposal to recover who actually moved.

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

    moves, trades = [], []
    # Deliberately no proposal/decline counters here: ESPN stamps transactions
    # with the EXECUTING team, and this league's commissioner pushes trades
    # through for other managers, which inflated his team ~4x. Waiver and
    # free-agent attribution is safe (verified: executing team == receiving team).
    per_team = defaultdict(lambda: {'waiver': 0, 'fa': 0, 'drop': 0, 'trades': 0, 'spent': 0})
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

    # ---- trades: ACCEPT joined to proposal; 2018+ roster-delta reconstruction ----
    # Executing-team on the feed is the commissioner, not a party. Item from/to
    # is usable once empty ACCEPTs are joined back to TRADE_PROPOSAL via rel.
    # One-sided ESPN rows are filled from the proposal or the paired item — not
    # dropped on a truthy from/to check. 2014–17 have no tx log; do not invent.
    # Draft board is week-0 ownership so post-draft pre-W1 swaps are trades.
    # Waiver/FA adds suppress only the add week, and only if dest == add team.
    # One-way roster jumps stay Traded in — no reverse player required.
    trades, accept_moves = build_season_trades(
        year, txd.get('tx', []), pmeta, draft.get('picks', []), rows, moves)

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

    biggest = max(trades, key=lambda t: sum(len(s['got']) for s in t['sides'])) if trades else None
    moved = Counter()
    for tr in trades:
        for s in tr['sides']:
            for g in s['got']:
                moved[(g['pid'], g['name'], g['pos'])] += 1
    most_traded = [{'name': k[1], 'pos': k[2], 'n': n}
                   for k, n in moved.most_common(5) if n > 1]

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
        'biggestSwap': ({'wk': biggest['wk'],
                         'n': sum(len(s['got']) for s in biggest['sides']),
                         'teams': [s['tid'] for s in biggest['sides']]} if biggest else None),
        'mostTraded': most_traded,
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
        'unnamedPicks': unnamed_picks,
        'kb': round(os.path.getsize(path) / 1024, 1),
    }

def patch_year_trades(year, site_bundle=None):
    """Rewrite only trades-related keys. Leaves export_site metrics intact."""
    path = os.path.join(YEARS_DIR, f'{year}.json')
    if not os.path.exists(path):
        return None
    bundle = json.load(open(path))
    txd = load(f'{DATA}/tx_{year}.json') or {'tx': []}
    draft = load(f'{DATA}/draft_{year}.json') or {'picks': []}
    pmeta = {}
    for k, v in (bundle.get('pmeta') or {}).items():
        try:
            pid = int(k)
        except (TypeError, ValueError):
            continue
        pmeta[pid] = {'name': v[0] if v else f'Player {pid}',
                      'pos': v[1] if v and len(v) > 1 else '?'}
    rows = []
    for wk_s, games in (bundle.get('weeks') or {}).items():
        wk = int(wk_s)
        for g in games:
            for side in ('home', 'away'):
                s = g[side]
                for pid, slot, pts in s.get('roster') or []:
                    rows.append((wk, s['tid'], pid, slot, pts,
                                 slot not in STARTER_SLOTS_EXCLUDE))
    trades, _ = build_season_trades(
        year, txd.get('tx', []), pmeta, draft.get('picks', []),
        rows, bundle.get('moves') or [])
    bundle['trades'] = trades
    bundle['hasTx'] = bool(bundle.get('moves') or trades)
    biggest = max(trades, key=lambda t: sum(len(s['got']) for s in t['sides'])) if trades else None
    bundle['biggestSwap'] = ({'wk': biggest['wk'],
                              'n': sum(len(s['got']) for s in biggest['sides']),
                              'teams': [s['tid'] for s in biggest['sides']]} if biggest else None)
    moved = Counter()
    for tr in trades:
        for s in tr['sides']:
            for g in s['got']:
                moved[(g['pid'], g['name'], g['pos'])] += 1
    bundle['mostTraded'] = [{'name': k[1], 'pos': k[2], 'n': n}
                            for k, n in moved.most_common(5) if n > 1]
    tx_by = bundle.get('txByTeam') or {}
    for rec in tx_by.values():
        if isinstance(rec, dict):
            rec['trades'] = 0
    for tr in trades:
        for s in tr['sides']:
            rec = tx_by.setdefault(str(s['tid']),
                                   {'waiver': 0, 'fa': 0, 'drop': 0, 'trades': 0, 'spent': 0})
            rec['trades'] = rec.get('trades', 0) + 1
    bundle['txByTeam'] = tx_by
    json.dump(bundle, open(path, 'w'))
    return {'year': year, 'trades': len(trades),
            'kb': round(os.path.getsize(path) / 1024, 1)}


def main():
    trades_only = '--trades-only' in sys.argv
    if trades_only:
        years = []
        for a in sys.argv[1:]:
            if a.isdigit():
                years.append(int(a))
        if not years:
            years = list(range(2014, 2026))
        for year in years:
            info = patch_year_trades(year)
            if info:
                print(f"  {year}: {info['trades']:>2} trades  {info['kb']:>6}KB  [trades-only]")
        return

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
        if info['unnamedPicks']:
            flags.append(f"UNNAMED {info['unnamedPicks']}")
        print(f"  {year}: {info['games']:>3} games, {info['players']:>3} players, "
              f"{info['picks']:>3} picks, {info['trades']:>2} trades, "
              f"{info['tx']:>4} tx, {info['kb']:>6}KB  [{', '.join(flags)}]")
    json.dump({'years': manifest}, open(os.path.join(SITE, 'index_years.json'), 'w'))
    total = sum(m['kb'] for m in manifest)
    print(f"wrote site/years/*.json ({total:.0f}KB total) + site/index_years.json")
    leaked = {m['year']: m['unnamedPicks'] for m in manifest if m['unnamedPicks']}
    if leaked:
        print(f"FAIL: draft picks with no resolvable name: {leaked}")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main() or 0)
