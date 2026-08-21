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
  skillRadar   started-player NFL pass/rush/rec efficiency + EPA (non-PPR)
  player PBP   CPOE / aDOT / success / xTD / TD luck patched onto players[]
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
YEARS = os.path.join(HERE, 'site', 'years')

def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]

def _rank(values, higher_is_better=True):
    """Competition rank (1 = best). Ties share a rank; next rank skips."""
    indexed = list(enumerate(values))
    indexed.sort(key=lambda iv: (iv[1] is None, -(iv[1] or 0) if higher_is_better else (iv[1] or 0)))
    ranks = [None] * len(values)
    i = 0
    while i < len(indexed):
        val = indexed[i][1]
        j = i
        while j < len(indexed) and indexed[j][1] == val:
            j += 1
        for k in range(i, j):
            ranks[indexed[k][0]] = None if val is None else i + 1
        i = j
    return ranks

def _round(v, nd=1):
    return None if v is None else round(float(v), nd)

def skill_radar_payload(con, year):
    raw = rows(con, """
        SELECT team_id, pass_yards, pass_tds, completions, attempts,
               rush_yards, rush_tds, carries, rec_yards, rec_tds, receptions,
               box_epa, pbp_epa, cpoe_sum, cpoe_n, success_n, success_d,
               xtd, pbp_td
          FROM v_skill_radar WHERE season = ?""", (year,))
    if not raw:
        return None
    teams = []
    for r in raw:
        att = r['attempts'] or 0
        carries = r['carries'] or 0
        rec = r['receptions'] or 0
        cpoe_n = r['cpoe_n'] or 0
        suc_d = r['success_d'] or 0
        teams.append({
            'teamId': r['team_id'],
            'passYds': _round(r['pass_yards'], 0),
            'passTd': _round(r['pass_tds'], 0),
            'compPct': _round(100.0 * (r['completions'] or 0) / att, 1) if att else None,
            'rushYds': _round(r['rush_yards'], 0),
            'rushTd': _round(r['rush_tds'], 0),
            'ypc': _round((r['rush_yards'] or 0) / carries, 2) if carries else None,
            'recYds': _round(r['rec_yards'], 0),
            'recTd': _round(r['rec_tds'], 0),
            'rec': _round(r['receptions'], 0),
            'ypr': _round((r['rec_yards'] or 0) / rec, 2) if rec else None,
            'epa': _round(r['pbp_epa'] or r['box_epa'], 1),
            'cpoe': _round((r['cpoe_sum'] or 0) / cpoe_n, 1) if cpoe_n else None,
            'success': _round((r['success_n'] or 0) / suc_d, 3) if suc_d else None,
            'xtd': _round(r['xtd'], 1),
            'tdLuck': _round((r['pbp_td'] or 0) - (r['xtd'] or 0), 1),
        })
    # league ranks — higher is better for every axis we publish
    axes = ('passYds', 'passTd', 'compPct', 'rushYds', 'rushTd', 'ypc',
            'recYds', 'recTd', 'rec', 'ypr', 'epa', 'cpoe', 'success')
    rank_keys = {
        'passYds': 'passYdsRk', 'passTd': 'passTdRk', 'compPct': 'compPctRk',
        'rushYds': 'rushYdsRk', 'rushTd': 'rushTdRk', 'ypc': 'ypcRk',
        'recYds': 'recYdsRk', 'recTd': 'recTdRk', 'rec': 'recRk',
        'ypr': 'yprRk', 'epa': 'epaRk', 'cpoe': 'cpoeRk', 'success': 'successRk',
    }
    for axis in axes:
        rks = _rank([t[axis] for t in teams])
        for t, rk in zip(teams, rks):
            t[rank_keys[axis]] = rk
    teams.sort(key=lambda t: (t['epaRk'] or 99, -(t['epa'] or 0)))
    return {
        'scoring': 'NON_PPR',
        'recIsVolume': True,
        'note': 'Receptions are a counting stat. AFFL awards 0 points per reception.',
        'teams': teams,
    }

def patch_player_pbp(con, bundle, year):
    """Attach Savant-class season rolls to rostered players via gsis_id."""
    gsis_rows = rows(con, """
        SELECT p.player_id AS pid, v.cpoe, v.adot, v.success_rate, v.xtd,
               v.td_luck, v.epa, v.targets, v.receptions
          FROM v_player_pbp_season v
          JOIN dim_player p ON p.gsis_id = v.gsis_id
         WHERE v.season = ?""", (year,))
    by_pid = {r['pid']: r for r in gsis_rows}
    n = 0
    for p in bundle.get('players') or []:
        row = by_pid.get(p.get('pid'))
        if not row:
            p.setdefault('cpoe', None)
            p.setdefault('adot', None)
            p.setdefault('success', None)
            p.setdefault('xtd', None)
            p.setdefault('tdLuck', None)
            continue
        p['cpoe'] = _round(row['cpoe'], 1)
        p['adot'] = _round(row['adot'], 1)
        p['success'] = _round(row['success_rate'], 3)
        p['xtd'] = _round(row['xtd'], 1)
        p['tdLuck'] = _round(row['td_luck'], 1)
        n += 1
    return n

def export_year(con, year):
    path = os.path.join(YEARS, f'{year}.json')
    if not os.path.exists(path):
        return None
    bundle = json.load(open(path))

    baselines = rows(con, """
        SELECT position, demand, ROUND(rank_based,1) AS rankBased,
               ROUND(best_undrafted,1) AS bestUndrafted,
               ROUND(baseline_points,1) AS baseline
          FROM v_baseline WHERE season = ? AND baseline_points > 0
         ORDER BY baseline_points DESC""", (year,))

    dv = rows(con, """
        SELECT dv.player_id AS pid, dv.name, dv.position AS pos, dv.team_id AS tid,
               dv.bid, dv.overall, dv.is_keeper AS keeper,
               ROUND(dv.total_points,1) AS pts, ROUND(dv.par,1) AS par,
               dv.par_per_dollar AS parPerDollar, dv.points_per_dollar AS ptsPerDollar,
               COALESCE(ps.is_computed, 0) AS computed
          FROM v_draft_value dv
          LEFT JOIN v_player_season_any ps
                 ON ps.season = ? AND ps.player_id = dv.player_id
         WHERE dv.season = ? AND dv.total_points IS NOT NULL""", (year, year))

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

    # If the season's points had to be computed from NFL stats (pre-2018, where
    # ESPN kept no lineups), say so rather than passing it off as ESPN's own.
    computed_season = bool(dv) and all(d['computed'] for d in dv)
    bundle['draftValue'] = {'steals': steals, 'busts': busts, 'teamEff': eff,
                            'auction': auction, 'baselines': baselines,
                            'parByOverall': par_by_overall,
                            'computed': computed_season}
    bundle['power'] = power
    bundle['luckFG'] = luck
    bundle['nflCap'] = {'byTeam': cap, 'final': capFinal, 'topPlayers': capTop}
    radar = skill_radar_payload(con, year)
    if radar:
        bundle['skillRadar'] = radar
    n_pbp = patch_player_pbp(con, bundle, year)
    json.dump(bundle, open(path, 'w'))
    return {'year': year, 'steals': len(steals), 'power': len(power),
            'cap_teams': len(cap), 'baselines': len(baselines),
            'radar': len((radar or {}).get('teams') or []),
            'pbp_players': n_pbp}

def main():
    con = sqlite3.connect(DB)
    years = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    for y in years:
        info = export_year(con, y)
        if info:
            print(f"  {info['year']}: {info['steals']} steals · {info['power']} power rows "
                  f"· {info['cap_teams']} teams w/ cap · {info['baselines']} baselines"
                  f" · {info['radar']} skill-radar · {info['pbp_players']} pbp players")
    print('site/years/*.json patched from affl.db')

if __name__ == '__main__':
    main()
