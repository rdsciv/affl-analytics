#!/usr/bin/env python3
"""Process raw ESPN fantasy JSON into site/data.json for the AFFL dashboard."""
import json
import glob
import os
import re
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
OUT = os.path.join(os.path.dirname(__file__), 'site', 'data.json')

def load_season(path):
    raw = json.load(open(path))
    if isinstance(raw, list):
        raw = raw[0]
    return raw

LOGO_MAP = {}
_lm_path = os.path.join(DATA_DIR, 'logo_map.json')
if os.path.exists(_lm_path):
    LOGO_MAP = json.load(open(_lm_path))

def local_logo(url):
    """Map ESPN/remote logo URLs to site/logos/*; never emit off-site URLs."""
    if not url:
        return ''
    mapped = LOGO_MAP.get(url)
    if mapped:
        return mapped
    s = str(url)
    if s.startswith('logos/'):
        return s
    # Unmapped http(s) or other remotes → empty (monogram). CHI-169.
    return ''

def team_name(t):
    n = t.get('name')
    if n:
        return re.sub(r'\s+', ' ', n).strip()
    return re.sub(r'\s+', ' ', (t.get('location', '') + ' ' + t.get('nickname', ''))).strip()

def main():
    seasons = {}
    members_all = {}

    for path in sorted(glob.glob(os.path.join(DATA_DIR, 'league_*.json'))):
        d = load_season(path)
        year = d['seasonId']
        status = d.get('status', {})
        final_mp = status.get('finalScoringPeriod') or 17

        for m in d.get('members', []):
            nm = (m.get('firstName', '') + ' ' + m.get('lastName', '')).strip()
            members_all[m['id']] = re.sub(r'\s+', ' ', nm)

        teams = {}
        for t in d.get('teams', []):
            rec = t.get('record', {}).get('overall', {})
            owners = t.get('owners', [])
            teams[t['id']] = {
                'id': t['id'],
                'abbrev': t.get('abbrev', ''),
                'name': team_name(t),
                'owner': owners[0] if owners else None,
                'owners': owners,
                'logo': local_logo(t.get('logo', '')),
                'wins': rec.get('wins', 0),
                'losses': rec.get('losses', 0),
                'ties': rec.get('ties', 0),
                'pf': round(rec.get('pointsFor', 0), 2),
                'pa': round(rec.get('pointsAgainst', 0), 2),
                'playoffSeed': t.get('playoffSeed'),
                'finalRank': t.get('rankCalculatedFinal') or t.get('rankFinal'),
            }

        # weekly matchups (regular season = matchupPeriod <= reg season count)
        settings = d.get('settings', {})
        sched_settings = settings.get('scheduleSettings', {})
        reg_weeks = sched_settings.get('matchupPeriodCount', 13)
        playoff_teams = sched_settings.get('playoffTeamCount', 6)

        matchups = []
        for g in d.get('schedule', []):
            home, away = g.get('home'), g.get('away')
            if not home or not away:
                continue  # bye
            hp, ap = home.get('totalPoints', 0), away.get('totalPoints', 0)
            if hp == 0 and ap == 0:
                continue  # unplayed
            matchups.append({
                'week': g['matchupPeriodId'],
                'homeId': home['teamId'], 'awayId': away['teamId'],
                'homePts': round(hp, 2), 'awayPts': round(ap, 2),
                'playoff': g.get('playoffTierType', 'NONE') != 'NONE' or g['matchupPeriodId'] > reg_weeks,
                'tier': g.get('playoffTierType', 'NONE'),
            })

        seasons[year] = {
            'year': year,
            'name': settings.get('name', ''),
            'regWeeks': reg_weeks,
            'playoffTeams': playoff_teams,
            'teams': teams,
            'matchups': matchups,
        }

    # ---- per-season analytics ----
    out_seasons = {}
    for year, s in sorted(seasons.items()):
        teams = s['teams']
        # weekly scores per team (regular season only for all-play/luck)
        weekly = defaultdict(dict)   # teamId -> week -> pts
        for m in s['matchups']:
            weekly[m['homeId']][m['week']] = m['homePts']
            weekly[m['awayId']][m['week']] = m['awayPts']

        reg_weeks_played = sorted({m['week'] for m in s['matchups'] if not m['playoff']})

        # all-play record: each week, rank every team's score against the field
        allplay = {tid: [0, 0] for tid in teams}
        for wk in reg_weeks_played:
            scores = [(tid, weekly[tid].get(wk)) for tid in teams if weekly[tid].get(wk) is not None]
            for tid, pts in scores:
                for tid2, pts2 in scores:
                    if tid == tid2:
                        continue
                    if pts > pts2:
                        allplay[tid][0] += 1
                    elif pts < pts2:
                        allplay[tid][1] += 1

        # cumulative wins per week (regular season)
        cumwins = {tid: [] for tid in teams}
        wins_running = {tid: 0 for tid in teams}
        for wk in reg_weeks_played:
            for m in s['matchups']:
                if m['week'] != wk or m['playoff']:
                    continue
                if m['homePts'] > m['awayPts']:
                    wins_running[m['homeId']] += 1
                elif m['awayPts'] > m['homePts']:
                    wins_running[m['awayId']] += 1
            for tid in teams:
                cumwins[tid].append(wins_running[tid])

        # superlatives
        best_week = {'pts': -1}
        worst_week = {'pts': 1e9}
        closest = {'margin': 1e9}
        blowout = {'margin': -1}
        for m in s['matchups']:
            for side, opp in (('home', 'away'), ('away', 'home')):
                pts = m[side + 'Pts']
                tid = m[side + 'Id']
                if pts > best_week['pts']:
                    best_week = {'pts': pts, 'teamId': tid, 'week': m['week']}
                if pts < worst_week['pts'] and pts > 0:
                    worst_week = {'pts': pts, 'teamId': tid, 'week': m['week']}
            margin = abs(m['homePts'] - m['awayPts'])
            winner = m['homeId'] if m['homePts'] > m['awayPts'] else m['awayId']
            loser = m['awayId'] if winner == m['homeId'] else m['homeId']
            if margin < closest['margin'] and margin > 0:
                closest = {'margin': round(margin, 2), 'winnerId': winner, 'loserId': loser, 'week': m['week']}
            if margin > blowout['margin']:
                blowout = {'margin': round(margin, 2), 'winnerId': winner, 'loserId': loser, 'week': m['week']}

        champion = next((t for t in teams.values() if t['finalRank'] == 1), None)
        runner_up = next((t for t in teams.values() if t['finalRank'] == 2), None)

        n_reg = len(reg_weeks_played) if reg_weeks_played else 1
        team_rows = []
        for tid, t in teams.items():
            ap_w, ap_l = allplay[tid]
            games = t['wins'] + t['losses'] + t['ties']
            exp_wins = round(ap_w / max(1, ap_w + ap_l) * (len(reg_weeks_played)), 2)
            reg_wins = cumwins[tid][-1] if cumwins[tid] else t['wins']
            row = dict(t)
            row['allplayW'] = ap_w
            row['allplayL'] = ap_l
            row['expWins'] = exp_wins
            row['regWins'] = reg_wins
            row['luck'] = round(reg_wins - exp_wins, 2)
            row['avgPts'] = round(sum(weekly[tid].get(w, 0) for w in reg_weeks_played) / n_reg, 2) if reg_weeks_played else 0
            row['weekly'] = [weekly[tid].get(w) for w in reg_weeks_played]
            row['cumWins'] = cumwins[tid]
            team_rows.append(row)

        # league weekly avg / max / min
        wk_avg, wk_max, wk_min = [], [], []
        for wk in reg_weeks_played:
            pts = [weekly[tid][wk] for tid in teams if weekly[tid].get(wk) is not None]
            if pts:
                wk_avg.append(round(sum(pts) / len(pts), 2))
                wk_max.append(max(pts))
                wk_min.append(min(pts))

        out_seasons[year] = {
            'year': year,
            'regWeeks': reg_weeks_played,
            'playoffTeams': s['playoffTeams'],
            'teams': team_rows,
            'champion': champion['id'] if champion else None,
            'runnerUp': runner_up['id'] if runner_up else None,
            'bestWeek': best_week, 'worstWeek': worst_week,
            'closest': closest, 'blowout': blowout,
            'totalPts': round(sum(t['pf'] for t in teams.values()), 1),
            'wkAvg': wk_avg, 'wkMax': wk_max, 'wkMin': wk_min,
        }

    # ---- franchise (owner) aggregates across seasons ----
    fr = {}
    for year, s in seasons.items():
        for tid, t in s['teams'].items():
            o = t['owner']
            if not o:
                continue
            f = fr.setdefault(o, {
                'owner': o, 'ownerName': members_all.get(o, 'Unknown'),
                'seasons': 0, 'wins': 0, 'losses': 0, 'ties': 0,
                'pf': 0, 'pa': 0, 'titles': 0, 'runnerUps': 0, 'playoffs': 0,
                'lastSacko': None, 'names': {}, 'years': [], 'bestFinish': 99,
                'pfBySeason': {},
            })
            f['seasons'] += 1
            f['years'].append(year)
            f['wins'] += t['wins']; f['losses'] += t['losses']; f['ties'] += t['ties']
            f['pf'] += t['pf']; f['pa'] += t['pa']
            f['pfBySeason'][year] = t['pf']
            f['names'][t['name']] = f['names'].get(t['name'], 0) + 1
            rank = t['finalRank']
            if rank == 1:
                f['titles'] += 1
            if rank == 2:
                f['runnerUps'] += 1
            if rank and rank < f['bestFinish']:
                f['bestFinish'] = rank
            if t['playoffSeed'] and t['playoffSeed'] <= seasons[year]['playoffTeams']:
                f['playoffs'] += 1
            if rank == len(s['teams']):
                f['lastSacko'] = year

    franchises = []
    for o, f in fr.items():
        games = f['wins'] + f['losses'] + f['ties']
        f['winPct'] = round((f['wins'] + 0.5 * f['ties']) / max(1, games), 4)
        f['pf'] = round(f['pf'], 1); f['pa'] = round(f['pa'], 1)
        f['currentName'] = max(f['names'], key=f['names'].get)
        # prefer the most RECENT name: use 2025 name if active
        if o in [t['owner'] for t in seasons.get(2025, {'teams': {}})['teams'].values()]:
            for t in seasons[2025]['teams'].values():
                if t['owner'] == o:
                    f['currentName'] = t['name']
                    f['active'] = True
        del f['names']
        franchises.append(f)
    # merge franchises whose owner display-name matches (old duplicate ESPN accounts)
    by_name = {}
    merged = []
    for f in franchises:
        key = f['ownerName'].lower()
        if key in by_name:
            g = by_name[key]
            g_last = max(g['years'])
            g['seasons'] += f['seasons']
            g['years'] += f['years']
            g['wins'] += f['wins']; g['losses'] += f['losses']; g['ties'] += f['ties']
            g['pf'] = round(g['pf'] + f['pf'], 1); g['pa'] = round(g['pa'] + f['pa'], 1)
            g['titles'] += f['titles']; g['runnerUps'] += f['runnerUps']; g['playoffs'] += f['playoffs']
            g['bestFinish'] = min(g['bestFinish'], f['bestFinish'])
            g['pfBySeason'].update(f['pfBySeason'])
            games = g['wins'] + g['losses'] + g['ties']
            g['winPct'] = round((g['wins'] + 0.5 * g['ties']) / max(1, games), 4)
            if f.get('active'):
                g['active'] = True
            # keep the name from whichever account played most recently
            if max(f['years']) > max(y for y in g['years'] if y not in f['years']):
                g['currentName'] = f['currentName']
        else:
            by_name[key] = f
            merged.append(f)
    franchises = merged
    franchises.sort(key=lambda x: (-x['titles'], -x['winPct']))

    # ---- all-time head-to-head (owner vs owner, all games) ----
    h2h = defaultdict(lambda: [0, 0])  # (ownerA, ownerB) sorted key -> [winsA, winsB]
    active_owners = [f['owner'] for f in franchises if f.get('active')]
    for year, s in seasons.items():
        owner_of = {tid: t['owner'] for tid, t in s['teams'].items()}
        for m in s['matchups']:
            oh, oa = owner_of.get(m['homeId']), owner_of.get(m['awayId'])
            if not oh or not oa or oh == oa:
                continue
            if m['homePts'] == m['awayPts']:
                continue
            winner = oh if m['homePts'] > m['awayPts'] else oa
            key = (oh, oa) if oh < oa else (oa, oh)
            h2h[key][0 if winner == key[0] else 1] += 1

    h2h_out = [{'a': k[0], 'b': k[1], 'aW': v[0], 'bW': v[1]} for k, v in h2h.items()]

    # champions timeline
    timeline = []
    for year in sorted(seasons):
        os_ = out_seasons[year]
        champ = next((t for t in os_['teams'] if t['id'] == os_['champion']), None)
        if champ:
            timeline.append({
                'year': year, 'team': champ['name'], 'owner': members_all.get(champ['owner'], '?'),
                'record': f"{champ['wins']}-{champ['losses']}", 'pf': champ['pf'], 'logo': champ['logo'],
            })

    result = {
        'leagueName': 'AFFL',
        'members': members_all,
        'seasons': out_seasons,
        'franchises': franchises,
        'h2h': h2h_out,
        'activeOwners': active_owners,
        'timeline': timeline,
        'latest': max(seasons),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Scrub ESPN member GUIDs (SWIDs) before writing — they are persistent
    # account identifiers and half of the auth cookie pair. Replace with stable
    # opaque ids so the published site never carries them.
    guid_re = re.compile(r'^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$')
    alias = {g: 'm%02d' % i for i, g in enumerate(sorted(members_all), 1)}

    def scrub(o):
        if isinstance(o, dict):
            return {alias.get(k, k): scrub(v) for k, v in o.items()}
        if isinstance(o, list):
            return [scrub(v) for v in o]
        if isinstance(o, str) and guid_re.match(o):
            return alias.get(o, 'm??')
        return o

    result = scrub(result)
    json.dump(result, open(OUT, 'w'))
    print('wrote', OUT, round(os.path.getsize(OUT) / 1024, 1), 'KB')
    print('seasons:', sorted(out_seasons))
    print('franchises:', [(f['ownerName'], f['titles'], f['winPct']) for f in franchises])

if __name__ == '__main__':
    main()
