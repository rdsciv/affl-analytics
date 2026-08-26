#!/usr/bin/env python3
"""CHI-25 / AFFL-006: 2025 normalized scoring and notable matchups.

Recomputes from fact_matchup regular-season sides (real warehouse grain):

  1. Weekly min/avg/max match v_score_week (heatmap / trend grain).
  2. Each team-week vs_avg = points - week_avg (v_score_normalized).
  3. Score distribution buckets sum to 168 regular sides.
  4. The six notables (min win, max loss, slugfest, pillow fight,
     blowout, nail biter) match an independent recompute. Both teams'
     scores are present. Ties for a kind are allowed; the view must
     contain the recomputed game.
"""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
PREVIEW = ROOT / "preview"
SEASON = 2025
fails = []
KINDS = ("min_win", "max_loss", "slugfest", "pillow_fight", "blowout", "nail_biter")


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
        cells = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            else:
                cells.append(str(v).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_sides(con):
    return list(con.execute("""
        SELECT week, team_id, opponent_id, points, opponent_points, result, is_home
          FROM fact_matchup
         WHERE season=? AND is_playoff=0
         ORDER BY week, team_id
    """, (SEASON,)))


def test_score_week(con, sides):
    by_wk = defaultdict(list)
    for s in sides:
        by_wk[s["week"]].append(s["points"])
    view = {r["week"]: r for r in con.execute(
        "SELECT * FROM v_score_week WHERE season=?", (SEASON,))}
    if set(view) != set(by_wk):
        fail(f"v_score_week weeks {sorted(view)} != {sorted(by_wk)}")
        return []
    rows = []
    for wk in sorted(by_wk):
        pts = by_wk[wk]
        mn, av, mx = min(pts), sum(pts) / len(pts), max(pts)
        v = view[wk]
        if v["n"] != len(pts):
            fail(f"week {wk} n {v['n']} != {len(pts)}")
        if abs(v["min_pts"] - mn) > 1e-9 or abs(v["max_pts"] - mx) > 1e-9:
            fail(f"week {wk} min/max {v['min_pts']}/{v['max_pts']} != {mn}/{mx}")
        if abs(v["avg_pts"] - av) > 1e-9:
            fail(f"week {wk} avg {v['avg_pts']} != {av}")
        rows.append((wk, len(pts), mn, av, mx))
    print(f"v_score_week matches weekly sides: {len(rows)} weeks")
    return rows


def test_normalized(con, sides, week_rows):
    avg = {wk: av for wk, _n, _mn, av, _mx in week_rows}
    view = list(con.execute(
        "SELECT * FROM v_score_normalized WHERE season=?", (SEASON,)))
    if len(view) != len(sides):
        fail(f"v_score_normalized {len(view)} != sides {len(sides)}")
        return
    by_key = {(r["week"], r["team_id"]): r for r in view}
    for s in sides:
        v = by_key.get((s["week"], s["team_id"]))
        if v is None:
            fail(f"missing normalized {s['week']}/{s['team_id']}")
            continue
        expect = s["points"] - avg[s["week"]]
        if abs(v["vs_avg"] - expect) > 1e-9:
            fail(f"week {s['week']} team {s['team_id']} vs_avg {v['vs_avg']} != {expect}")
        if abs(v["points"] - s["points"]) > 1e-9:
            fail(f"normalized points drifted for {s['week']}/{s['team_id']}")
    print(f"v_score_normalized vs_avg = points - week_avg: {len(sides)} sides")


def test_distribution(con, sides):
    buckets = defaultdict(int)
    for s in sides:
        buckets[int(s["points"] // 10) * 10] += 1
    view = {r["bucket"]: r["n"] for r in con.execute(
        "SELECT bucket, n FROM v_score_distribution WHERE season=?", (SEASON,))}
    if view != dict(buckets):
        fail(f"distribution {view} != {dict(buckets)}")
    total = sum(view.values())
    if total != 168:
        fail(f"distribution n={total} != 168 regular sides")
    else:
        print(f"v_score_distribution: {len(view)} buckets, {total} sides")
    return sorted(view.items())


def test_notables(con, sides, names):
    games = []
    for s in sides:
        if not s["is_home"]:
            continue
        hp, ap = s["points"], s["opponent_points"]
        w_id, l_id = (s["team_id"], s["opponent_id"]) if hp >= ap else (s["opponent_id"], s["team_id"])
        w_pts, l_pts = (hp, ap) if hp >= ap else (ap, hp)
        games.append({
            "week": s["week"], "winner_id": w_id, "loser_id": l_id,
            "winner_pts": w_pts, "loser_pts": l_pts,
            "combined": hp + ap, "margin": abs(hp - ap),
        })
    if len(games) != 84:
        fail(f"regular games {len(games)} != 84")
    expect = {
        "min_win": min(games, key=lambda g: g["winner_pts"]),
        "max_loss": max(games, key=lambda g: g["loser_pts"]),
        "slugfest": max(games, key=lambda g: g["combined"]),
        "pillow_fight": min(games, key=lambda g: g["combined"]),
        "blowout": max(games, key=lambda g: g["margin"]),
        "nail_biter": min((g for g in games if g["margin"] > 0), key=lambda g: g["margin"]),
    }
    view = list(con.execute(
        "SELECT * FROM v_notable_matchup WHERE season=? ORDER BY kind", (SEASON,)))
    have = {r["kind"] for r in view}
    if have != set(KINDS):
        fail(f"notable kinds {have} != {set(KINDS)}")
    rows = []
    for kind, exp in expect.items():
        matches = [r for r in view if r["kind"] == kind
                   and r["week"] == exp["week"]
                   and r["winner_id"] == exp["winner_id"]
                   and r["loser_id"] == exp["loser_id"]
                   and abs(r["winner_pts"] - exp["winner_pts"]) < 1e-9
                   and abs(r["loser_pts"] - exp["loser_pts"]) < 1e-9]
        if not matches:
            fail(f"{kind} missing expected W{exp['week']} "
                 f"{exp['winner_id']} {exp['winner_pts']} / {exp['loser_id']} {exp['loser_pts']}")
        r = matches[0]
        if r["winner_pts"] is None or r["loser_pts"] is None:
            fail(f"{kind} missing a side score")
        rows.append((kind, r["week"], names.get(r["winner_id"], r["winner_id"]),
                     r["winner_pts"], names.get(r["loser_id"], r["loser_id"]),
                     r["loser_pts"], r["combined"], r["margin"]))
    print(f"v_notable_matchup: {len(KINDS)} kinds, both scores present")
    return rows, expect


def write_preview(week_rows, dist, notable_rows, names, expect):
    PREVIEW.mkdir(exist_ok=True)
    lines = [
        f"# {SEASON} scoring and notable matchups",
        "",
        "CHI-25 / AFFL-006. From `fact_matchup` regular-season weeks (box grain).",
        "This is the data. Not the website.",
        "",
        "## Weekly distribution (heatmap / trend grain)",
        "",
        md_table(["week", "n", "min", "avg", "max"], week_rows),
        "",
        "## Score histogram (10-pt buckets)",
        "",
        md_table(["bucket", "n"], dist),
        "",
        "## Notable matchups (both scores)",
        "",
        "Min win = lowest winning score. Max loss = highest losing score. "
        "Slugfest = highest combined. Pillow fight = lowest combined. "
        "Blowout = largest margin. Nail biter = smallest margin > 0.",
        "",
        md_table(["kind", "week", "winner", "w_pts", "loser", "l_pts", "combined", "margin"],
                 notable_rows),
        "",
        "## How to refresh",
        "",
        "```",
        "python3 evals/test_scoring_notables_2025.py",
        "```",
        "",
    ]
    path = PREVIEW / "SCORING.md"
    path.write_text("\n".join(lines))
    print(path)


def main():
    con = connect()
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=?", (SEASON,))}
    sides = load_sides(con)
    if len(sides) != 168:
        fail(f"regular sides {len(sides)} != 168")
    week_rows = test_score_week(con, sides)
    if week_rows:
        test_normalized(con, sides, week_rows)
    dist = test_distribution(con, sides)
    notable_rows, expect = test_notables(con, sides, names)
    write_preview(week_rows, dist, notable_rows, names, expect)
    con.close()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-25: 2025 scoring views and notables recomputed from matchup grain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
