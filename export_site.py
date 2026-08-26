#!/usr/bin/env python3
"""Export the site's metric payloads from affl.db.

process_seasons.py still assembles the structural payload (weekly rosters,
player meta, transaction log, trades). This owns the *metrics*, computed once in
SQL so there is a single definition of each. It patches the per-season bundles
in place, replacing any key it is responsible for.

Owns:
  draftValue   steals / busts / per-team efficiency, all on points above
               replacement per dollar (v_draft_value)
  power        all-play record and PWR% (v_power); rank is raw ratio
  luckFG       Luck Index: FantasyGenius lucky / unlucky (v_luck)
  luckWeighted League Legacy expected-wins luck (v_luck_weighted). Not luckFG.
  nflCap       NFL salary-cap total carried by each AFFL roster (v_team_nfl_cap)
  baselines    the replacement level used, so the UI can explain the number
  custody      weekly points + Custody PAR by acquisition; Trade Alpha stays null
  receivingUsage 2018+ WOPR / aDOT / RACR / xFP from fact_nfl_week + xTD
  trophies     H2H / median / all-play / roto champions (team-season)
  luckCard     actual vs all-play vs median + schedule luck
  auctionDna   top-6 spend vs Cates curve (auction years only)
  awards       All-League / Bush League weekly position awards (2018+)
  w1Acquired   week-1 roster points vs later acquisitions (2018+)
"""
import json
import os
import sqlite3

import compute_eight

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
YEARS = os.path.join(HERE, 'site', 'years')

def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]


ROTO_CATS = (
    ('py', 'Pass Yds', 'Passing', 'py', 'py_rank', 'py_pts'),
    ('ptd', 'Pass TD', 'Passing', 'ptd', 'ptd_rank', 'ptd_pts'),
    ('compPct', 'Comp%', 'Passing', 'comp_pct', 'comp_pct_rank', 'comp_pct_pts'),
    ('ry', 'Rush Yds', 'Rushing', 'ry', 'ry_rank', 'ry_pts'),
    ('rtd', 'Rush TD', 'Rushing', 'rtd', 'rtd_rank', 'rtd_pts'),
    ('ypc', 'YPC', 'Rushing', 'ypc', 'ypc_rank', 'ypc_pts'),
    ('recy', 'Rec Yds', 'Receiving', 'recy', 'recy_rank', 'recy_pts'),
    ('retd', 'Rec TD', 'Receiving', 'retd', 'retd_rank', 'retd_pts'),
    ('rec', 'Rec', 'Receiving', 'rec', 'rec_rank', 'rec_pts'),
    ('ypr', 'YPR', 'Receiving', 'ypr', 'ypr_rank', 'ypr_pts'),
)
ROTO_PHASE_OUT = {'regular': 'reg', 'championship': 'championship', 'combined': 'combined'}


def export_roto(con, year):
    """None before 2018 (no weekly lineups)."""
    if year < 2018:
        return None
    out = {}
    for db_phase, key in ROTO_PHASE_OUT.items():
        recs = rows(con, """
            SELECT * FROM v_roto_standings
             WHERE season = ? AND phase = ?
             ORDER BY total_rank""", (year, db_phase))
        teams = []
        for r in recs:
            cats = [{'key': k, 'label': lab, 'group': grp,
                     'value': r[col], 'rank': r[rk], 'pts': r[pt]}
                    for k, lab, grp, col, rk, pt in ROTO_CATS]
            teams.append({'teamId': r['team_id'], 'games': r['games'],
                          'totalPts': r['total_pts'], 'totalRank': r['total_rank'],
                          'cats': cats})
        out[key] = {'teams': teams}
    return out


def write_roto_career(con):
    import compute_roto
    payload = {}
    for db_phase, key in ROTO_PHASE_OUT.items():
        c = compute_roto.career_rows(con, db_phase)
        payload[key] = {
            'scoredYears': c['scoredYears'],
            'missingYears': c['missingYears'],
            'evidence': c['evidence'],
            'rows': [{
                'ownerId': r['ownerId'], 'manager': r['manager'],
                'seasons': r['seasons'], 'avgRank': r['avgRank'],
                'bestRank': r['bestRank'], 'worstRank': r['worstRank'],
                'avgPts': r['avgPts'],
                'byYear': {str(y): v for y, v in r['byYear'].items()},
            } for r in c['rows']],
        }
    path = os.path.join(HERE, 'site', 'roto_career.json')
    json.dump(payload, open(path, 'w'))
    print(f"  career: {len(payload['reg']['rows'])} managers -> site/roto_career.json")


def export_custody(con, year):
    """Weekly custody 2018+. None before (no lineups / tx feed)."""
    if year < 2018:
        return None
    held = rows(con, """
        SELECT team_id AS tid, acquisition,
               ROUND(SUM(points),1) AS pts, ROUND(SUM(par),1) AS par,
               COUNT(*) AS weeks, SUM(started) AS started
          FROM fact_player_week_par
         WHERE season = ?
         GROUP BY team_id, acquisition""", (year,))
    if not held:
        return None
    spend = {r["tid"]: r for r in rows(con, """
        SELECT d.team_id AS tid,
               SUM(d.bid) AS draftSpendTraded,
               COUNT(DISTINCT d.player_id) AS nDraftedTraded
          FROM fact_draft_pick d
          JOIN fact_trade_item ti
            ON ti.player_id = d.player_id AND ti.from_team_id = d.team_id
          JOIN fact_trade tr
            ON tr.trade_id = ti.trade_id AND tr.season = d.season
         WHERE d.season = ?
         GROUP BY d.team_id""", (year,))}
    away = {r["tid"]: r["pts"] for r in rows(con, """
        SELECT ti.from_team_id AS tid, ROUND(SUM(r.points),1) AS pts
          FROM fact_trade_item ti
          JOIN fact_trade tr ON tr.trade_id = ti.trade_id
          JOIN fact_player_week_par r
            ON r.season = tr.season AND r.player_id = ti.player_id
           AND r.week > tr.week AND r.team_id != ti.from_team_id
         WHERE tr.season = ?
         GROUP BY ti.from_team_id""", (year,))}
    dropped = {r["tid"]: r["pts"] for r in rows(con, """
        WITH first_drop AS (
          SELECT team_id, player_id, MIN(week) AS week
            FROM fact_transaction
           WHERE season = ? AND direction = 'DROP' AND week IS NOT NULL
           GROUP BY team_id, player_id)
        SELECT d.team_id AS tid, ROUND(SUM(r.points),1) AS pts
          FROM first_drop d
          JOIN fact_player_week_par r
            ON r.season = ? AND r.player_id = d.player_id
           AND r.week > d.week AND r.team_id != d.team_id
         GROUP BY d.team_id""", (year, year))}
    by = {}
    for r in held:
        t = by.setdefault(r["tid"], {
            "tid": r["tid"],
            "ptsDrafted": 0, "ptsTradedIn": 0, "ptsWaived": 0, "ptsUnknown": 0,
            "parDrafted": 0, "parTradedIn": 0, "parWaived": 0, "parUnknown": 0,
            "parWaiver": 0, "parFa": 0, "parTotal": 0,
            "weeksDrafted": 0, "weeksTradedIn": 0, "weeksWaived": 0,
            "draftSpendTraded": 0, "nDraftedTraded": 0,
            "ptsTradedAway": 0, "ptsDroppedAway": 0,
            "ptsWaiver": 0, "ptsFa": 0,
        })
        acq = r["acquisition"]
        pts, par, wks = r["pts"] or 0, r["par"] or 0, r["weeks"]
        if acq == "Drafted":
            t["ptsDrafted"] = pts
            t["parDrafted"] = par
            t["weeksDrafted"] = wks
        elif acq == "Traded in":
            t["ptsTradedIn"] = pts
            t["parTradedIn"] = par
            t["weeksTradedIn"] = wks
        elif acq == "Waiver":
            t["ptsWaiver"] = pts
            t["ptsWaived"] += pts
            t["parWaiver"] = par
            t["parWaived"] += par
            t["weeksWaived"] += wks
        elif acq == "FA":
            t["ptsFa"] = pts
            t["ptsWaived"] += pts
            t["parFa"] = par
            t["parWaived"] += par
            t["weeksWaived"] += wks
        elif acq == "Waived":
            t["ptsWaived"] += pts
            t["parWaived"] += par
            t["weeksWaived"] += wks
        else:
            t["ptsUnknown"] += pts
            t["parUnknown"] += par
    for tid, t in by.items():
        sp = spend.get(tid) or {}
        t["draftSpendTraded"] = int(sp.get("draftSpendTraded") or 0)
        t["nDraftedTraded"] = int(sp.get("nDraftedTraded") or 0)
        t["ptsTradedAway"] = away.get(tid) or 0
        t["ptsDroppedAway"] = dropped.get(tid) or 0
        t["ptsWaiver"] = round(t["ptsWaiver"], 1)
        t["ptsFa"] = round(t["ptsFa"], 1)
        t["ptsWaived"] = round(t["ptsWaived"], 1)
        t["parWaiver"] = round(t["parWaiver"], 1)
        t["parFa"] = round(t["parFa"], 1)
        t["parWaived"] = round(t["parWaived"], 1)
        t["parUnknown"] = round(t["parUnknown"], 1)
        t["ptsUnknown"] = round(t["ptsUnknown"], 1)
        # Trade Alpha is a separate number and is never added here.
        t["parTotal"] = round(
            t["parDrafted"] + t["parTradedIn"] + t["parWaiver"] + t["parFa"] + t["parUnknown"], 1)
        t["ptsKept"] = round(t["ptsDrafted"] + t["ptsTradedIn"] + t["ptsWaived"], 1)
    return {"grain": "weekly", "tradeAlpha": None, "teams": list(by.values())}


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
               ROUND(power_pct*100,1) AS pwrPct, power_rank AS rank
          FROM v_power WHERE season = ?
         ORDER BY power_ratio DESC, allplay_w DESC, allplay_l ASC""", (year,))

    luck = rows(con, """
        SELECT team_id AS teamId, lucky_wins AS lucky,
               unlucky_losses AS unlucky, net_luck AS net
          FROM v_luck WHERE season = ? ORDER BY net_luck DESC""", (year,))

    luck_w = rows(con, """
        SELECT team_id AS teamId, reg_wins AS regWins, exp_wins AS expWins,
               weighted_luck AS weighted
          FROM v_luck_weighted WHERE season = ? ORDER BY weighted_luck DESC""", (year,))

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
    bundle['luckWeighted'] = luck_w
    bundle['notables'] = rows(con, """
        SELECT kind, week, winner_id AS winnerId, loser_id AS loserId,
               ROUND(winner_pts,1) AS winnerPts, ROUND(loser_pts,1) AS loserPts,
               ROUND(combined,1) AS combined, ROUND(margin,1) AS margin
          FROM v_notable_matchup WHERE season = ? ORDER BY kind""", (year,))
    bundle['scoreWeek'] = rows(con, """
        SELECT week, n, ROUND(min_pts,1) AS minPts, ROUND(avg_pts,1) AS avgPts,
               ROUND(max_pts,1) AS maxPts
          FROM v_score_week WHERE season = ? ORDER BY week""", (year,))
    sides = [r['points'] for r in rows(con, """
        SELECT points FROM fact_matchup
         WHERE season = ? AND is_playoff = 0
         ORDER BY points""", (year,))]
    if sides:
        n = len(sides)
        mid = n // 2
        med = sides[mid] if n % 2 else (sides[mid - 1] + sides[mid]) / 2
        bundle['scoreSeason'] = {
            'n': n,
            'minPts': round(sides[0], 1),
            'medianPts': round(med, 1),
            'maxPts': round(sides[-1], 1),
        }
    else:
        bundle['scoreSeason'] = None
    bundle['nflCap'] = {'byTeam': cap, 'final': capFinal, 'topPlayers': capTop}
    bundle['roto'] = export_roto(con, year)
    bundle['custody'] = export_custody(con, year)
    compute_eight.patch_year(con, bundle, year)
    json.dump(bundle, open(path, 'w'))
    return {'year': year, 'steals': len(steals), 'power': len(power),
            'cap_teams': len(cap), 'baselines': len(baselines),
            'roto': 0 if bundle['roto'] is None else len(bundle['roto']['reg']['teams'])}

def main():
    con = sqlite3.connect(DB)
    years = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    for y in years:
        info = export_year(con, y)
        if info:
            print(f"  {info['year']}: {info['steals']} steals · {info['power']} power rows "
                  f"· {info['cap_teams']} teams w/ cap · {info['baselines']} baselines"
                  f" · {info.get('roto', 0)} roto")
    write_roto_career(con)
    compute_eight.write_player_bio(con)
    compute_eight.write_miles(con)
    print('site/years/*.json patched from affl.db')

if __name__ == '__main__':
    main()
