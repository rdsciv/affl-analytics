#!/usr/bin/env python3
"""Dump the warehouse into readable files. No website required.

    python3 inspect_data.py
    python3 inspect_data.py --season 2025

Writes preview/SUMMARY.md plus a few CSVs. Safe to re-run.
"""
import argparse
import csv
import os
import sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "affl.db")
OUT = os.path.join(HERE, "preview")


def q(con, sql, args=()):
    cur = con.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def md_table(cols, rows, limit=30):
    if not rows:
        return "_no rows_"
    shown = rows[:limit]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in shown:
        cells = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            else:
                cells.append(str(v).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) > limit:
        lines.append(f"| … | {len(rows) - limit} more rows |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    args = ap.parse_args()
    season = args.season

    if not os.path.exists(DB):
        raise SystemExit(f"missing {DB} — run python3 build_db.py first")

    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    tables = con.execute(
        "SELECT name, (SELECT COUNT(*) FROM sqlite_master sm WHERE 0) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1"
    ).fetchall()
    counts = []
    for (name, _) in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        counts.append((name, n))

    cov_cols, cov = q(
        con,
        """
        SELECT s.season, s.team_count, s.reg_weeks, s.auction_draft, s.has_rosters, s.has_tx,
               s.yardage_mode,
               (SELECT COUNT(*) FROM fact_roster_week r WHERE r.season=s.season) AS roster_weeks,
               (SELECT COUNT(*) FROM fact_matchup m WHERE m.season=s.season) AS matchups,
               (SELECT COUNT(*) FROM fact_draft_pick d WHERE d.season=s.season) AS draft_picks,
               (SELECT COUNT(*) FROM fact_transaction t WHERE t.season=s.season) AS transactions
        FROM dim_season s
        ORDER BY s.season
        """,
    )

    stand_cols, stand = q(
        con,
        """
        SELECT t.final_rank, t.name, m.display_name, t.wins, t.losses, t.ties,
               t.points_for, t.points_against, t.playoff_seed
        FROM dim_team t
        LEFT JOIN dim_member m ON m.member_id = t.member_id
        WHERE t.season = ?
        ORDER BY COALESCE(t.final_rank, 99), t.points_for DESC
        """,
        (season,),
    )

    draft_cols, draft = q(
        con,
        """
        SELECT d.overall, t.name AS team, p.name AS player, p.position, d.bid
        FROM fact_draft_pick d
        JOIN dim_team t ON t.season=d.season AND t.team_id=d.team_id
        JOIN dim_player p ON p.player_id=d.player_id
        WHERE d.season = ?
        ORDER BY d.overall
        """,
        (season,),
    )

    trade_cols, trades = q(
        con,
        """
        SELECT tr.week, pf.name AS from_team, pt.name AS to_team, p.name AS player
        FROM fact_trade_item i
        JOIN fact_trade tr ON tr.trade_id = i.trade_id
        JOIN dim_team pf ON pf.season=tr.season AND pf.team_id=i.from_team_id
        JOIN dim_team pt ON pt.season=tr.season AND pt.team_id=i.to_team_id
        JOIN dim_player p ON p.player_id=i.player_id
        WHERE tr.season = ?
        ORDER BY tr.week, tr.trade_id
        """,
        (season,),
    )
    try:
        power_cols, power = q(con, "SELECT * FROM v_power WHERE season = ? ORDER BY 1", (season,))
    except Exception:
        power_cols, power = [], []
    try:
        luck_cols, luck = q(con, "SELECT * FROM v_luck WHERE season = ? ORDER BY 1", (season,))
    except Exception:
        luck_cols, luck = [], []

    write_csv(os.path.join(OUT, "coverage.csv"), cov_cols, cov)
    write_csv(os.path.join(OUT, f"standings_{season}.csv"), stand_cols, stand)
    write_csv(os.path.join(OUT, f"draft_{season}.csv"), draft_cols, draft)
    write_csv(os.path.join(OUT, "table_counts.csv"), ["table", "rows"], counts)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"# AFFL warehouse preview",
        "",
        f"Generated {now} from `affl.db`. Season focus: **{season}**.",
        "This is the data. Not the website.",
        "",
        "## Table counts",
        "",
        md_table(["table", "rows"], counts, limit=80),
        "",
        "## Coverage by season",
        "",
        md_table(cov_cols, cov, limit=20),
        "",
        f"## {season} standings",
        "",
        md_table(stand_cols, stand, limit=16),
        "",
        f"## {season} draft (first 30)",
        "",
        md_table(draft_cols, draft, limit=30),
    ]
    if trade_cols:
        parts += ["", f"## {season} trades (sample)", "", md_table(trade_cols, trades, limit=20)]
    if power:
        write_csv(os.path.join(OUT, f"power_{season}.csv"), power_cols, power)
        parts += ["", f"## {season} power", "", md_table(power_cols, power, limit=16)]
    if luck:
        write_csv(os.path.join(OUT, f"luck_{season}.csv"), luck_cols, luck)
        parts += ["", f"## {season} luck", "", md_table(luck_cols, luck, limit=16)]

    try:
        radar_cols, radar = q(
            con,
            """
            SELECT team_id, ROUND(pass_yards,0), ROUND(pass_tds,0),
                   ROUND(rush_yards,0), ROUND(rec_yards,0), ROUND(receptions,0),
                   ROUND(pbp_epa,1), ROUND(xtd,1)
              FROM v_skill_radar WHERE season = ? ORDER BY pbp_epa DESC
            """,
            (season,),
        )
    except Exception:
        radar_cols, radar = [], []
    if radar:
        write_csv(os.path.join(OUT, f"skill_radar_{season}.csv"), radar_cols, radar)
        parts += ["", f"## {season} skill radar (started skill players, non-PPR)",
                  "", md_table(radar_cols, radar, limit=16)]

    pbp_n = ngs_n = xfp_n = 0
    try:
        pbp_n = con.execute("SELECT COUNT(*) FROM fact_pbp_agg").fetchone()[0]
        ngs_n = con.execute("SELECT COUNT(*) FROM fact_ngs").fetchone()[0]
        xfp_n = con.execute("SELECT COUNT(*) FROM fact_player_xfp").fetchone()[0]
    except Exception:
        pass
    try:
        xfp_cols, xfp = q(
            con,
            """
            SELECT p.name, p.position, x.st_games, ROUND(x.st_fp,1),
                   ROUND(x.st_xfp,1), ROUND(x.st_fpoe,1), ROUND(x.xtd,1)
              FROM fact_player_xfp x
              JOIN dim_player p ON p.player_id = x.player_id
             WHERE x.season = ? AND x.st_games > 0
             ORDER BY x.st_fpoe DESC
            """,
            (season,),
        )
    except Exception:
        xfp_cols, xfp = [], []
    if xfp:
        write_csv(os.path.join(OUT, f"xfp_{season}.csv"), xfp_cols, xfp)
        parts += ["", f"## {season} AFFL XFP / FPOE (started skill players, non-PPR)",
                  "", md_table(xfp_cols, xfp, limit=16)]
    parts += [
        "",
        "## Savant / nflverse PBP",
        "",
        f"fact_pbp_agg rows: **{pbp_n:,}**. fact_ngs rows: **{ngs_n:,}**. "
        f"fact_player_xfp rows: **{xfp_n:,}**.",
        "",
        "Landed from nflverse release files (not a live Savant scrape):",
        "",
        "- play-by-play 2013–2025 → `fact_pbp_agg` (EPA, CPOE, air yards, success, xTD)",
        "- nextgen_stats 2016+ → `fact_ngs` (separation, cushion, CPOE, RYoe)",
        "- AFFL FP / XFP / FPOE from `dim_scoring` + box + PBP. Receptions are volume, not PPR",
        "- Skill Radar on the site uses started AFFL skill players",
        "",
        "Savant `/fantasy` std is a **comparison UI**, not the AFFL scoring source. "
        "Do not import its FP / XFP / PPR / half-PPR columns. AFFL: rec = 0, "
        "yardage bucketed through 2018, 50-yard FG = 3.",
        "",
        "Still needs a browser scrape of nflsavant.com (Cloudflare) if we want the UI pages themselves:",
        "",
        "- Combine RAS (0–10)",
        "- Explore query-builder leaderboards",
        "- Compare-page snapshots",
        "",
        "PBP sources (same grain; we fetch nflverse gzip, do not commit giant CSVs):",
        "",
        "- nflverse: `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.csv.gz`",
        "- Savant R2 (alternate, ~112–115 MB): `https://pub-e9a6e73e336047fba26374ae44334139.r2.dev/pbp-{year}.csv`",
        "- `https://nflsavant.com/pbp_data.php?year={year}` 301s to the homepage — not a file",
    ]

    parts += [
        "",
        "## How to refresh",
        "",
        "```",
        "python3 build_db.py --check",
        "python3 inspect_data.py --season 2025",
        "```",
        "",
        "Open `preview/SUMMARY.md` or the CSVs. Do not wait on the site.",
        "",
    ]
    summary = os.path.join(OUT, "SUMMARY.md")
    with open(summary, "w") as f:
        f.write("\n".join(parts))
    print(summary)
    for name, n in counts:
        print(f"{n:8d}  {name}")


if __name__ == "__main__":
    main()
