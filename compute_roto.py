#!/usr/bin/env python3
"""Rotisserie standings from started-player NFL stats.

AFFL is H2H points. This re-scores starter production as 10-category roto.
Player-level lineups exist from 2018; 2014-2017 stay unavailable.

    python3 compute_roto.py
    python3 compute_roto.py --season 2025

Join: fact_roster_week (started=1) -> dim_player.gsis_id -> fact_nfl_week
      + v_matchup phase. Players without gsis_id contribute nothing.
Games are matchup sides in that phase, not starter-week counts.

Phases:
  regular       is_playoff = 0
  championship  tier = WINNERS_BRACKET
  combined      those two. Consolation excluded.
"""
import argparse
import os
import sqlite3
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "affl.db")

FIRST_YEAR = 2018
PHASES = ("regular", "championship", "combined")
PHASE_MATCH = {
    "regular": "m.phase = 'regular'",
    "championship": "m.phase = 'championship'",
    "combined": "m.phase IN ('regular', 'championship')",
}

CATS = (
    ("py", "Pass Yds", "Passing", "py"),
    ("ptd", "Pass TD", "Passing", "ptd"),
    ("compPct", "Comp%", "Passing", "comp_pct"),
    ("ry", "Rush Yds", "Rushing", "ry"),
    ("rtd", "Rush TD", "Rushing", "rtd"),
    ("ypc", "YPC", "Rushing", "ypc"),
    ("recy", "Rec Yds", "Receiving", "recy"),
    ("retd", "Rec TD", "Receiving", "retd"),
    ("rec", "Rec", "Receiving", "rec"),
    ("ypr", "YPR", "Receiving", "ypr"),
)

DDL = """
CREATE TABLE IF NOT EXISTS fact_roto_team_season (
  season INTEGER NOT NULL,
  phase TEXT NOT NULL,
  team_id INTEGER NOT NULL,
  games INTEGER NOT NULL,
  py REAL NOT NULL DEFAULT 0,
  ptd REAL NOT NULL DEFAULT 0,
  cmp REAL NOT NULL DEFAULT 0,
  att REAL NOT NULL DEFAULT 0,
  ry REAL NOT NULL DEFAULT 0,
  rtd REAL NOT NULL DEFAULT 0,
  car REAL NOT NULL DEFAULT 0,
  rec REAL NOT NULL DEFAULT 0,
  recy REAL NOT NULL DEFAULT 0,
  retd REAL NOT NULL DEFAULT 0,
  comp_pct REAL NOT NULL DEFAULT 0,
  ypc REAL NOT NULL DEFAULT 0,
  ypr REAL NOT NULL DEFAULT 0,
  py_rank INTEGER, py_pts INTEGER,
  ptd_rank INTEGER, ptd_pts INTEGER,
  comp_pct_rank INTEGER, comp_pct_pts INTEGER,
  ry_rank INTEGER, ry_pts INTEGER,
  rtd_rank INTEGER, rtd_pts INTEGER,
  ypc_rank INTEGER, ypc_pts INTEGER,
  recy_rank INTEGER, recy_pts INTEGER,
  retd_rank INTEGER, retd_pts INTEGER,
  rec_rank INTEGER, rec_pts INTEGER,
  ypr_rank INTEGER, ypr_pts INTEGER,
  total_pts INTEGER NOT NULL,
  total_rank INTEGER NOT NULL,
  PRIMARY KEY (season, phase, team_id)
);

CREATE TABLE IF NOT EXISTS fact_roto_team_week (
  season INTEGER NOT NULL,
  phase TEXT NOT NULL,
  week INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  py REAL NOT NULL DEFAULT 0,
  ptd REAL NOT NULL DEFAULT 0,
  cmp REAL NOT NULL DEFAULT 0,
  att REAL NOT NULL DEFAULT 0,
  ry REAL NOT NULL DEFAULT 0,
  rtd REAL NOT NULL DEFAULT 0,
  car REAL NOT NULL DEFAULT 0,
  rec REAL NOT NULL DEFAULT 0,
  recy REAL NOT NULL DEFAULT 0,
  retd REAL NOT NULL DEFAULT 0,
  comp_pct REAL NOT NULL DEFAULT 0,
  ypc REAL NOT NULL DEFAULT 0,
  ypr REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (season, phase, week, team_id)
);

DROP VIEW IF EXISTS v_roto_standings;
CREATE VIEW v_roto_standings AS
SELECT r.season, r.phase, r.team_id, t.owner_id, t.owner_name, t.name AS team_name,
       r.games, r.py, r.ptd, r.cmp, r.att, r.comp_pct, r.ry, r.rtd, r.car, r.ypc,
       r.recy, r.retd, r.rec, r.ypr,
       r.py_rank, r.py_pts, r.ptd_rank, r.ptd_pts,
       r.comp_pct_rank, r.comp_pct_pts, r.ry_rank, r.ry_pts,
       r.rtd_rank, r.rtd_pts, r.ypc_rank, r.ypc_pts,
       r.recy_rank, r.recy_pts, r.retd_rank, r.retd_pts,
       r.rec_rank, r.rec_pts, r.ypr_rank, r.ypr_pts,
       r.total_pts, r.total_rank
  FROM fact_roto_team_season r
  JOIN v_team t ON t.season = r.season AND t.team_id = r.team_id;
"""


def ensure_schema(con):
    con.executescript(DDL)


def _empty():
    return dict(py=0.0, ptd=0.0, cmp=0.0, att=0.0,
                ry=0.0, rtd=0.0, car=0.0,
                rec=0.0, recy=0.0, retd=0.0)


def coverage(con, season):
    """Skill-starter join gaps for a season (regular + all phases)."""
    rows = list(con.execute("""
        SELECT r.week, r.team_id, r.player_id, p.name, p.position, p.gsis_id,
               r.points, n.gsis_id IS NOT NULL AS nfl_hit
          FROM fact_roster_week r
          JOIN dim_player p ON p.player_id = r.player_id
         LEFT JOIN fact_nfl_week n
                ON n.season = r.season AND n.week = r.week AND n.gsis_id = p.gsis_id
         WHERE r.season = ? AND r.started = 1
    """, (season,)))
    skill_no_gsis = []
    skill_no_nfl = []
    for week, tid, pid, name, pos, gsis, pts, hit in rows:
        if pos in ("DST", "D/ST", "K"):
            continue
        if not gsis:
            skill_no_gsis.append((week, tid, pid, name, pos, pts))
        elif not hit:
            skill_no_nfl.append((week, tid, pid, name, pos, gsis, pts))
    return skill_no_gsis, skill_no_nfl


def compute_phase(con, season, phase):
    clause = PHASE_MATCH[phase]
    games = defaultdict(int)
    for (tid,) in con.execute(
            f"SELECT team_id FROM v_matchup m WHERE m.season = ? AND {clause}",
            (season,)):
        games[tid] += 1
    if not games:
        return []

    totals = {tid: _empty() for tid in games}
    sql = f"""
        SELECT r.team_id,
               n.pass_yards, n.pass_tds, n.completions, n.attempts,
               n.rush_yards, n.rush_tds, n.carries,
               n.rec_yards, n.rec_tds, n.receptions
          FROM fact_roster_week r
          JOIN dim_player p ON p.player_id = r.player_id
          JOIN v_matchup m
            ON m.season = r.season AND m.week = r.week AND m.team_id = r.team_id
          JOIN fact_nfl_week n
            ON n.season = r.season AND n.week = r.week AND n.gsis_id = p.gsis_id
         WHERE r.season = ? AND r.started = 1 AND {clause}
           AND p.gsis_id IS NOT NULL AND p.gsis_id != ''
    """
    for row in con.execute(sql, (season,)):
        t = totals[row[0]]
        t["py"] += row[1] or 0
        t["ptd"] += row[2] or 0
        t["cmp"] += row[3] or 0
        t["att"] += row[4] or 0
        t["ry"] += row[5] or 0
        t["rtd"] += row[6] or 0
        t["car"] += row[7] or 0
        t["recy"] += row[8] or 0
        t["retd"] += row[9] or 0
        t["rec"] += row[10] or 0

    derived = []
    for tid, raw in totals.items():
        derived.append({
            "team_id": tid,
            "games": games[tid],
            "py": raw["py"], "ptd": raw["ptd"],
            "cmp": raw["cmp"], "att": raw["att"],
            "ry": raw["ry"], "rtd": raw["rtd"], "car": raw["car"],
            "rec": raw["rec"], "recy": raw["recy"], "retd": raw["retd"],
            "comp_pct": (raw["cmp"] / raw["att"] * 100) if raw["att"] else 0.0,
            "ypc": (raw["ry"] / raw["car"]) if raw["car"] else 0.0,
            "ypr": (raw["recy"] / raw["rec"]) if raw["rec"] else 0.0,
        })

    n = len(derived)
    value_key = {export: db for export, _label, _g, db in CATS}
    for export, _label, _g, db in CATS:
        ordered = sorted(derived, key=lambda d: (-d[db], d["team_id"]))
        for i, d in enumerate(ordered):
            d[f"{db}_rank"] = i + 1
            d[f"{db}_pts"] = n - i

    for d in derived:
        d["total_pts"] = sum(d[f"{value_key[e]}_pts"] for e, *_ in CATS)
    derived.sort(key=lambda d: (-d["total_pts"], d["team_id"]))
    for i, d in enumerate(derived):
        d["total_rank"] = i + 1
    return derived


def persist(con, season, phase, rows):
    con.execute(
        "DELETE FROM fact_roto_team_season WHERE season = ? AND phase = ?",
        (season, phase))
    con.executemany("""
        INSERT INTO fact_roto_team_season (
          season, phase, team_id, games,
          py, ptd, cmp, att, ry, rtd, car, rec, recy, retd,
          comp_pct, ypc, ypr,
          py_rank, py_pts, ptd_rank, ptd_pts, comp_pct_rank, comp_pct_pts,
          ry_rank, ry_pts, rtd_rank, rtd_pts, ypc_rank, ypc_pts,
          recy_rank, recy_pts, retd_rank, retd_pts, rec_rank, rec_pts,
          ypr_rank, ypr_pts, total_pts, total_rank
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        season, phase, d["team_id"], d["games"],
        d["py"], d["ptd"], d["cmp"], d["att"],
        d["ry"], d["rtd"], d["car"], d["rec"], d["recy"], d["retd"],
        d["comp_pct"], d["ypc"], d["ypr"],
        d["py_rank"], d["py_pts"], d["ptd_rank"], d["ptd_pts"],
        d["comp_pct_rank"], d["comp_pct_pts"],
        d["ry_rank"], d["ry_pts"], d["rtd_rank"], d["rtd_pts"],
        d["ypc_rank"], d["ypc_pts"],
        d["recy_rank"], d["recy_pts"], d["retd_rank"], d["retd_pts"],
        d["rec_rank"], d["rec_pts"], d["ypr_rank"], d["ypr_pts"],
        d["total_pts"], d["total_rank"],
    ) for d in rows])


def compute_phase_weeks(con, season, phase):
    """Same join as compute_phase, grouped by week. One row per matchup side."""
    clause = PHASE_MATCH[phase]
    sides = list(con.execute(
            f"SELECT week, team_id FROM v_matchup m WHERE m.season = ? AND {clause}",
            (season,)))
    if not sides:
        return []
    totals = {(week, tid): _empty() for week, tid in sides}
    sql = f"""
        SELECT r.week, r.team_id,
               n.pass_yards, n.pass_tds, n.completions, n.attempts,
               n.rush_yards, n.rush_tds, n.carries,
               n.rec_yards, n.rec_tds, n.receptions
          FROM fact_roster_week r
          JOIN dim_player p ON p.player_id = r.player_id
          JOIN v_matchup m
            ON m.season = r.season AND m.week = r.week AND m.team_id = r.team_id
          JOIN fact_nfl_week n
            ON n.season = r.season AND n.week = r.week AND n.gsis_id = p.gsis_id
         WHERE r.season = ? AND r.started = 1 AND {clause}
           AND p.gsis_id IS NOT NULL AND p.gsis_id != ''
    """
    for row in con.execute(sql, (season,)):
        key = (row[0], row[1])
        if key not in totals:
            continue
        t = totals[key]
        t["py"] += row[2] or 0
        t["ptd"] += row[3] or 0
        t["cmp"] += row[4] or 0
        t["att"] += row[5] or 0
        t["ry"] += row[6] or 0
        t["rtd"] += row[7] or 0
        t["car"] += row[8] or 0
        t["recy"] += row[9] or 0
        t["retd"] += row[10] or 0
        t["rec"] += row[11] or 0

    derived = []
    for (week, tid), raw in totals.items():
        derived.append({
            "week": week,
            "team_id": tid,
            "py": raw["py"], "ptd": raw["ptd"],
            "cmp": raw["cmp"], "att": raw["att"],
            "ry": raw["ry"], "rtd": raw["rtd"], "car": raw["car"],
            "rec": raw["rec"], "recy": raw["recy"], "retd": raw["retd"],
            "comp_pct": (raw["cmp"] / raw["att"] * 100) if raw["att"] else 0.0,
            "ypc": (raw["ry"] / raw["car"]) if raw["car"] else 0.0,
            "ypr": (raw["recy"] / raw["rec"]) if raw["rec"] else 0.0,
        })
    return derived


def persist_weeks(con, season, phase, rows):
    con.execute(
        "DELETE FROM fact_roto_team_week WHERE season = ? AND phase = ?",
        (season, phase))
    if not rows:
        return
    con.executemany("""
        INSERT INTO fact_roto_team_week (
          season, phase, week, team_id,
          py, ptd, cmp, att, ry, rtd, car, rec, recy, retd,
          comp_pct, ypc, ypr
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        season, phase, d["week"], d["team_id"],
        d["py"], d["ptd"], d["cmp"], d["att"],
        d["ry"], d["rtd"], d["car"], d["rec"], d["recy"], d["retd"],
        d["comp_pct"], d["ypc"], d["ypr"],
    ) for d in rows])


def compute_all(con, seasons=None):
    ensure_schema(con)
    if seasons is None:
        seasons = [s for (s,) in con.execute(
            "SELECT season FROM dim_season WHERE has_rosters = 1 ORDER BY season")]
    n = 0
    for season in seasons:
        if season < FIRST_YEAR:
            continue
        for phase in PHASES:
            rows = compute_phase(con, season, phase)
            persist(con, season, phase, rows)
            n += len(rows)
            weeks = compute_phase_weeks(con, season, phase)
            persist_weeks(con, season, phase, weeks)
    return n


def career_rows(con, phase="regular"):
    """Average roto finish across scored seasons. Missing years are omitted, not zero-filled."""
    acc = {}
    scored = []
    for season, in con.execute("""
        SELECT DISTINCT season FROM fact_roto_team_season
         WHERE phase = ? ORDER BY season
    """, (phase,)):
        teams = list(con.execute("""
            SELECT owner_id, owner_name, total_rank, total_pts
              FROM v_roto_standings
             WHERE season = ? AND phase = ?
        """, (season, phase)))
        if not teams:
            continue
        scored.append(season)
        nteams = len(teams)
        for oid, name, rank, pts in teams:
            if not oid:
                continue
            c = acc.get(oid)
            if c is None:
                c = dict(owner_id=oid, manager=name, seasons=0,
                         rank_sum=0, pts_sum=0, best=99, worst=0, by_year={})
                acc[oid] = c
            c["seasons"] += 1
            c["rank_sum"] += rank
            c["pts_sum"] += pts
            c["best"] = min(c["best"], rank)
            c["worst"] = max(c["worst"], rank)
            c["by_year"][season] = {"rank": rank, "pts": pts, "nTeams": nteams}
    rows = []
    for c in acc.values():
        rows.append({
            "ownerId": c["owner_id"],
            "manager": c["manager"],
            "seasons": c["seasons"],
            "avgRank": c["rank_sum"] / c["seasons"],
            "bestRank": c["best"],
            "worstRank": c["worst"],
            "avgPts": c["pts_sum"] / c["seasons"],
            "byYear": c["by_year"],
        })
    rows.sort(key=lambda r: (r["avgRank"], r["manager"]))
    return {
        "scoredYears": scored,
        "missingYears": [],
        "evidence": "Verified" if scored else "Unavailable",
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    args = ap.parse_args()
    con = sqlite3.connect(DB)
    seasons = [args.season] if args.season else None
    n = compute_all(con, seasons)
    con.commit()
    nw = con.execute("SELECT COUNT(*) FROM fact_roto_team_week").fetchone()[0]
    print(f"fact_roto_team_season {n} rows")
    print(f"fact_roto_team_week {nw} rows")

    focus = args.season or 2025
    print(f"\n{focus} regular")
    for r in con.execute("""
        SELECT total_rank, team_name, games, total_pts, py, ptd, ry, rtd, ypc_rank
          FROM v_roto_standings
         WHERE season = ? AND phase = 'regular'
         ORDER BY total_rank
    """, (focus,)):
        print(f"  {r[0]:2}  {r[1]:<28} G={r[2]}  {r[3]:3} pts   "
              f"PY {r[4]:.0f}  PTD {r[5]:.0f}  RY {r[6]:.0f}  RTD {r[7]:.0f}  YPC#{r[8]}")

    no_gsis, no_nfl = coverage(con, focus)
    print(f"\njoin coverage {focus} (started skill players):")
    print(f"  missing gsis_id: {len(no_gsis)}")
    dnp = [x for x in no_nfl if (x[6] or 0) == 0]
    live = [x for x in no_nfl if (x[6] or 0) != 0]
    print(f"  gsis but no nfl week: {len(no_nfl)} "
          f"({len(dnp)} zero-point DNP/bye, {len(live)} with fantasy points)")
    for x in no_nfl:
        print(f"    wk{x[0]} {x[3]} ({x[4]}) pts={x[6]} gsis={x[5]}")


if __name__ == "__main__":
    main()
