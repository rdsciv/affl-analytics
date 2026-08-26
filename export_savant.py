#!/usr/bin/env python3
"""Export the Savant explorer payloads.

Read-only against affl.db. Writes only into site/savant/.

One file per season so the browser pulls ~200KB, not the whole warehouse.
Rows are arrays, not objects — the key names live once in meta.json.

AFFL context is what makes this an AFFL view rather than a generic NFL site:
every NFL player-season carries how many times an AFFL manager started them
and which franchise did it, keyed on member_id so a rename never splits a
franchise (m18 is Tittsburgh through 2024 and Grand Teeton after; both are
the same franchise and both resolve to the current name).
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "affl.db")
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "site", "savant")

SKILL = {"QB", "RB", "WR", "TE", "FB", "HB"}

# Row layout. Kept in meta.json so savant.js never hardcodes an index.
COLS = [
    "pid", "name", "pos", "team", "g",
    "tgt", "rec", "recyd", "rectd", "ay", "tgtsh", "aysh", "wopr", "racr",
    "car", "ruyd", "rutd",
    "att", "cmp", "payd", "patd", "int",
    "epa", "fpts", "fppg",
    "starts", "fr",
]

# AFFL scoring, non-PPR. SPEC.md §1. Receptions are volume and score nothing.
PASS_YD, PASS_TD, INT = 0.04, 4.0, -2.0
RUSH_YD, RUSH_TD = 0.10, 6.0
REC_YD, REC_TD = 0.10, 6.0


def load_rosters(season: int) -> dict:
    """gsis_id -> (full_name, team, position) from the nflverse roster file."""
    path = os.path.join(DATA, f"roster_{season}.csv")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            gid = (r.get("gsis_id") or "").strip()
            if not gid:
                continue
            pos = (r.get("position") or "").strip().upper()
            # keep the last non-empty team seen; late-season rows win
            prev = out.get(gid)
            name = (r.get("full_name") or "").strip() or (prev[0] if prev else gid)
            team = (r.get("team") or "").strip() or (prev[1] if prev else "")
            out[gid] = (name, team, pos or (prev[2] if prev else ""))
    return out


def current_names(con) -> dict:
    """member_id -> the franchise's current name."""
    return {m: n for m, n in con.execute(
        "SELECT member_id, name FROM dim_team "
        "WHERE (member_id, season) IN "
        "(SELECT member_id, MAX(season) FROM dim_team GROUP BY member_id)"
    )}


def pre2018_context(con, current) -> tuple:
    """Weekly starts for 2014-2017 from site/pre2018_starts.json.

    ESPN does not retain pre-2018 weekly lineups — leagueHistory returns only
    season totals, verified live. This file is the surviving capture. It is
    trusted only where it can be proved: a team-week counts if its starter
    points sum exactly to that team's fact_matchup score. Team-weeks that do
    not reconcile are dropped, never patched or guessed.

    Returns ((season, gsis_id) -> (starts, franchise), season -> coverage%).
    """
    path = os.path.join(HERE, "site", "pre2018_starts.json")
    if not os.path.exists(path):
        return {}, {}
    with open(path) as fh:
        blob = json.load(fh)

    pid_to_gsis = {str(p): g for p, g in con.execute(
        "SELECT player_id, gsis_id FROM dim_player "
        "WHERE gsis_id IS NOT NULL AND gsis_id != ''")}

    out, coverage = {}, {}
    for y_s, players in blob.items():
        season = int(y_s)
        member = {t: m for t, m in con.execute(
            "SELECT team_id, member_id FROM dim_team WHERE season = ?", (season,))}
        official = {(t, w): p for t, w, p in con.execute(
            "SELECT team_id, week, points FROM fact_matchup WHERE season = ?", (season,))}

        bucket = defaultdict(list)
        for pid, weeks in players.items():
            for wk, rec in weeks.items():
                bucket[(rec.get("tid"), int(wk))].append((pid, rec.get("pts") or 0.0))

        good = 0
        considered = 0
        for (tid, wk), rows in bucket.items():
            off = official.get((tid, wk))
            if off is None:
                continue                       # NFL week outside the AFFL season
            considered += 1
            if abs(sum(p for _, p in rows) - off) > 0.6:
                continue                       # cannot prove this lineup — drop it
            good += 1
            for pid, _ in rows:
                gid = pid_to_gsis.get(str(pid))
                if not gid:
                    continue
                starts, _fr = out.get((season, gid), (0, ""))
                out[(season, gid)] = (starts + 1, current.get(member.get(tid), ""))
        coverage[season] = round(100.0 * good / considered, 1) if considered else 0.0
    return out, coverage


def affl_context(con, current) -> dict:
    """(season, gsis_id) -> (starts, current_franchise_name).

    Franchise identity is member_id, never team_id — three team_ids map to
    more than one member across the league's history.
    """
    out = {}
    q = """
        SELECT r.season, p.gsis_id, m.member_id, COUNT(*) AS starts
        FROM fact_roster_week r
        JOIN dim_player p ON p.player_id = r.player_id
        JOIN dim_team   t ON t.team_id = r.team_id AND t.season = r.season
        JOIN dim_member m ON m.member_id = t.member_id
        WHERE r.started = 1 AND p.gsis_id IS NOT NULL AND p.gsis_id != ''
        GROUP BY r.season, p.gsis_id, m.member_id
    """
    best = defaultdict(list)
    for season, gid, member_id, starts in con.execute(q):
        best[(season, gid)].append((starts, member_id))
    for key, rows in best.items():
        rows.sort(reverse=True)
        starts = sum(s for s, _ in rows)
        out[key] = (starts, current.get(rows[0][1], ""))
    return out


def season_rows(con, season: int, rosters: dict, ctx: dict) -> list:
    q = """
        SELECT gsis_id,
               COUNT(*)                AS g,
               SUM(COALESCE(targets,0))       AS tgt,
               SUM(COALESCE(receptions,0))    AS rec,
               SUM(COALESCE(rec_yards,0))     AS recyd,
               SUM(COALESCE(rec_tds,0))       AS rectd,
               SUM(COALESCE(air_yards,0))     AS ay,
               AVG(target_share)              AS tgtsh,
               AVG(air_yards_share)           AS aysh,
               AVG(wopr)                      AS wopr,
               AVG(racr)                      AS racr,
               SUM(COALESCE(carries,0))       AS car,
               SUM(COALESCE(rush_yards,0))    AS ruyd,
               SUM(COALESCE(rush_tds,0))      AS rutd,
               SUM(COALESCE(attempts,0))      AS att,
               SUM(COALESCE(completions,0))   AS cmp,
               SUM(COALESCE(pass_yards,0))    AS payd,
               SUM(COALESCE(pass_tds,0))      AS patd,
               SUM(COALESCE(interceptions,0)) AS ints,
               SUM(COALESCE(epa,0))           AS epa
        FROM fact_nfl_week
        WHERE season = ?
        GROUP BY gsis_id
    """
    rows = []
    for r in con.execute(q, (season,)):
        (gid, g, tgt, rec, recyd, rectd, ay, tgtsh, aysh, wopr, racr,
         car, ruyd, rutd, att, cmp_, payd, patd, ints, epa) = r
        meta = rosters.get(gid)
        if not meta:
            continue
        name, team, pos = meta
        if pos not in SKILL:
            continue
        if not (tgt or car or att):
            continue

        fpts = (payd * PASS_YD + patd * PASS_TD + ints * INT
                + ruyd * RUSH_YD + rutd * RUSH_TD
                + recyd * REC_YD + rectd * REC_TD)
        starts, fr = ctx.get((season, gid), (0, ""))

        def n(v, nd=1):
            return None if v is None else round(float(v), nd)

        rows.append([
            gid, name, "RB" if pos in ("HB", "FB") else pos, team, g,
            n(tgt, 0), n(rec, 0), n(recyd, 0), n(rectd, 0), n(ay, 0),
            n(tgtsh, 4), n(aysh, 4), n(wopr, 4), n(racr, 3),
            n(car, 0), n(ruyd, 0), n(rutd, 0),
            n(att, 0), n(cmp_, 0), n(payd, 0), n(patd, 0), n(ints, 0),
            n(epa, 2), n(fpts, 1), n(fpts / g if g else 0, 2),
            starts, fr,
        ])
    rows.sort(key=lambda x: -(x[COLS.index("fpts")] or 0))
    return rows


def main() -> int:
    if not os.path.exists(DB):
        print("affl.db not found")
        return 1
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")

    seasons = [r[0] for r in con.execute(
        "SELECT DISTINCT season FROM fact_nfl_week ORDER BY season")]
    current = current_names(con)
    ctx = affl_context(con, current)
    pre, pre_cov = pre2018_context(con, current)
    ctx.update(pre)          # 2014-2017 only; never overwrites a 2018+ key

    franchises, total = set(), 0
    for s in seasons:
        rows = season_rows(con, s, load_rosters(s), ctx)
        total += len(rows)
        for r in rows:
            if r[COLS.index("fr")]:
                franchises.add(r[COLS.index("fr")])
        with open(os.path.join(OUT, f"season_{s}.json"), "w") as fh:
            json.dump(rows, fh, separators=(",", ":"))
        kb = os.path.getsize(os.path.join(OUT, f"season_{s}.json")) // 1024
        starters = sum(1 for r in rows if r[COLS.index("starts")])
        print(f"  {s}: {len(rows):4d} players  {starters:3d} AFFL-started  {kb:4d} KB")

    # How much of each season's AFFL lineup history is provable.
    # 2018+ comes from fact_roster_week and is complete. 2014-2017 is only as
    # good as the surviving capture, measured against fact_matchup.
    cov = {}
    for s in seasons:
        cov[str(s)] = 100.0 if s >= 2018 else pre_cov.get(s, 0.0)

    meta = {
        "cols": COLS,
        "seasons": seasons,
        "franchises": sorted(franchises),
        "positions": ["QB", "RB", "WR", "TE"],
        "scoring": "AFFL non-PPR — receptions score 0",
        "lineupCoverage": cov,
        "lineupNote": ("2018+ lineups are complete. ESPN does not retain "
                       "pre-2018 weekly lineups; 2014-2017 uses the surviving "
                       "capture and keeps only team-weeks whose starter points "
                       "reconcile exactly to the official score."),
    }
    with open(os.path.join(OUT, "meta.json"), "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))
    con.close()
    print(f"\n  {total} player-seasons across {len(seasons)} seasons -> site/savant/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
