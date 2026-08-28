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
  lineupIQPre2018 start/sit for the 2014-2017 team-weeks whose bench is known
               (dated roster snapshot). Verified roster, computed optimal.
"""
import json
import os
import sqlite3

import compute_eight
from affl_xfp import SAVANT_FANTASY_NOTE
from process_seasons import load_player_pool, optimal_points

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'affl.db')
YEARS = os.path.join(HERE, 'site', 'years')
CHART_FIRST_YEAR = 2013
CHART_LAST_YEAR = 2025

def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]


# ── Savant-class payloads (CHI-113 / CHI-114), merged from verify/full-audit ──
# Season/week rollups joined via gsis_id. AFFL scoring is non-PPR throughout.

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
        'note': 'Receptions are a counting stat. AFFL awards 0 points per reception. '
                + SAVANT_FANTASY_NOTE,
        'teams': teams,
    }

def patch_player_pbp(con, bundle, year):
    """Attach PBP rolls and AFFL XFP / FPOE to rostered players via gsis_id."""
    gsis_rows = rows(con, """
        SELECT p.player_id AS pid, v.cpoe, v.adot, v.success_rate, v.xtd,
               v.td_luck, v.epa, v.targets, v.receptions
          FROM v_player_pbp_season v
          JOIN dim_player p ON p.gsis_id = v.gsis_id
         WHERE v.season = ?""", (year,))
    xfp_rows = rows(con, """
        SELECT player_id AS pid, games, fp, xfp, fpoe, fp_g, xfp_g,
               st_games, st_fp, st_xfp, st_fpoe, wopr, target_share,
               air_yards_share, rz_opp, gl_opp, xtd, td_luck, targets,
               carries, opp
          FROM fact_player_xfp WHERE season = ?""", (year,))
    by_pid = {r['pid']: r for r in gsis_rows}
    by_xfp = {r['pid']: r for r in xfp_rows}
    n = 0
    for p in bundle.get('players') or []:
        row = by_pid.get(p.get('pid'))
        xf = by_xfp.get(p.get('pid'))
        if not row and not xf:
            p.setdefault('cpoe', None)
            p.setdefault('adot', None)
            p.setdefault('success', None)
            p.setdefault('xtd', None)
            p.setdefault('tdLuck', None)
            continue
        if row:
            p['cpoe'] = _round(row['cpoe'], 1)
            p['adot'] = _round(row['adot'], 1)
            p['success'] = _round(row['success_rate'], 3)
            p['xtd'] = _round(row['xtd'], 1)
            p['tdLuck'] = _round(row['td_luck'], 1)
        if xf:
            p['fp'] = _round(xf['fp'], 1)
            p['xfp'] = _round(xf['xfp'], 1)
            p['fpoe'] = _round(xf['fpoe'], 1)
            p['fpG'] = _round(xf['fp_g'], 2)
            p['xfpG'] = _round(xf['xfp_g'], 2)
            p['stFp'] = _round(xf['st_fp'], 1)
            p['stXfp'] = _round(xf['st_xfp'], 1)
            p['stFpoe'] = _round(xf['st_fpoe'], 1)
            p['ayShare'] = _round(xf['air_yards_share'], 3)
            p['rzOpp'] = _round(xf['rz_opp'], 0)
            p['glOpp'] = _round(xf['gl_opp'], 0)
            p['opp'] = _round(xf['opp'], 0)
            if xf['wopr'] is not None:
                p['wopr'] = _round(xf['wopr'], 2)
            if xf['target_share'] is not None:
                p['tsh'] = _round(xf['target_share'], 3)
            if xf['xtd'] is not None:
                p['xtd'] = _round(xf['xtd'], 1)
            if xf['td_luck'] is not None:
                p['tdLuck'] = _round(xf['td_luck'], 1)
        n += 1
    return n


def player_season_xfp_payload(con, year):
    """Season grain only. CHI-114 binds fp / xfp / fpoe on season+player_id.

    Do not put weekly yards or TDs on this object.
    """
    raw = rows(con, """
        SELECT season, player_id, fp, xfp, fpoe
          FROM fact_player_xfp
         WHERE season = ?
         ORDER BY player_id""", (year,))
    if not raw:
        return None
    return {
        'grain': 'season+player_id',
        'scoring': 'NON_PPR',
        'recIsVolume': True,
        'source': 'fact_player_xfp',
        'note': SAVANT_FANTASY_NOTE,
        'rows': [{
            'season': r['season'],
            'player_id': r['player_id'],
            'fp': _round(r['fp'], 1),
            'xfp': _round(r['xfp'], 1),
            'fpoe': _round(r['fpoe'], 1),
        } for r in raw],
    }


def player_week_nfl_payload(con, year):
    """Week grain only. CHI-114 binds pbp volume/TDs and nfl_week yards.

    Keys are season+week+gsis_id. player_id is a dim_player join, not a key.
    XFP / FPOE / air yards stay off this object. Receptions are volume.
    """
    raw = rows(con, """
        SELECT a.season, a.week, a.gsis_id, p.player_id,
               a.targets, a.receptions, a.rush_td, a.pass_td, a.rec_td,
               n.pass_yards, n.rush_yards
          FROM fact_pbp_agg a
          LEFT JOIN dim_player p ON p.gsis_id = a.gsis_id
          LEFT JOIN fact_nfl_week n
            ON n.season = a.season AND n.week = a.week AND n.gsis_id = a.gsis_id
         WHERE a.season = ?
         ORDER BY a.week, a.gsis_id""", (year,))
    if not raw:
        return None
    return {
        'grain': 'season+week+gsis_id',
        'scoring': 'NON_PPR',
        'recIsVolume': True,
        'source': 'fact_pbp_agg + fact_nfl_week via dim_player',
        'note': SAVANT_FANTASY_NOTE,
        'rows': [{
            'season': r['season'],
            'week': r['week'],
            'gsis_id': r['gsis_id'],
            'player_id': r['player_id'],
            'targets': _round(r['targets'], 0),
            'receptions': _round(r['receptions'], 0),
            'rush_td': _round(r['rush_td'], 0),
            'pass_td': _round(r['pass_td'], 0),
            'rec_td': _round(r['rec_td'], 0),
            'pass_yards': _round(r['pass_yards'], 1),
            'rush_yards': _round(r['rush_yards'], 1),
        } for r in raw],
    }


def ensure_year_bundle(year):
    """Create an NFL-only stub so 2013 (and any missing play year) can ship."""
    path = os.path.join(YEARS, f'{year}.json')
    if os.path.exists(path):
        return path
    os.makedirs(YEARS, exist_ok=True)
    stub = {
        'year': year,
        'nflOnly': True,
        'hasRosters': False,
        'hasTx': False,
        'players': [],
        'weeks': {},
        'note': 'NFL play year. AFFL league history starts 2014. '
                'playerWeekNfl is the weekly bind; playerSeasonXfp is empty '
                'when fact_nfl_week has no rows.',
    }
    json.dump(stub, open(path, 'w'))
    return path


def affl_fantasy_payload(con, year):
    started = rows(con, """
        SELECT x.player_id AS pid, p.name, p.position AS pos,
               x.st_games AS starts, x.st_fp AS fp, x.st_xfp AS xfp,
               x.st_fpoe AS fpoe, x.wopr, x.target_share AS tsh,
               x.air_yards_share AS ayShare, x.rz_opp AS rzOpp,
               x.xtd, x.td_luck AS tdLuck
          FROM fact_player_xfp x
          JOIN dim_player p ON p.player_id = x.player_id
         WHERE x.season = ? AND x.st_games > 0
           AND p.position IN ('QB', 'RB', 'WR', 'TE')
         ORDER BY x.st_fpoe DESC""", (year,))
    if not started:
        return None
    return {
        'scoring': 'NON_PPR',
        'recIsVolume': True,
        'source': 'AFFL dim_scoring',
        'note': SAVANT_FANTASY_NOTE,
        'started': [{
            'pid': r['pid'], 'name': r['name'], 'pos': r['pos'],
            'starts': r['starts'],
            'fp': _round(r['fp'], 1), 'xfp': _round(r['xfp'], 1),
            'fpoe': _round(r['fpoe'], 1),
            'wopr': _round(r['wopr'], 2),
            'tsh': _round(r['tsh'], 3),
            'ayShare': _round(r['ayShare'], 3),
            'rzOpp': _round(r['rzOpp'], 0),
            'xtd': _round(r['xtd'], 1),
            'tdLuck': _round(r['tdLuck'], 1),
        } for r in started],
    }


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


def backfill_roster_pmeta(con, bundle, year):
    """Name every player in the recovered pre-2018 lineups.

    process_seasons builds pmeta from the boxscore, the draft and the tx log. A
    player who was rostered but neither drafted nor transacted has no entry, and
    the scoreboard falls through to an em-dash — 19 of 2017's starters rendered
    that way. fact_roster_week is what the scoreboard is drawing, so it is also
    the right list to name from. Returns the pids it filled.
    """
    pmeta = bundle.setdefault('pmeta', {})
    known = dict(con.execute("""
        SELECT player_id, name FROM dim_player WHERE name <> ''"""))
    pos_by = dict(con.execute("""
        SELECT player_id, position FROM dim_player WHERE name <> ''"""))
    # Six pre-2018 starters are in the recovered lineups but never made it into
    # dim_player (no boxscore, no nflverse espn_id). The season's ESPN pool has
    # them, so fall back to it rather than leaving an em-dash on the scoreboard.
    pool = load_player_pool(year)
    # The scoreboard reads pmeta -> player_index -> roster snapshot, so only fill
    # ids none of those name. Overwriting a name player_index already resolves
    # would swap the ESPN form the league actually saw for nflverse's legal one
    # (Stevie Johnson -> Steve Johnson), which is churn, not a fix.
    named_elsewhere = set()
    for rel, sub in (('player_index.json', None), ('pre2018_rosters.json', str(year))):
        path = os.path.join(HERE, 'site', rel)
        if not os.path.exists(path):
            continue
        src = json.load(open(path))
        if sub is not None:
            src = src.get(sub) or {}
        named_elsewhere |= {int(k) for k, v in src.items() if (v or {}).get('name')}
    filled = []
    for (pid,) in con.execute(
            'SELECT DISTINCT player_id FROM fact_roster_week WHERE season = ?', (year,)):
        cur = pmeta.get(str(pid))
        if (cur and cur[0]) or pid in named_elsewhere:
            continue
        if pid in known:
            pmeta[str(pid)] = [known[pid], pos_by.get(pid) or '?', '', '']
        elif pid in pool:
            pmeta[str(pid)] = [pool[pid]['name'], pool[pid]['pos'], '', '']
        else:
            continue
        filled.append(pid)
    return filled


def export_year(con, year):
    path = os.path.join(YEARS, f'{year}.json')
    if not os.path.exists(path):
        return None
    bundle = json.load(open(path))
    filled = backfill_roster_pmeta(con, bundle, year)

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
    # 2014-2017 only, and never merged into bundle['lineupIQ'] - that key is a
    # season aggregate over full rosters and pre-2018 has neither.
    iq_pre = export_pre2018_lineup_iq(con, year)
    if iq_pre:
        bundle['lineupIQPre2018'] = iq_pre
    else:
        bundle.pop('lineupIQPre2018', None)
    compute_eight.patch_year(con, bundle, year)
    # CHI-114: attach bind objects when the warehouse has them. Empty tables
    # return None — keep the keys already on disk so an export cannot wipe
    # a shipped bind.
    sx = player_season_xfp_payload(con, year)
    if sx:
        bundle['playerSeasonXfp'] = sx
    wk = player_week_nfl_payload(con, year)
    if wk:
        bundle['playerWeekNfl'] = wk
    json.dump(bundle, open(path, 'w'))
    return {'year': year, 'steals': len(steals), 'power': len(power),
            'cap_teams': len(cap), 'baselines': len(baselines),
            'roto': 0 if bundle['roto'] is None else len(bundle['roto']['reg']['teams'])}


def export_pre2018_lineup_iq(con, year):
    """Start/sit efficiency for 2014-2017, only where the bench is actually known.

    Lineup IQ needs a bench, and pre-2018 has one for exactly the team-weeks whose
    roster snapshot could be dated - see load_pre2018_bench.py. This is NOT the
    season-aggregate `lineupIQ` that 2018+ publishes and must not be pooled with it:
    it is one week per team, usually a playoff week, so it goes in its own key.

    The two halves have different provenance, which is why every record carries the
    counts behind it:

      actual   ESPN's own starter points, exact.
      optimal  the best legal lineup from the full snapshot roster. Starters keep
               their ESPN points, so the lineup actually fielded is always feasible
               and optimal >= actual holds by construction. Bench points are
               computed by the same engine validate_scoring.py gates.

    A rostered player with no stat row that week scored nothing - inactive, bye, or
    simply no production - so 0 is the right value, not a gap. A player the engine
    CANNOT score is a different thing, and a team-week containing one is dropped
    rather than published with an optimum we know is too low.
    """
    if year > 2017:
        return None
    from build_candidate_scores import all_scores

    dated = rows(con, """
        SELECT DISTINCT team_id, dated_week FROM fact_roster_snapshot_pre2018
         WHERE season = ? AND dated_week IS NOT NULL
         ORDER BY team_id""", (year,))
    if not dated:
        return None

    srow = con.execute(
        'SELECT slot_qb, slot_rb, slot_wr, slot_te, slot_flex, slot_dst, slot_k, '
        'reg_weeks FROM dim_season WHERE season = ?', (year,)).fetchone()
    slots = {'QB': srow[0], 'RB': srow[1], 'WR': srow[2], 'TE': srow[3],
             'FLEX': srow[4], 'DST': srow[5], 'K': srow[6]}
    reg_weeks = srow[7]

    scores = all_scores(con, year)
    out = []
    for r in dated:
        tid, week = r['team_id'], r['dated_week']
        roster = rows(con, """
            SELECT s.player_id, s.slot, p.position
              FROM fact_roster_snapshot_pre2018 s
              LEFT JOIN dim_player p ON p.player_id = s.player_id
             WHERE s.season = ? AND s.team_id = ?""", (year, tid))
        started = {pid: pts for pid, pts in con.execute(
            'SELECT player_id, points FROM fact_roster_week '
            'WHERE season=? AND week=? AND team_id=? AND started=1', (year, week, tid))}

        entries, unscoreable, no_stat = [], 0, 0
        for m in roster:
            pid = m['player_id']
            pos = (m['position'] or '').strip()
            if pos == 'D/ST':
                pos = 'DST'
            if pid in started:
                entries.append((pos, started[pid]))
                continue
            hit = scores.get((week, pid))
            if hit is not None:
                entries.append((pos, hit[0]))
            elif pos == 'DST':
                # The D/ST engine covers a fixed set of team ids; a miss here is the
                # engine, not a real zero, so the optimum for this team-week is
                # unknown rather than low.
                unscoreable += 1
            else:
                entries.append((pos, 0.0))
                no_stat += 1
        if unscoreable:
            continue

        actual = round(sum(started.values()), 2)
        optimal = optimal_points(entries, slots)
        if optimal + 0.005 < actual:
            # Cannot happen while starters keep their ESPN points. If it ever does,
            # the roster and the lineup disagree - say so instead of publishing it.
            print(f'  WARN {year} w{week} team {tid}: optimal {optimal} < '
                  f'actual {actual}; skipped')
            continue
        out.append({
            'teamId': tid,
            'week': week,
            'phase': 'regular' if week <= reg_weeks else 'playoff',
            'actual': round(actual, 1),
            'optimal': round(optimal, 1),
            'eff': round(actual / optimal, 4) if optimal else None,
            'wasted': round(optimal - actual, 1),
            'rosterSize': len(roster),
            'benchNoStat': no_stat,
        })
    return out or None


def main():
    con = sqlite3.connect(DB)
    years = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    for y in years:
        info = export_year(con, y)
        if info:
            print(f"  {info['year']}: {info['steals']} steals · {info['power']} power rows "
                  f"· {info['cap_teams']} teams w/ cap · {info['baselines']} baselines"
                  f" · {info.get('roto', 0)} roto")
    # site/pre2018_starts.json is what the scoreboard and Players read for
    # 2014-2017 lineups. It used to be hand-maintained, which is how it came to
    # label every pre-2018 starter QB; regenerate it from the warehouse instead.
    # It is not purely derivable: a few team-weeks the warehouse deliberately
    # excludes survive only in the file, so the generator merges them forward and
    # refuses to write if any complete team-week stops reconciling.
    import regen_pre2018_starts
    if regen_pre2018_starts.main(write=True, con=con):
        raise SystemExit('pre2018_starts regeneration failed its reconciliation gate')
    # site/pre2018_rosters.json stays a checked-in artifact on purpose: it also
    # carries draft-only players (draftTid) that no warehouse table models, and
    # players.js reads them. fact_roster_snapshot_pre2018 covers the rostered set
    # only, so regenerating from it would silently drop the rest.
    write_roto_career(con)
    compute_eight.write_player_bio(con)
    compute_eight.write_miles(con)
    print('site/years/*.json patched from affl.db')

if __name__ == '__main__':
    main()
