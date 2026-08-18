#!/usr/bin/env python3
"""Export the site's metric payloads from affl.db.

process_seasons.py still assembles the structural payload (weekly rosters,
player meta, transaction log, trades). This owns the *metrics*, computed once in
SQL so there is a single definition of each. It patches the per-season bundles
in place, replacing any key it is responsible for.

Owns:
  draftValue   steals / busts / per-team efficiency, all on points above
               replacement per dollar (v_draft_value)
  power        all-play record and PWR% (v_power)
  luckFG       FantasyGenius-style lucky wins / unlucky losses (v_luck)
  nflCap       NFL salary-cap total carried by each AFFL roster (v_team_nfl_cap)
  baselines    the replacement level used, so the UI can explain the number
  draftHoldout pre-aggregated auction cost-bucket PAR (Marimekko + early/late)
  posByWeek    started points by lineup slot, per team-week (stacked area)
"""
import json
import os
import sqlite3
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
SITE = os.path.join(HERE, 'site')
YEARS = os.path.join(SITE, 'years')
SITE_DATA = os.path.join(SITE, 'data.json')

BENCH = {'BN', 'IR'}
SLOT_LAYERS = ('QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DST')
BUCKETS = (
    ('$1', 1, 1),
    ('$2', 2, 2),
    ('$3–5', 3, 5),
    ('$6–10', 6, 10),
    ('$11–20', 11, 20),
    ('$21–40', 21, 40),
    ('$41–70', 41, 70),
    ('$71+', 71, 10**9),
)
CHEAP = {'$1', '$2', '$3–5'}


def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def r1(n):
    return None if n is None else round(float(n), 1)


def r3(n):
    return None if n is None else round(float(n), 3)


def norm_pos(pos):
    if pos in ('D/ST', 'DST', 'D-ST'):
        return 'DST'
    return pos


def slot_layer(slot):
    key = norm_pos(slot)
    return key if key in SLOT_LAYERS else None


def cost_bucket(bid):
    if bid is None or bid <= 0:
        return None
    for label, lo, hi in BUCKETS:
        if lo <= bid <= hi:
            return label
    return None


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------------ warehouse
def build_from_site():
    """Rebuild the metric tables ESPN dumps would have filled, from the
    committed site bundles. Raw data/*.json is gitignored; the year files
    already carry warehouse-exported PAR and weekly lineups."""
    site = load_json(SITE_DATA)
    if not site:
        raise SystemExit('site/data.json missing; cannot reconstruct warehouse')

    con = sqlite3.connect(':memory:')
    con.executescript(open(os.path.join(HERE, 'schema.sql')).read())

    members = [(mid, name, 0) for mid, name in site['members'].items()]
    con.executemany(
        'INSERT OR REPLACE INTO dim_member(member_id, display_name, is_active) VALUES (?,?,?)',
        members)
    active = set(site.get('activeOwners') or [])
    con.executemany('UPDATE dim_member SET is_active = 1 WHERE member_id = ?',
                    [(a,) for a in active])

    players = {}
    pseason = []
    drafts = []
    rosters = []
    matchups = []

    for year in sorted(int(y) for y in site['seasons']):
        s = site['seasons'][str(year)]
        bundle = load_json(os.path.join(YEARS, f'{year}.json')) or {}
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

        for pid_s, v in (bundle.get('pmeta') or {}).items():
            pid = int(pid_s)
            name = v[0] if len(v) > 0 else '?'
            pos = norm_pos(v[1] if len(v) > 1 else None)
            nfl = v[2] if len(v) > 2 else None
            hs = v[3] if len(v) > 3 else None
            # First season wins, matching build_db.py's setdefault from box scores.
            # Overwriting with a later draft-board pos would move hybrids (Taysom
            # Hill) onto TE and change v_baseline for that position.
            cur = players.get(pid)
            if cur is None:
                players[pid] = {'name': name, 'position': pos, 'hs': hs}
            else:
                if pos and (not cur['position'] or cur['position'] == '?'):
                    cur['position'] = pos
                if name and cur['name'] in ('?', None, ''):
                    cur['name'] = name
                if hs and not cur['hs']:
                    cur['hs'] = hs
            if nfl:
                pseason.append((year, pid, nfl))

        for p in (bundle.get('draft') or {}).get('board') or []:
            pid = p.get('pid')
            pos = norm_pos(p.get('pos'))
            if pid:
                cur = players.get(pid)
                if cur is None:
                    players[pid] = {'name': p.get('name') or '?', 'position': pos, 'hs': None}
                elif pos and (not cur['position'] or cur['position'] == '?'):
                    cur['position'] = pos
                if cur and p.get('name') and cur['name'] in ('?', None, ''):
                    cur['name'] = p['name']
            drafts.append((year, p.get('overall'), p.get('round'), p.get('pick'),
                           p.get('tid'), pid, p.get('bid') or 0, int(bool(p.get('keeper')))))

        reg = max(s['regWeeks']) if s.get('regWeeks') else 13
        for wk_s, games in (bundle.get('weeks') or {}).items():
            wk = int(wk_s)
            for g in games:
                h, a = g['home'], g['away']
                playoff = 1 if (g.get('tier', 'NONE') != 'NONE' or wk > reg) else 0
                matchups.append((year, wk, h['tid'], a['tid'], h.get('pts') or 0,
                                 a.get('pts') or 0, 1, g.get('tier', 'NONE'), playoff))
                matchups.append((year, wk, a['tid'], h['tid'], a.get('pts') or 0,
                                 h.get('pts') or 0, 0, g.get('tier', 'NONE'), playoff))
                for side in (h, a):
                    seen = set()
                    for row in side.get('roster') or []:
                        pid, slot, pts = row[0], row[1], row[2]
                        if pid in seen:
                            continue
                        seen.add(pid)
                        if pid not in players:
                            guess = slot_layer(slot)
                            players[pid] = {
                                'name': '?',
                                'position': guess if guess and guess != 'FLEX' else None,
                                'hs': None,
                            }
                        rosters.append((year, wk, side['tid'], pid, slot,
                                        pts or 0, 0 if slot in BENCH else 1))

    con.executemany("""INSERT OR REPLACE INTO dim_player
        (player_id, name, position, gsis_id, otc_id, headshot_url) VALUES (?,?,?,?,?,?)""",
        [(pid, v['name'], v['position'], None, None, v['hs'])
         for pid, v in players.items()])
    con.executemany(
        'INSERT OR REPLACE INTO player_season(season, player_id, nfl_team) VALUES (?,?,?)',
        pseason)
    con.executemany("""INSERT OR REPLACE INTO fact_draft_pick
        (season, overall, round, pick_in_round, team_id, player_id, bid, is_keeper)
        VALUES (?,?,?,?,?,?,?,?)""", drafts)
    con.executemany("""INSERT OR REPLACE INTO fact_roster_week
        (season, week, team_id, player_id, slot, points, started) VALUES (?,?,?,?,?,?,?)""",
                    rosters)
    con.executemany("""INSERT OR REPLACE INTO fact_matchup
        (season, week, team_id, opponent_id, points, opponent_points, is_home, tier, is_playoff)
        VALUES (?,?,?,?,?,?,?,?,?)""", matchups)
    con.commit()
    return con, {
        'source': 'site-json',
        'players': len(players),
        'drafts': len(drafts),
        'rosters': len(rosters),
    }


def open_warehouse():
    if os.path.exists(DB) and os.path.getsize(DB) > 0:
        con = sqlite3.connect(DB)
        has_view = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_draft_value'"
        ).fetchone()
        if has_view:
            return con, {'source': 'affl.db'}
        con.close()
    return build_from_site()


def verify_par(con):
    """Confirm reconstructed v_draft_value.par matches the committed export."""
    mismatches = []
    checked = 0
    for year in range(2018, 2026):
        path = os.path.join(YEARS, f'{year}.json')
        bundle = load_json(path)
        if not bundle:
            continue
        stored = (bundle.get('draftValue') or {}).get('parByOverall') or {}
        queried = {str(r['overall']): r['par'] for r in rows(con, """
            SELECT overall, par FROM v_draft_value
             WHERE season = ? AND par IS NOT NULL""", (year,))}
        for overall, par in stored.items():
            checked += 1
            q = queried.get(str(overall))
            if q is None or abs((q or 0) - par) > 0.05:
                mismatches.append((year, overall, par, q))
    return checked, mismatches


# --------------------------------------------------------------- year metrics
def export_year(con, year):
    path = os.path.join(YEARS, f'{year}.json')
    if not os.path.exists(path):
        return None
    bundle = json.load(open(path))

    baselines = rows(con, """
        SELECT position, demand, ROUND(rank_based,1) AS rankBased,
               ROUND(best_undrafted,1) AS bestUndrafted,
               ROUND(baseline_points,1) AS baseline
          FROM v_baseline WHERE season = ? ORDER BY baseline_points DESC""", (year,))

    dv = rows(con, """
        SELECT player_id AS pid, name, position AS pos, team_id AS tid, bid, overall,
               is_keeper AS keeper, ROUND(total_points,1) AS pts, ROUND(par,1) AS par,
               par_per_dollar AS parPerDollar, points_per_dollar AS ptsPerDollar
          FROM v_draft_value
         WHERE season = ? AND total_points IS NOT NULL""", (year,))

    auction = bool(bundle.get('auctionDraft'))
    # A steal has to actually beat replacement; ranking by PAR/$ alone would put
    # every $1 flyer on top regardless of whether it helped.
    scored = [d for d in dv if d['par'] is not None]
    steals = sorted([d for d in scored if d['par'] > 0],
                    key=lambda d: -(d['parPerDollar'] or 0))[:8]
    busts = sorted([d for d in scored if (d['bid'] or 0) >= (20 if auction else 0)],
                   key=lambda d: (d['par'] or 0))[:8]

    eff = rows(con, """
        SELECT dp.team_id AS teamId, SUM(dp.bid) AS spent,
               ROUND(SUM(COALESCE(v.total_points,0)),1) AS pts,
               ROUND(SUM(COALESCE(v.par,0)),1) AS par,
               ROUND(SUM(COALESCE(v.par,0)) / MAX(SUM(dp.bid),1), 2) AS parPerDollar
          FROM fact_draft_pick dp
          LEFT JOIN v_draft_value v ON v.season = dp.season AND v.overall = dp.overall
         WHERE dp.season = ? GROUP BY dp.team_id
         ORDER BY parPerDollar DESC""", (year,))

    power = rows(con, """
        SELECT team_id AS teamId, allplay_w AS w, allplay_l AS l,
               ROUND(power_pct*100,1) AS pwrPct
          FROM v_power WHERE season = ? ORDER BY power_pct DESC""", (year,))

    luck = rows(con, """
        SELECT team_id AS teamId, lucky_wins AS lucky,
               unlucky_losses AS unlucky, net_luck AS net
          FROM v_luck WHERE season = ? ORDER BY net_luck DESC""", (year,))

    cap = rows(con, """
        SELECT team_id AS teamId, players_matched AS matched,
               total_cap_hit AS totalCap, avg_cap_hit AS avgCap,
               priciest_cap_hit AS maxCap
          FROM v_team_nfl_cap WHERE season = ? ORDER BY total_cap_hit DESC""", (year,))

    capFinal = rows(con, """
        SELECT team_id AS teamId, players_matched AS matched,
               total_cap_hit AS totalCap, starters_cap_hit AS startersCap,
               avg_cap_hit AS avgCap, priciest_cap_hit AS maxCap
          FROM v_team_nfl_cap_final WHERE season = ? ORDER BY total_cap_hit DESC""", (year,))

    # A player can pass through several AFFL rosters in one season, so credit the
    # team that held him the longest instead of listing him once per team.
    capTop = rows(con, """
        WITH held AS (
          SELECT r.player_id, r.team_id, COUNT(*) AS wks,
                 ROW_NUMBER() OVER (PARTITION BY r.player_id
                                    ORDER BY COUNT(*) DESC, r.team_id) AS rn
            FROM fact_roster_week r
           WHERE r.season = ?
           GROUP BY r.player_id, r.team_id)
        SELECT h.team_id AS teamId, p.name, p.position AS pos,
               c.nfl_team AS nfl, ROUND(c.cap_hit) AS cap, h.wks AS weeks
          FROM held h
          JOIN dim_player p   ON p.player_id = h.player_id
          JOIN v_player_cap c ON c.season = ? AND c.player_id = h.player_id
         WHERE h.rn = 1
         ORDER BY c.cap_hit DESC LIMIT 12""", (year, year))

    # PAR for every pick, so the full board can show the column rather than only
    # the sixteen rows that make the steals/busts lists
    par_by_overall = {str(d['overall']): d['par'] for d in dv if d['par'] is not None}

    bundle['draftValue'] = {'steals': steals, 'busts': busts, 'teamEff': eff,
                            'auction': auction, 'baselines': baselines,
                            'parByOverall': par_by_overall}
    bundle['power'] = power
    bundle['luckFG'] = luck
    bundle['nflCap'] = {'byTeam': cap, 'final': capFinal, 'topPlayers': capTop}
    json.dump(bundle, open(path, 'w'))
    return {'year': year, 'steals': len(steals), 'power': len(power),
            'cap_teams': len(cap), 'baselines': len(baselines)}


# ---------------------------------------------------------- holdout + pos week
def _mean(vals):
    return None if not vals else sum(vals) / len(vals)


def _examples(picks, limit=3):
    top = sorted(picks, key=lambda p: (-(p['par'] or 0), p['overall']))[:limit]
    return [{'name': p['name'], 'year': p['season'], 'par': r1(p['par']),
             'overall': p['overall'], 'bid': p['bid'], 'pos': p['position']}
            for p in top]


def _slice_payload(picks, cheap):
    scored = [p for p in picks if p['par'] is not None]
    pars = [p['par'] for p in scored]
    spend = sum(p['bid'] or 0 for p in picks)
    out = {
        'n': len(scored),
        'nNominated': len(picks),
        'spend': spend,
        'meanPar': r1(_mean(pars)),
        'meanOverall': r1(_mean([p['overall'] for p in scored])),
    }
    if cheap:
        out['examples'] = _examples(scored)
    return out


def _pos_slices(picks, cheap):
    by_pos = defaultdict(list)
    for p in picks:
        by_pos[p['position'] or '?'].append(p)
    order = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
    keys = [k for k in order if k in by_pos] + sorted(k for k in by_pos if k not in order)
    return [{'pos': k, **_slice_payload(by_pos[k], cheap)} for k in keys]


def _continuous(picks, bins=5):
    if not picks:
        return []
    ordered = sorted(picks, key=lambda p: p['overall'])
    n = len(ordered)
    out = []
    for i in range(bins):
        lo = int(i * n / bins)
        hi = int((i + 1) * n / bins)
        chunk = ordered[lo:hi]
        if not chunk:
            continue
        out.append({
            'q': i + 1,
            'n': len(chunk),
            'meanOverall': r1(_mean([p['overall'] for p in chunk])),
            'meanPar': r1(_mean([p['par'] for p in chunk])),
        })
    return out


def _aggregate(picks):
    """picks already filtered to auction + scored + assigned half (or keeper)."""
    comparable = [p for p in picks if not p['is_keeper'] and p.get('half') and p['par'] is not None]
    spend_all = sum(p['bid'] or 0 for p in picks)
    by_b = defaultdict(list)
    for p in picks:
        by_b[p['bucket']].append(p)

    mekko, scatter, continuous = [], [], []
    for label, _, _ in BUCKETS:
        group = by_b.get(label) or []
        if not group:
            continue
        cheap = label in CHEAP
        early = [p for p in group if p.get('half') == 'early']
        late = [p for p in group if p.get('half') == 'late']
        spend = sum(p['bid'] or 0 for p in group)
        scored_group = [p for p in group if p['par'] is not None]
        pars = [p['par'] for p in scored_group]
        mekko.append({
            'id': label,
            'n': len(scored_group),
            'nNominated': len(group),
            'spend': spend,
            'spendShare': r3(spend / spend_all) if spend_all else 0,
            'meanPar': r1(_mean(pars)),
            'slices': {
                'early': _slice_payload(early, cheap),
                'late': _slice_payload(late, cheap),
            },
            'byPos': _pos_slices(group, cheap),
        })
        e_mean = _mean([p['par'] for p in early if p['par'] is not None])
        l_mean = _mean([p['par'] for p in late if p['par'] is not None])
        scatter.append({
            'id': label,
            'early': _slice_payload(early, cheap),
            'late': _slice_payload(late, cheap),
            'delta': r1((l_mean - e_mean) if e_mean is not None and l_mean is not None else None),
        })
        continuous.append({
            'id': label,
            'points': _continuous([p for p in group if not p['is_keeper'] and p['par'] is not None]),
        })

    late_worse = sum(1 for b in scatter if b['delta'] is not None and b['delta'] < 0)
    late_better = sum(1 for b in scatter if b['delta'] is not None and b['delta'] > 0)
    b1 = next((b for b in scatter if b['id'] == '$1'), None)
    claim = None
    if b1 and b1['early']['meanPar'] is not None and b1['late']['meanPar'] is not None:
        claim = (
            f"Ticket holdouts lose: later nominations in the same cost bucket return "
            f"less mean PAR in {late_worse} of {len(scatter)} buckets. "
            f"$1 late {b1['late']['meanPar']:.1f} vs early {b1['early']['meanPar']:.1f}"
        )
    return {
        'n': len([p for p in picks if p['par'] is not None]),
        'nNominated': len(picks),
        'nComparable': len(comparable),
        'spend': spend_all,
        'lateWorse': late_worse,
        'lateBetter': late_better,
        'claim': claim,
        'mekko': mekko,
        'scatter': scatter,
        'continuous': continuous,
    }


def _assign_halves(picks):
    """Split by nomination order in the bucket, not by who later scored.

    A $1 flyer who never posted points still used a nomination slot. Mean PAR
    then drops those rows. A single pick in a (season, bucket) is early — there
    is no second half to compare it to.
    """
    groups = defaultdict(list)
    for p in picks:
        p['bucket'] = cost_bucket(p['bid'])
        p['half'] = None
        if p['bucket'] and not p['is_keeper']:
            groups[(p['season'], p['bucket'])].append(p)
    for _, group in groups.items():
        group.sort(key=lambda r: r['overall'])
        n = len(group)
        mid = n if n == 1 else n // 2
        for i, row in enumerate(group):
            row['half'] = 'early' if i < mid else 'late'
    return picks


def load_holdout_picks():
    """Auction picks with the PAR already exported from v_draft_value.

    Reconstructing dim_player.position from later seasons can move a hybrid
    (Taysom Hill) onto TE and change that year's baseline. The live board's
    parByOverall is the warehouse number we refuse to invent past.
    """
    picks = []
    snake, auction_no_par, scored = [], [], []
    keepers = 0
    for year in range(2014, 2026):
        bundle = load_json(os.path.join(YEARS, f'{year}.json'))
        if not bundle:
            continue
        auction = bool(bundle.get('auctionDraft') or (bundle.get('draft') or {}).get('auction'))
        has = bool(bundle.get('hasRosters'))
        if not auction:
            snake.append(year)
        elif not has:
            auction_no_par.append(year)
        else:
            scored.append(year)
        par_idx = (bundle.get('draftValue') or {}).get('parByOverall') or {}
        for p in (bundle.get('draft') or {}).get('board') or []:
            if p.get('keeper'):
                keepers += 1
            bid = p.get('bid') or 0
            if bid <= 0:
                continue
            par = par_idx.get(str(p['overall']))
            if par is None:
                par = par_idx.get(p['overall'])
            picks.append({
                'season': year,
                'overall': p['overall'],
                'team_id': p.get('tid'),
                'player_id': p.get('pid'),
                'name': p.get('name'),
                'position': norm_pos(p.get('pos')),
                'bid': bid,
                'is_keeper': int(bool(p.get('keeper'))),
                'total_points': p.get('pts'),
                'par': par,
                'par_per_dollar': None,
            })
    return picks, {
        'snake': snake,
        'auction_no_par': auction_no_par,
        'scored': scored,
        'keepers': keepers,
    }


def export_holdout(con):
    picks, meta = load_holdout_picks()
    snake = meta['snake']
    auction_no_par = meta['auction_no_par']
    scored = meta['scored']
    keepers = meta['keepers']

    auction_picks = [p for p in picks if p['season'] in scored]
    _assign_halves(auction_picks)
    scored_picks = [p for p in auction_picks if p['par'] is not None]

    by_season = {}
    for year in scored:
        year_picks = [p for p in auction_picks if p['season'] == year]
        by_season[str(year)] = _aggregate(year_picks)

    pooled = _aggregate(auction_picks)
    grain = (
        "one row per drafted player-season · auction bids only (bid > 0) · "
        "PAR from v_draft_value · early/late = first vs second half of overall "
        "pick order within each (season, cost bucket) · keepers excluded from "
        "the early/late split · seasons without scored rosters dropped from PAR"
    )
    seasons_label = f"{scored[0]}–{scored[-1]}" if scored else ""
    claim = pooled['claim']
    if claim:
        claim = f"{claim} ({seasons_label} auction, non-keepers, scored rosters)."

    payload = {
        'metric': 'PAR',
        'sourceView': 'v_draft_value',
        'sourceField': 'draftValue.parByOverall',
        'also': 'par_per_dollar',
        'warp': False,
        'grain': grain,
        'subtitle': (
            f"Auction player-seasons {seasons_label} · column width = share of draft spend · "
            f"height stacks = early/late nomination half · color = mean PAR"
        ),
        'buckets': [b[0] for b in BUCKETS],
        'bucketRule': '$1 | $2 | $3–5 | $6–10 | $11–20 | $21–40 | $41–70 | $71+',
        'histogramNote': (
            'Default buckets kept after the bid histogram: 544 ones, 234 twos, '
            'then a long right tail. $71+ is labeled with its small n.'
        ),
        'keepers': {
            'count': keepers,
            'note': (
                'ESPN stored is_keeper = 0 on every AFFL draft pick in this warehouse. '
                'The early/late split still excludes keepers so a future keeper class '
                'does not leak into the holdout comparison.'
            ),
        },
        'excludedSeasons': {
            'snake': snake,
            'auctionNoPar': auction_no_par,
        },
        'scoredAuctionSeasons': scored,
        'claim': claim,
        'pooled': pooled,
        'bySeason': by_season,
    }
    path = os.path.join(SITE, 'draft_holdout.json')
    with open(path, 'w') as f:
        json.dump(payload, f, separators=(',', ':'))
    return payload


def export_pos_by_week():
    """Started lineup-slot points by team-week. Grain is the roster slot
    (FLEX stays FLEX), not the player's listed position."""
    out = {}
    for year in range(2014, 2026):
        bundle = load_json(os.path.join(YEARS, f'{year}.json'))
        if not bundle:
            continue
        teams = {}
        for wk_s, games in (bundle.get('weeks') or {}).items():
            wk = int(wk_s)
            for g in games:
                for side in (g.get('home'), g.get('away')):
                    if not side:
                        continue
                    roster = side.get('roster') or []
                    if not roster:
                        continue
                    tid = str(side['tid'])
                    rec = teams.setdefault(tid, {'weeks': [], 'slots': {s: [] for s in SLOT_LAYERS}})
                    # one value per slot this week (sum if two RBs etc.)
                    week_slots = {s: 0.0 for s in SLOT_LAYERS}
                    started = False
                    for row in roster:
                        slot = slot_layer(row[1])
                        if slot is None:
                            continue
                        week_slots[slot] += float(row[2] or 0)
                        started = True
                    if not started:
                        continue
                    rec['weeks'].append(wk)
                    for s in SLOT_LAYERS:
                        rec['slots'][s].append(r1(week_slots[s]))
        # keep week order stable
        for rec in teams.values():
            order = sorted(range(len(rec['weeks'])), key=lambda i: rec['weeks'][i])
            rec['weeks'] = [rec['weeks'][i] for i in order]
            rec['slots'] = {s: [rec['slots'][s][i] for i in order] for s in SLOT_LAYERS}
        out[str(year)] = {
            'slots': list(SLOT_LAYERS),
            'grain': 'started points by lineup slot · that season’s roster weeks only',
            'teams': teams,
        }
    path = os.path.join(SITE, 'pos_by_week.json')
    with open(path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    return {y: len(v['teams']) for y, v in out.items()}


def main():
    con, info = open_warehouse()
    print(f"warehouse source: {info.get('source')} "
          f"({', '.join(f'{k}={v}' for k, v in info.items() if k != 'source')})")

    checked, mismatches = verify_par(con)
    if mismatches:
        print(f"PAR verify: {len(mismatches)} reconstructed cells differ / {checked} "
              f"(using committed parByOverall for the site payload)")
        for row in mismatches[:5]:
            print('  ', row)
    else:
        print(f"PAR verify: {checked} cells match reconstructed v_draft_value")

    if info.get('source') == 'affl.db':
        years = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
        for y in years:
            yr = export_year(con, y)
            if yr:
                print(f"  {yr['year']}: {yr['steals']} steals · {yr['power']} power rows "
                      f"· {yr['cap_teams']} teams w/ cap · {yr['baselines']} baselines")
        print('site/years/*.json patched from affl.db')
    else:
        print('site-json warehouse: leaving existing year metric patches untouched')

    holdout = export_holdout(con)
    print(f"draft_holdout.json: n={holdout['pooled']['n']} "
          f"claim={holdout['claim']}")
    teams = export_pos_by_week()
    print('pos_by_week.json:',
          ', '.join(f"{y}:{n}" for y, n in teams.items()))


if __name__ == '__main__':
    main()
