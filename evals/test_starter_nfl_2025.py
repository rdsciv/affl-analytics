#!/usr/bin/env python3
"""CHI-27 / AFFL-007: 2025 started-player NFL stat lines.

fact_nfl_week is already loaded. This proves the starter join:

  1. v_starter_nfl_week row count = started roster weeks.
  2. Skill starters (QB/RB/WR/TE) all have gsis_id.
  3. A scored skill starter (affl_points != 0) without an nflverse row FAILS
     (that would block Roto). Zero-point DNPs are surfaced, not invented.
  4. DST has no gsis — unavailable, not zero-filled.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
PREVIEW = ROOT / "preview"
SEASON = 2025
SKILL = ("QB", "RB", "WR", "TE")
fails = []


def fail(msg):
    fails.append(msg)


def connect():
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def md_table(cols, rows):
    if not rows:
        return "_no rows_"
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        cells = ["" if v is None else str(v).replace("|", "/") for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    con = connect()
    started = con.execute(
        "SELECT COUNT(*) FROM fact_roster_week WHERE season=? AND started=1",
        (SEASON,)).fetchone()[0]
    view_n = con.execute(
        "SELECT COUNT(*) FROM v_starter_nfl_week WHERE season=?",
        (SEASON,)).fetchone()[0]
    if view_n != started:
        fail(f"v_starter_nfl_week {view_n} != started roster weeks {started}")
    else:
        print(f"v_starter_nfl_week = {view_n} started rows")

    no_gsis = list(con.execute("""
        SELECT week, team_id, name, position, affl_points
          FROM v_starter_nfl_week
         WHERE season=? AND position IN ('QB','RB','WR','TE') AND gsis_id IS NULL
    """, (SEASON,)))
    if no_gsis:
        fail(f"skill starters missing gsis_id: {len(no_gsis)}")
    else:
        print("all 2025 skill starters have gsis_id")

    scored_miss = list(con.execute("""
        SELECT week, team_id, name, position, affl_points, gsis_id
          FROM v_starter_nfl_week
         WHERE season=? AND position IN ('QB','RB','WR','TE')
           AND has_nfl=0 AND affl_points != 0
         ORDER BY week, name
    """, (SEASON,)))
    if scored_miss:
        fail(f"scored skill starter missing nflverse ({len(scored_miss)}) — blocks Roto")
        for r in scored_miss:
            print(" scored miss", dict(r))
    else:
        print("no scored skill starter is missing nflverse")

    dnp = list(con.execute("""
        SELECT week, team_id, name, position, affl_points, gsis_id
          FROM v_starter_nfl_week
         WHERE season=? AND position IN ('QB','RB','WR','TE')
           AND has_nfl=0 AND affl_points = 0
         ORDER BY week, name
    """, (SEASON,)))
    print(f"zero-point skill DNPs without nflverse: {len(dnp)} (surfaced, not filled)")

    dst = con.execute("""
        SELECT COUNT(*) n,
               SUM(CASE WHEN gsis_id IS NOT NULL THEN 1 ELSE 0 END) gsis,
               SUM(has_nfl) nfl
          FROM v_starter_nfl_week WHERE season=? AND position='DST'
    """, (SEASON,)).fetchone()
    if dst["gsis"] or dst["nfl"]:
        fail("DST should have no gsis/nflverse join")
    else:
        print(f"DST {dst['n']} starts: no gsis (unavailable, not zero-filled)")

    by_pos = list(con.execute("""
        SELECT position, COUNT(*) n, SUM(has_nfl) nfl,
               ROUND(100.0*SUM(has_nfl)/COUNT(*),1) pct
          FROM v_starter_nfl_week WHERE season=?
         GROUP BY position ORDER BY position
    """, (SEASON,)))
    print("by position:")
    for r in by_pos:
        print(" ", dict(r))

    PREVIEW.mkdir(exist_ok=True)
    lines = [
        f"# {SEASON} started-player NFL lines",
        "",
        "CHI-27 / AFFL-007. Join is `fact_roster_week` (started) → `dim_player.gsis_id` → `fact_nfl_week`.",
        "Missing stays missing. DST has no nflverse id.",
        "",
        f"- Started rows: **{started}**",
        f"- Skill starters missing gsis: **{len(no_gsis)}**",
        f"- Scored skill missing nflverse: **{len(scored_miss)}** (Roto gate)",
        f"- Zero-point skill DNPs missing nflverse: **{len(dnp)}** (not invented)",
        f"- DST starts: **{dst['n']}**, gsis=0",
        "",
        "## Coverage by position",
        "",
        md_table(["position", "n", "nfl", "pct"],
                 [(r["position"], r["n"], r["nfl"], r["pct"]) for r in by_pos]),
        "",
        "## Zero-point DNPs (no nflverse row)",
        "",
        md_table(["week", "team_id", "player", "pos", "affl_pts", "gsis"],
                 [(r["week"], r["team_id"], r["name"], r["position"],
                   r["affl_points"], r["gsis_id"]) for r in dnp]),
        "",
        "## How to refresh",
        "",
        "```",
        "python3 evals/test_starter_nfl_2025.py",
        "```",
        "",
    ]
    path = PREVIEW / "STARTERS.md"
    path.write_text("\n".join(lines))
    print(path)
    con.close()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-27: 2025 started-player NFL lines joined; missing DNPs surfaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
