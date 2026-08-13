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
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_AFFL = os.path.join(HERE, 'affl.db')
DB_NFL = os.path.join(HERE, 'nfl.db')
YEARS = os.path.join(HERE, 'site', 'years')

def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]

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

def main():
    con = sqlite3.connect(DB_AFFL)
    # Attach NFL database for the warehouse views
    con.execute(f"ATTACH DATABASE '{DB_NFL}' AS nfl")
    years = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    for y in years:
        info = export_year(con, y)
        if info:
            print(f"  {info['year']}: {info['steals']} steals · {info['power']} power rows "
                  f"· {info['cap_teams']} teams w/ cap · {info['baselines']} baselines")
    print('site/years/*.json patched from affl.db + nfl.db')

if __name__ == '__main__':
    main()
