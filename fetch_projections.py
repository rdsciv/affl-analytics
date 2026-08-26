#!/usr/bin/env python3
"""Projection ingest. Does not scrape a fake consensus.

Sources, in order of what this script will actually write:

1. ESPN raw weekly mMatchup payloads on disk (`data/box_w*.json`).
   ESPN does not use a `projectedPoints` field in these files. Projected
   stat lines live on `player.stats` where `statSourceId == 1`, and
   `appliedTotal` is already scored with AFFL rules. Stored as source='espn'.
2. FantasyPros weekly *standard* (non-PPR) stat-line CSVs, if you drop them
   at `data/projections/fantasypros_{season}_w{week}.csv` with columns
   at least: player / name, pass_yds, pass_td, int, rush_yds, rush_td,
   rec_yds, rec_td, rec. They are scored with that season's AFFL rules
   (bucketed yards through 2018, fractional after; 50-yard FG = 3).
   Historical FantasyPros consensus is a paid product. Do not scrape one.
   Missing stays missing.

    python3 fetch_projections.py
"""
import csv
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DB = os.path.join(HERE, "affl.db")
PROJ = os.path.join(DATA, "projections")

# ESPN statId -> our column
STAT_COL = {
    3: "pass_yds", 4: "pass_td", 20: "interceptions",
    24: "rush_yds", 25: "rush_td",
    42: "rec_yds", 43: "rec_td", 53: "receptions",
    72: "fumbles_lost",
}


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_espn_raw():
    """Pull statSourceId=1 lines from cached weekly box payloads."""
    rows = {}
    for name in sorted(os.listdir(DATA), key=lambda n: (len(n), n)):
        m = re.fullmatch(r"box_w(\d+)\.json", name)
        if not m:
            continue
        week = int(m.group(1))
        path = os.path.join(DATA, name)
        try:
            d = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        season = d.get("seasonId")
        if not season:
            continue
        for g in d.get("schedule") or []:
            if g.get("matchupPeriodId") not in (None, week):
                continue
            for side in ("home", "away"):
                s = g.get(side) or {}
                roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
                if not roster:
                    continue
                for e in roster.get("entries") or []:
                    ppe = e.get("playerPoolEntry") or {}
                    p = ppe.get("player") or {}
                    pid = p.get("id") or e.get("playerId")
                    if pid is None:
                        continue
                    proj = None
                    for st in p.get("stats") or []:
                        if st.get("statSourceId") == 1 and st.get("scoringPeriodId") in (week, None, 0):
                            proj = st
                            break
                    if proj is None:
                        for st in p.get("stats") or []:
                            if st.get("statSourceId") == 1:
                                proj = st
                                break
                    if proj is None:
                        continue
                    rec = {c: None for c in (
                        "pass_yds", "pass_td", "interceptions",
                        "rush_yds", "rush_td", "rec_yds", "rec_td",
                        "receptions", "fumbles_lost")}
                    stats = proj.get("stats") or {}
                    for sid, col in STAT_COL.items():
                        if str(sid) in stats:
                            rec[col] = fnum(stats[str(sid)])
                    affl = fnum(proj.get("appliedTotal"))
                    key = ("espn", int(season), week, int(pid))
                    rows[key] = (
                        "espn", int(season), week, int(pid),
                        rec["pass_yds"], rec["pass_td"], rec["interceptions"],
                        rec["rush_yds"], rec["rush_td"],
                        rec["rec_yds"], rec["rec_td"], rec["receptions"],
                        rec["fumbles_lost"], affl,
                    )
    return list(rows.values())


def score_affl(con, season, rec):
    """Score a FantasyPros-style stat line with that season's AFFL rules."""
    mode = con.execute(
        "SELECT yardage_mode FROM dim_season WHERE season=?", (season,)
    ).fetchone()
    if not mode:
        return None
    rules = {sid: pts for sid, pts in con.execute(
        "SELECT stat_id, points FROM dim_scoring WHERE season=?", (season,))}
    py = rec.get("pass_yds") or 0
    ry = rec.get("rush_yds") or 0
    cy = rec.get("rec_yds") or 0
    if mode[0] == "BUCKET":
        yards = int(py // 25) + int(ry // 10) + int(cy // 10)
    else:
        yards = py * rules.get(3, 0) + ry * rules.get(24, 0) + cy * rules.get(42, 0)
    return (yards
            + (rec.get("pass_td") or 0) * rules.get(4, 0)
            + (rec.get("interceptions") or 0) * rules.get(20, 0)
            + (rec.get("rush_td") or 0) * rules.get(25, 0)
            + (rec.get("rec_td") or 0) * rules.get(43, 0)
            + (rec.get("receptions") or 0) * rules.get(53, 0)
            + (rec.get("fumbles_lost") or 0) * rules.get(72, 0))


def load_fantasypros(con):
    """Only files the operator placed under data/projections/."""
    if not os.path.isdir(PROJ):
        return []
    # map names -> espn player_id for the season (unique name only)
    out = []
    for name in sorted(os.listdir(PROJ)):
        m = re.fullmatch(r"fantasypros_(\d{4})_w(\d+)\.csv", name)
        if not m:
            continue
        season, week = int(m.group(1)), int(m.group(2))
        by_name = {}
        for pid, pname in con.execute(
            "SELECT player_id, name FROM dim_player WHERE name IS NOT NULL"
        ):
            key = pname.strip().lower()
            by_name.setdefault(key, []).append(pid)
        with open(os.path.join(PROJ, name), newline="") as f:
            for row in csv.DictReader(f):
                pname = (row.get("player") or row.get("name") or "").strip()
                if not pname:
                    continue
                cands = by_name.get(pname.lower(), [])
                if len(cands) != 1:
                    continue
                rec = {
                    "pass_yds": fnum(row.get("pass_yds") or row.get("passYds")),
                    "pass_td": fnum(row.get("pass_td") or row.get("passTD")),
                    "interceptions": fnum(row.get("int") or row.get("interceptions")),
                    "rush_yds": fnum(row.get("rush_yds") or row.get("rushYds")),
                    "rush_td": fnum(row.get("rush_td") or row.get("rushTD")),
                    "rec_yds": fnum(row.get("rec_yds") or row.get("recYds")),
                    "rec_td": fnum(row.get("rec_td") or row.get("recTD")),
                    "receptions": fnum(row.get("rec") or row.get("receptions")),
                    "fumbles_lost": fnum(row.get("fl") or row.get("fumbles_lost")),
                }
                affl = score_affl(con, season, rec)
                out.append((
                    "fantasypros", season, week, cands[0],
                    rec["pass_yds"], rec["pass_td"], rec["interceptions"],
                    rec["rush_yds"], rec["rush_td"],
                    rec["rec_yds"], rec["rec_td"], rec["receptions"],
                    rec["fumbles_lost"], affl,
                ))
    return out


def load_into(con):
    espn = extract_espn_raw()
    fp = load_fantasypros(con)
    rows = espn + fp
    con.execute("DELETE FROM fact_projection_week")
    if rows:
        con.executemany(
            """INSERT OR REPLACE INTO fact_projection_week
               (source, season, week, player_id,
                pass_yds, pass_td, interceptions,
                rush_yds, rush_td, rec_yds, rec_td, receptions,
                fumbles_lost, affl_points)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
    return len(espn), len(fp)


def main():
    if not os.path.exists(DB):
        sys.exit(f"missing {DB} — run python3 build_db.py first")
    con = sqlite3.connect(DB)
    # table may not exist if schema has not been applied
    con.executescript(open(os.path.join(HERE, "schema.sql")).read())
    n_espn, n_fp = load_into(con)
    con.commit()
    print(f"projections: espn={n_espn}  fantasypros={n_fp}")
    if n_espn == 0 and n_fp == 0:
        print("no projection files found. ESPN box_w*.json had no usable "
              "statSourceId=1 lines, and data/projections/ is empty. "
              "gap stays unavailable.")


if __name__ == "__main__":
    main()
