#!/usr/bin/env python3
"""Player-level analytics for 2025: lineup IQ, draft ROI, position DNA,
and nflverse advanced-stat joins (EPA / WOPR / target share).
Appends a `nextgen` block to site/data.json."""
import json
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, 'data')
SITE = os.path.join(HERE, 'site', 'data.json')

POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}
BENCH, IR = 20, 21
REG_WEEKS = 14  # weeks 1-14 regular season, 15-17 playoffs

SEASON = 2025
BENCH_SLOTS = {'BN', 'IR'}

def load_boxscores():
    """Read the compact per-season bundle written by fetch.py."""
    box = json.load(open(f'{DATA}/box_{SEASON}.json'))
    meta = box['players']            # pid(str) -> [name, pos, nflTeam]
    rows = []
    for wk_s, games in box['weeks'].items():
        wk = int(wk_s)
        for g in games:
            for side in ('home', 'away'):
                s = g[side]
                for pid, slot, pts in s['roster']:
                    m = meta.get(str(pid), ['?', '?', ''])
                    rows.append({
                        'week': wk, 'teamId': s['tid'],
                        'pid': pid, 'name': m[0], 'pos': m[1],
                        'slot': slot, 'pts': pts,
                        'started': slot not in BENCH_SLOTS,
                    })
    return rows

def optimal_points(entries):
    """Exact optimum for 1QB/2RB/2WR/1TE/1FLEX/1DST/1K."""
    by = defaultdict(list)
    for e in entries:
        by[e['pos']].append(e['pts'])
    for k in by:
        by[k].sort(reverse=True)
    total = 0.0
    total += sum(by['QB'][:1]) + sum(by['DST'][:1]) + sum(by['K'][:1])
    rb, wr, te = by['RB'], by['WR'], by['TE']
    total += sum(rb[:2]) + sum(wr[:2]) + sum(te[:1])
    flex_pool = rb[2:3] + wr[2:3] + te[1:2]
    total += max(flex_pool) if flex_pool else 0.0
    return round(total, 2)

def main():
    rows = load_boxscores()
    site = json.load(open(SITE))
    teams25 = {t['id']: t for t in site['seasons']['2025']['teams']}

    # ---------- lineup IQ ----------
    week_team = defaultdict(list)
    for r in rows:
        week_team[(r['week'], r['teamId'])].append(r)

    iq = {tid: {'actual': 0, 'optimal': 0, 'weeks': 0, 'perfect': 0} for tid in teams25}
    for (wk, tid), entries in week_team.items():
        if wk > REG_WEEKS or tid not in iq:
            continue
        actual = round(sum(e['pts'] for e in entries if e['started']), 2)
        optimal = optimal_points(entries)
        b = iq[tid]
        b['actual'] += actual
        b['optimal'] += optimal
        b['weeks'] += 1
        if optimal - actual < 0.005:
            b['perfect'] += 1

    lineup_iq = []
    for tid, b in iq.items():
        eff = b['actual'] / b['optimal'] if b['optimal'] else 0
        lineup_iq.append({
            'teamId': tid, 'actual': round(b['actual'], 1), 'optimal': round(b['optimal'], 1),
            'eff': round(eff, 4), 'wasted': round(b['optimal'] - b['actual'], 1),
            'perfect': b['perfect'],
        })
    lineup_iq.sort(key=lambda x: -x['eff'])

    # ---------- position DNA (started points by position, reg season) ----------
    dna = {tid: defaultdict(float) for tid in teams25}
    for r in rows:
        if r['started'] and r['week'] <= REG_WEEKS and r['teamId'] in dna:
            dna[r['teamId']][r['pos']] += r['pts']
    pos_dna = {tid: {p: round(v, 1) for p, v in d.items()} for tid, d in dna.items()}

    # ---------- franchise MVPs (started points, full season) ----------
    started_pts = defaultdict(float)   # (tid, pid) -> pts
    pname, ppos = {}, {}
    for r in rows:
        if r['started']:
            started_pts[(r['teamId'], r['pid'])] += r['pts']
            pname[r['pid']] = r['name']
            ppos[r['pid']] = r['pos']
    mvps = {}
    for (tid, pid), pts in started_pts.items():
        if tid not in mvps or pts > mvps[tid]['pts']:
            mvps[tid] = {'pid': pid, 'name': pname[pid], 'pos': ppos[pid], 'pts': round(pts, 1)}
    for tid in mvps:
        mvps[tid]['pts'] = round(mvps[tid]['pts'], 1)

    # ---------- draft ROI (auction) ----------
    draft = json.load(open(f'{DATA}/draft_{SEASON}.json'))['picks']
    rostered_pts = defaultdict(float)  # pid -> pts while on any roster (all weeks)
    for r in rows:
        rostered_pts[r['pid']] += r['pts']
    picks = []
    for pk in draft:
        pid = pk['pid']
        picks.append({
            'pid': pid, 'teamId': pk['tid'], 'bid': pk['bid'],
            'name': pname.get(pid, f'#{pid}'), 'pos': ppos.get(pid, '?'),
            'pts': round(rostered_pts.get(pid, 0), 1),
        })
    for p in picks:
        p['ppd'] = round(p['pts'] / max(1, p['bid']), 2)
    known = [p for p in picks if not p['name'].startswith('#')]
    steals = sorted([p for p in known if p['bid'] >= 1], key=lambda x: -x['ppd'])[:8]
    busts = sorted([p for p in known if p['bid'] >= 20], key=lambda x: x['ppd'])[:8]
    spend = defaultdict(lambda: [0, 0.0])
    for p in picks:
        spend[p['teamId']][0] += p['bid']
        spend[p['teamId']][1] += p['pts']
    draft_eff = [{'teamId': t, 'spent': s[0], 'pts': round(s[1], 1),
                  'ppd': round(s[1] / max(1, s[0]), 2)} for t, s in spend.items()]
    draft_eff.sort(key=lambda x: -x['ppd'])

    # ---------- nflverse join ----------
    espn_to_gsis = {}
    with open(f'{DATA}/roster_{SEASON}.csv') as f:
        for row in csv.DictReader(f):
            if row.get('espn_id') and row.get('gsis_id'):
                espn_to_gsis[row['espn_id']] = row['gsis_id']

    nfl = defaultdict(dict)  # gsis -> week -> stats row
    with open(f'{DATA}/stats_player_week_{SEASON}.csv') as f:
        for row in csv.DictReader(f):
            if row['season_type'] != 'REG':
                continue
            try:
                wk = int(row['week'])
            except ValueError:
                continue
            nfl[row['player_id']][wk] = row

    def fnum(row, key):
        v = row.get(key, '')
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    # per-franchise: EPA generated by started players, air yards, wopr (reg season)
    adv = {tid: {'epa': 0.0, 'air': 0.0, 'wopr': 0.0, 'woprN': 0, 'matched': 0, 'starts': 0}
           for tid in teams25}
    player_adv = defaultdict(lambda: {'epa': 0.0, 'wopr': 0.0, 'woprN': 0, 'air': 0.0, 'tsh': 0.0, 'tshN': 0})
    for r in rows:
        if not r['started'] or r['week'] > REG_WEEKS or r['teamId'] not in adv:
            continue
        a = adv[r['teamId']]
        if r['pos'] in ('DST',):
            continue
        a['starts'] += 1
        gsis = espn_to_gsis.get(str(r['pid']))
        st = nfl.get(gsis, {}).get(r['week']) if gsis else None
        if not st:
            continue
        a['matched'] += 1
        epa = fnum(st, 'passing_epa') + fnum(st, 'rushing_epa') + fnum(st, 'receiving_epa')
        a['epa'] += epa
        a['air'] += fnum(st, 'receiving_air_yards')
        w = fnum(st, 'wopr')
        if w:
            a['wopr'] += w
            a['woprN'] += 1
        pa = player_adv[r['pid']]
        pa['epa'] += epa
        pa['air'] += fnum(st, 'receiving_air_yards')
        if w:
            pa['wopr'] += w
            pa['woprN'] += 1
        t = fnum(st, 'target_share')
        if t:
            pa['tsh'] += t
            pa['tshN'] += 1

    franchise_adv = []
    for tid, a in adv.items():
        franchise_adv.append({
            'teamId': tid,
            'epa': round(a['epa'], 1),
            'air': int(a['air']),
            'wopr': round(a['wopr'] / a['woprN'], 3) if a['woprN'] else 0,
            'matchRate': round(a['matched'] / max(1, a['starts']), 3),
        })
    franchise_adv.sort(key=lambda x: -x['epa'])

    # spotlight: top 12 players by started points w/ NFL context
    tot_started = defaultdict(float)
    starter_team = defaultdict(lambda: defaultdict(float))
    for (tid, pid), pts in started_pts.items():
        tot_started[pid] += pts
        starter_team[pid][tid] += pts
    spotlight = []
    for pid, pts in sorted(tot_started.items(), key=lambda x: -x[1]):
        if ppos.get(pid) in ('DST', 'K'):
            continue
        main_team = max(starter_team[pid], key=starter_team[pid].get)
        pa = player_adv.get(pid, {})
        wks = max(1, sum(1 for r in rows if r['pid'] == pid and r['started']))
        spotlight.append({
            'name': pname[pid], 'pos': ppos.get(pid, '?'), 'teamId': main_team,
            'pts': round(pts, 1), 'ppg': round(pts / wks, 1),
            'epa': round(pa.get('epa', 0), 1),
            'wopr': round(pa['wopr'] / pa['woprN'], 2) if pa.get('woprN') else None,
            'tsh': round(pa['tsh'] / pa['tshN'], 3) if pa.get('tshN') else None,
        })
        if len(spotlight) >= 12:
            break

    # ================= PLAYER PROFILER + FANTASY GENIUS =================

    # roster meta: espn_id -> NFL team & headshot
    nfl_meta = {}
    with open(f'{DATA}/roster_{SEASON}.csv') as f:
        for row in csv.DictReader(f):
            if row.get('espn_id'):
                hs = row.get('headshot_url', '')
                if hs:
                    hs = hs.replace('f_auto,q_auto', 'c_fill,g_face,h_200,w_200,f_auto,q_auto')
                nfl_meta[row['espn_id']] = {
                    'nfl': row.get('team', ''),
                    'hs': hs,
                }

    drafted_by = {p['pid']: {'teamId': p['teamId'], 'bid': p['bid']} for p in picks}

    # weekly log per player: week -> (pts, started, teamId, slot)
    SLOT_LABEL = {0: 'QB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE', 6: 'TE', 7: 'OP',
                  16: 'D/ST', 17: 'K', 20: 'BN', 21: 'IR', 23: 'FLEX'}
    plog = defaultdict(dict)
    for r in rows:
        plog[r['pid']][r['week']] = (r['pts'], r['started'], r['teamId'], SLOT_LABEL.get(r['slot'], '?'))

    players_out = []
    for pid, log in plog.items():
        tot = round(sum(v[0] for v in log.values()), 1)
        st_weeks = [v for v in log.values() if v[1]]
        if tot < 10 and not st_weeks:
            continue
        st_pts = round(sum(v[0] for v in st_weeks), 1)
        n_st = len(st_weeks)
        ppg = round(st_pts / n_st, 1) if n_st else 0
        scores = [v[0] for v in st_weeks]
        boom = bust = 0
        cons = None
        if len(scores) >= 3:
            mean = sum(scores) / len(scores)
            if mean > 0:
                boom = sum(1 for x in scores if x >= 1.5 * mean)
                bust = sum(1 for x in scores if x <= 0.5 * mean)
                var = sum((x - mean) ** 2 for x in scores) / len(scores)
                cons = round(1 - min(1, (var ** 0.5) / mean), 2)  # 1 = metronome
        meta = nfl_meta.get(str(pid), {})
        pa = player_adv.get(pid, {})
        dr = drafted_by.get(pid)
        gsis = espn_to_gsis.get(str(pid))
        wk_arr = []
        for w in sorted(log):
            pts_, st_, tid_, slot_ = log[w]
            st = nfl.get(gsis, {}).get(w) if gsis else None
            opp = st['opponent_team'] if st else ''
            yds = int(fnum(st, 'passing_yards') + fnum(st, 'rushing_yards') + fnum(st, 'receiving_yards')) if st else None
            td = int(fnum(st, 'passing_tds') + fnum(st, 'rushing_tds') + fnum(st, 'receiving_tds')) if st else None
            tgt = int(fnum(st, 'targets')) if st else None
            epa_w = round(fnum(st, 'passing_epa') + fnum(st, 'rushing_epa') + fnum(st, 'receiving_epa'), 1) if st else None
            wk_arr.append([w, pts_, 1 if st_ else 0, tid_, slot_, opp, yds, td, tgt, epa_w])
        st_by = defaultdict(float)
        for w, (pts_, st_, tid_, slot_) in log.items():
            if st_:
                st_by[tid_] += pts_
        players_out.append({
            'pid': pid, 'name': pname.get(pid, '?'), 'pos': ppos.get(pid, '?'),
            'nfl': meta.get('nfl', ''), 'hs': meta.get('hs', ''),
            'tot': tot, 'stPts': st_pts, 'starts': n_st, 'ppg': ppg,
            'boom': boom, 'bust': bust, 'cons': cons,
            'epa': round(pa.get('epa', 0), 1) if pa else None,
            'wopr': round(pa['wopr'] / pa['woprN'], 2) if pa and pa.get('woprN') else None,
            'tsh': round(pa['tsh'] / pa['tshN'], 3) if pa and pa.get('tshN') else None,
            'draft': dr, 'wk': wk_arr,
            'mainTeam': max(st_by, key=st_by.get) if st_by else wk_arr[-1][3],
        })
    players_out.sort(key=lambda x: -x['tot'])

    # ---- what-if standings: everyone starts a perfect lineup ----
    wk_opt = {}   # (tid, wk) -> optimal
    wk_act = {}
    for (wk, tid), entries in week_team.items():
        if wk <= REG_WEEKS:
            wk_opt[(tid, wk)] = optimal_points(entries)
            wk_act[(tid, wk)] = round(sum(e['pts'] for e in entries if e['started']), 2)
    league_raw = json.load(open(f'{DATA}/league_{SEASON}.json'))
    if isinstance(league_raw, list):
        league_raw = league_raw[0]
    whatif = {tid: {'w': 0, 'l': 0} for tid in teams25}
    actualrec = {tid: {'w': 0, 'l': 0} for tid in teams25}
    for g in league_raw.get('schedule', []):
        wk = g['matchupPeriodId']
        if wk > REG_WEEKS or not g.get('home') or not g.get('away'):
            continue
        h, a = g['home']['teamId'], g['away']['teamId']
        if (h, wk) not in wk_opt or (a, wk) not in wk_opt:
            continue
        ho, ao = wk_opt[(h, wk)], wk_opt[(a, wk)]
        if ho != ao:
            whatif[ho > ao and h or a]['w'] += 1
            whatif[ho > ao and a or h]['l'] += 1
        ha, aa = g['home']['totalPoints'], g['away']['totalPoints']
        if ha != aa:
            actualrec[ha > aa and h or a]['w'] += 1
            actualrec[ha > aa and a or h]['l'] += 1
    whatif_rows = []
    act_sorted = sorted(teams25, key=lambda t: (-actualrec[t]['w'], -teams25[t]['pf']))
    wif_sorted = sorted(teams25, key=lambda t: (-whatif[t]['w'], -iq[t]['optimal']))
    for tid in teams25:
        whatif_rows.append({
            'teamId': tid,
            'actW': actualrec[tid]['w'], 'actL': actualrec[tid]['l'],
            'optW': whatif[tid]['w'], 'optL': whatif[tid]['l'],
            'actRank': act_sorted.index(tid) + 1, 'optRank': wif_sorted.index(tid) + 1,
        })
    whatif_rows.sort(key=lambda x: x['optRank'])

    # ---- waiver wizard: undrafted players, started points ----
    waiver_by_team = defaultdict(float)
    waiver_players = []
    for p in players_out:
        if p['draft'] is None and p['stPts'] > 0:
            waiver_players.append(p)
    for pid, log in plog.items():
        if pid in drafted_by:
            continue
        for w, (pts_, st_, tid_, slot_) in log.items():
            if st_ and w <= REG_WEEKS:
                waiver_by_team[tid_] += pts_
    waiver_top = sorted(waiver_players, key=lambda x: -x['stPts'])[:8]
    waiver_top = [{'name': p['name'], 'pos': p['pos'], 'stPts': p['stPts'],
                   'teamId': p['mainTeam'], 'nfl': p['nfl']} for p in waiver_top]

    # ---- manager report card ----
    def ranks(pairs, reverse=True):
        """pairs: (tid, value) -> tid -> rank 1..n"""
        srt = sorted(pairs, key=lambda x: -x[1] if reverse else x[1])
        return {tid: i + 1 for i, (tid, v) in enumerate(srt)}

    n = len(teams25)
    draft_rank = ranks([(d['teamId'], d['ppd']) for d in draft_eff])
    iq_by_tid = {x['teamId']: x for x in lineup_iq}
    lineup_rank = ranks([(tid, iq_by_tid[tid]['eff']) for tid in teams25])
    waiver_rank = ranks([(tid, waiver_by_team.get(tid, 0)) for tid in teams25])
    luck_by_tid = {t['id']: t['luck'] for t in site['seasons']['2025']['teams']}
    luck_rank = ranks([(tid, luck_by_tid.get(tid, 0)) for tid in teams25])

    def grade(rank):
        pct = (rank - 1) / (n - 1)
        for cut, g in ((0.09, 'A+'), (0.2, 'A'), (0.32, 'B+'), (0.45, 'B'),
                       (0.6, 'C+'), (0.75, 'C'), (0.88, 'D'), (2, 'F')):
            if pct <= cut:
                return g
    GPA = {'A+': 4.3, 'A': 4.0, 'B+': 3.3, 'B': 3.0, 'C+': 2.3, 'C': 2.0, 'D': 1.0, 'F': 0.0}

    verdicts = []
    report = []
    for tid in teams25:
        g_draft, g_line, g_waiv = grade(draft_rank[tid]), grade(lineup_rank[tid]), grade(waiver_rank[tid])
        g_luck = grade(luck_rank[tid])
        gpa = round((GPA[g_draft] + GPA[g_line] + GPA[g_waiv]) / 3, 2)
        skill = {'draft': draft_rank[tid], 'lineup': lineup_rank[tid], 'waiver': waiver_rank[tid]}
        best = min(skill, key=skill.get)
        worst = max(skill, key=skill.get)
        BLURB_GOOD = {'draft': 'drafted like a genius', 'lineup': 'set lineups like a surgeon', 'waiver': 'owned the waiver wire'}
        BLURB_BAD = {'draft': 'lit auction money on fire', 'lineup': 'benched the wrong guys', 'waiver': 'ignored free agents'}
        verdict = f"{BLURB_GOOD[best].capitalize()}, but {BLURB_BAD[worst]}." if skill[best] <= 4 and skill[worst] >= 8 \
            else ('Complete performance across the board.' if gpa >= 3.5
                  else 'Solid fundamentals, no fatal flaw.' if gpa >= 2.5
                  else 'A rebuilding year on every front.')
        report.append({
            'teamId': tid, 'gDraft': g_draft, 'gLineup': g_line, 'gWaiver': g_waiv,
            'gLuck': g_luck, 'gpa': gpa, 'verdict': verdict,
            'waiverPts': round(waiver_by_team.get(tid, 0), 1),
        })
    report.sort(key=lambda x: -x['gpa'])

    site['nextgen'] = {
        'year': 2025,
        'lineupIQ': lineup_iq,
        'posDNA': pos_dna,
        'mvps': {str(k): v for k, v in mvps.items()},
        'draft': {'steals': steals, 'busts': busts, 'teamEff': draft_eff},
        'franchiseAdv': franchise_adv,
        'spotlight': spotlight,
        'players': players_out,
        'whatif': whatif_rows,
        'waiver': waiver_top,
        'report': report,
    }
    json.dump(site, open(SITE, 'w'))
    print('lineup IQ:', [(teams25[x["teamId"]]["abbrev"] or x["teamId"], x['eff'], x['wasted']) for x in lineup_iq[:3]], '...')
    print('match rate:', [(x['teamId'], x['matchRate']) for x in franchise_adv])
    print('top steal:', steals[0] if steals else None)
    print('top bust:', busts[0] if busts else None)
    print('spotlight[0]:', spotlight[0] if spotlight else None)
    print('size:', round(os.path.getsize(SITE) / 1024, 1), 'KB')

if __name__ == '__main__':
    main()
