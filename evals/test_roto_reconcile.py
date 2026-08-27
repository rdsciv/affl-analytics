#!/usr/bin/env python3
"""Reconcile 10-category roto season totals and weekly trends.

Recomputes 2025 regular-phase category totals from started roster weeks
joined to nflverse weeks (same join as compute_roto.py) and asserts
fact_roto_team_season matches. After weekly facts exist, weekly rows
must sum to the season row. Site roto pages stay runtime-computed.
"""
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
SITE = ROOT / "site"
FEELERS_OWNER = "m18"
FEELERS_YEAR = 2025
TOL = 1e-6

PHASE_MATCH = {
    "regular": "m.phase = 'regular'",
    "championship": "m.phase = 'championship'",
    "combined": "m.phase IN ('regular', 'championship')",
}
CATS = (
    ("py", "py"),
    ("ptd", "ptd"),
    ("compPct", "comp_pct"),
    ("ry", "ry"),
    ("rtd", "rtd"),
    ("ypc", "ypc"),
    ("recy", "recy"),
    ("retd", "retd"),
    ("rec", "rec"),
    ("ypr", "ypr"),
)
SEASON_ASSERT = ("py", "ptd", "ry", "rtd", "rec", "recy", "retd", "games", "total_pts", "total_rank")
WEEK_SUM_CATS = ("py", "ptd", "ry", "recy", "rec")
BANNED_LITERALS = ("3452", "3932", "81")

fails = []


def fail(msg):
    fails.append(msg)


def connect():
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def feelers_team_id():
    data = json.loads((SITE / "data.json").read_text())
    teams = data["seasons"][str(FEELERS_YEAR)]["teams"]
    t = next((x for x in teams if x["owner"] == FEELERS_OWNER), None)
    if t is None:
        fail(f"data.json 2025 has no owner {FEELERS_OWNER}")
        return None
    return t["id"]


def _empty():
    return dict(py=0.0, ptd=0.0, cmp=0.0, att=0.0,
                ry=0.0, rtd=0.0, car=0.0,
                rec=0.0, recy=0.0, retd=0.0)


def recompute_phase(con, season, phase):
    """Same join as compute_roto.py: started skill + v_matchup + fact_nfl_week."""
    clause = PHASE_MATCH[phase]
    games = defaultdict(int)
    for (tid,) in con.execute(
            f"SELECT team_id FROM v_matchup m WHERE m.season = ? AND {clause}",
            (season,)):
        games[tid] += 1
    if not games:
        return {}
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
    value_key = {export: db for export, db in CATS}
    for export, db in CATS:
        ordered = sorted(derived, key=lambda d: (-d[db], d["team_id"]))
        for i, d in enumerate(ordered):
            d[f"{db}_rank"] = i + 1
            d[f"{db}_pts"] = n - i
    for d in derived:
        d["total_pts"] = sum(d[f"{value_key[e]}_pts"] for e, _ in CATS)
    derived.sort(key=lambda d: (-d["total_pts"], d["team_id"]))
    for i, d in enumerate(derived):
        d["total_rank"] = i + 1
    return {d["team_id"]: d for d in derived}


def warehouse_phase(con, season, phase):
    rows = con.execute("""
        SELECT team_id, games, py, ptd, ry, rtd, rec, recy, retd,
               total_pts, total_rank
          FROM fact_roto_team_season
         WHERE season = ? AND phase = ?
    """, (season, phase)).fetchall()
    return {r["team_id"]: dict(r) for r in rows}


def close(a, b):
    return abs(float(a) - float(b)) <= TOL


def test_2025_regular_matches_recompute(con):
    recomputed = recompute_phase(con, 2025, "regular")
    stored = warehouse_phase(con, 2025, "regular")
    if len(recomputed) != 12:
        fail(f"recompute produced {len(recomputed)} teams, expected 12")
    if len(stored) != 12:
        fail(f"fact_roto_team_season 2025 regular has {len(stored)} teams, expected 12")
    for tid in sorted(set(recomputed) | set(stored)):
        if tid not in recomputed:
            fail(f"team {tid} in warehouse but missing from recompute")
            continue
        if tid not in stored:
            fail(f"team {tid} in recompute but missing from warehouse")
            continue
        rec, wh = recomputed[tid], stored[tid]
        for col in SEASON_ASSERT:
            if col in ("total_pts", "total_rank", "games"):
                if int(wh[col]) != int(rec[col]):
                    fail(f"team {tid} {col}: warehouse {wh[col]} != recompute {rec[col]}")
            else:
                if not close(wh[col], rec[col]):
                    fail(f"team {tid} {col}: warehouse {wh[col]} != recompute {rec[col]}")
    return recomputed, stored


def test_feelers_equals_recompute(con, recomputed, stored):
    tid = feelers_team_id()
    if tid != 7:
        fail(f"Feelers 2025 team_id should be 7 (data.json owner m18), got {tid}")
    if tid is None:
        return
    rec = recomputed.get(tid)
    if rec is None:
        fail(f"recompute missing Feelers team_id {tid}")
        return
    print(
        "Feelers 2025 recomputed regular: "
        f"team_id={tid} games={rec['games']} "
        f"py={rec['py']} ptd={rec['ptd']} ry={rec['ry']} rtd={rec['rtd']} "
        f"rec={rec['rec']} recy={rec['recy']} retd={rec['retd']} "
        f"total_pts={rec['total_pts']} total_rank={rec['total_rank']}"
    )
    wh = stored.get(tid)
    if wh is None:
        fail(f"warehouse missing Feelers team_id {tid} 2025 regular")
        return
    for col in SEASON_ASSERT:
        if col in ("total_pts", "total_rank", "games"):
            if int(wh[col]) != int(rec[col]):
                fail(f"Feelers warehouse {col} {wh[col]} != recompute {rec[col]}")
        elif not close(wh[col], rec[col]):
            fail(f"Feelers warehouse {col} {wh[col]} != recompute {rec[col]}")


def test_no_pre2018_rows(con):
    """Roto season rows still must not exist for 2014-2017 - but for the right reason.

    Recovered starters are not enough to build them. Roto counts a team's whole
    season of accumulated stats, which needs full rosters; pre-2018 has starters
    only and no transaction feed, so dim_season.has_rosters stays 0 and
    compute_roto.py (which selects on that flag) skips those years. Assert the
    flag, not the absence of lineups - the lineups are there now.
    """
    n = con.execute(
        "SELECT COUNT(*) FROM fact_roto_team_season WHERE season BETWEEN 2014 AND 2017"
    ).fetchone()[0]
    lineups = con.execute(
        "SELECT COUNT(*) FROM fact_roster_week WHERE season BETWEEN 2014 AND 2017"
    ).fetchone()[0]
    flagged = [s for (s,) in con.execute(
        "SELECT season FROM dim_season "
        "WHERE season BETWEEN 2014 AND 2017 AND has_rosters = 1")]
    print(f"2014-2017 fact_roto_team_season rows: {n}")
    print(f"2014-2017 fact_roster_week rows: {lineups} (recovered starters)")
    if flagged:
        fail(f"has_rosters=1 for {flagged}; pre-2018 has no bench, so roto cannot "
             f"be built from it")
    if n:
        fail(f"2014-2017 have {n} fact_roto_team_season rows; roto needs full "
             f"rosters and pre-2018 has starters only")


def test_weekly_sums_to_season(con):
    names = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_roto_team_week'"
    )}
    if "fact_roto_team_week" not in names:
        fail("fact_roto_team_week does not exist")
        return
    stored = warehouse_phase(con, 2025, "regular")
    weekly = list(con.execute("""
        SELECT team_id, week, py, ptd, ry, recy, rec
          FROM fact_roto_team_week
         WHERE season = 2025 AND phase = 'regular'
    """))
    if not weekly:
        fail("fact_roto_team_week has no 2025 regular rows")
        return
    sums = defaultdict(lambda: {c: 0.0 for c in WEEK_SUM_CATS})
    weeks = defaultdict(set)
    for r in weekly:
        tid = r["team_id"]
        weeks[tid].add(r["week"])
        for c in WEEK_SUM_CATS:
            sums[tid][c] += r[c] or 0
    for tid, wh in stored.items():
        if tid not in sums:
            fail(f"team {tid} has a 2025 regular season row but no weekly rows")
            continue
        for c in WEEK_SUM_CATS:
            if not close(sums[tid][c], wh[c]):
                fail(f"team {tid} weekly sum {c}={sums[tid][c]} != season {wh[c]}")
    tid = feelers_team_id() or 7
    week_count = len(weeks.get(tid, ()))
    games = stored.get(tid, {}).get("games")
    starter_weeks = con.execute("""
        SELECT COUNT(DISTINCT r.week)
          FROM fact_roster_week r
          JOIN v_matchup m
            ON m.season = r.season AND m.week = r.week AND m.team_id = r.team_id
         WHERE r.season = 2025 AND r.team_id = ? AND r.started = 1
           AND m.phase = 'regular'
    """, (tid,)).fetchone()[0]
    print(f"Feelers 2025 regular weekly rows: {week_count}")
    print(f"Feelers 2025 regular games (season row): {games}")
    print(f"Feelers 2025 regular matchup weeks with starters: {starter_weeks}")
    if week_count != games and week_count != starter_weeks:
        fail(
            f"Feelers weekly row count {week_count} matches neither "
            f"regular games ({games}) nor starter-matchup weeks ({starter_weeks})"
        )


def test_site_no_hardcoded_totals():
    for name in ("roto-math.js", "roto.js"):
        text = (SITE / name).read_text()
        for lit in BANNED_LITERALS:
            if re.search(r"\b" + lit + r"\b", text):
                fail(f"{name} contains hardcoded literal {lit}")


def main():
    con = connect()
    recomputed, stored = test_2025_regular_matches_recompute(con)
    test_feelers_equals_recompute(con, recomputed, stored)
    test_no_pre2018_rows(con)
    test_weekly_sums_to_season(con)
    test_site_no_hardcoded_totals()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("2025 regular warehouse matches independent recompute for all 12 teams")
    print("Weekly 2025 regular rows sum to season totals")
    print("roto-math.js / roto.js have no hardcoded season totals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
