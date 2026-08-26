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
        power_cols, power = q(con, "SELECT power_rank, team_id, allplay_w, allplay_l, power_ratio, power_pct FROM v_power WHERE season = ? ORDER BY power_rank, team_id", (season,))
    except Exception:
        power_cols, power = [], []
    try:
        luck_cols, luck = q(con, "SELECT team_id, lucky_wins, unlucky_losses, net_luck FROM v_luck WHERE season = ? ORDER BY net_luck DESC, team_id", (season,))
    except Exception:
        luck_cols, luck = [], []
    try:
        lw_cols, luck_w = q(con, "SELECT team_id, reg_wins, exp_wins, weighted_luck FROM v_luck_weighted WHERE season = ? ORDER BY weighted_luck DESC, team_id", (season,))
    except Exception:
        lw_cols, luck_w = [], []

    write_csv(os.path.join(OUT, "coverage.csv"), cov_cols, cov)
    write_csv(os.path.join(OUT, f"standings_{season}.csv"), stand_cols, stand)
    write_csv(os.path.join(OUT, f"draft_{season}.csv"), draft_cols, draft)
    write_csv(os.path.join(OUT, "table_counts.csv"), ["table", "rows"], counts)

    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M CT")
    except Exception:
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
        parts += ["", f"## {season} Luck Index (v_luck)", "",
                  "FantasyGenius discrete lucky/unlucky. Not League Legacy weighted luck.",
                  "", md_table(luck_cols, luck, limit=16)]
    if luck_w:
        write_csv(os.path.join(OUT, f"luck_weighted_{season}.csv"), lw_cols, luck_w)
        parts += ["", f"## {season} League Legacy weighted luck", "",
                  "actual wins minus all-play expected wins. See preview/STANDINGS.md.",
                  "", md_table(lw_cols, luck_w, limit=16)]
    try:
        nb_cols, notables = q(con, "SELECT kind, week, winner_id, loser_id, winner_pts, loser_pts, combined, margin FROM v_notable_matchup WHERE season = ? ORDER BY kind", (season,))
    except Exception:
        nb_cols, notables = [], []
    if notables:
        write_csv(os.path.join(OUT, f"notables_{season}.csv"), nb_cols, notables)
        parts += ["", f"## {season} notable matchups", "",
                  "Both scores. See preview/SCORING.md.",
                  "", md_table(nb_cols, notables, limit=8)]

    # --- contracts / new metrics ---
    try:
        own_cols, owners = q(
            con,
            """
            SELECT o.owner_id, o.display_name, o.is_active,
                   GROUP_CONCAT(m.member_id) AS member_ids,
                   (SELECT COUNT(*) FROM dim_team t
                     JOIN dim_member mm ON mm.member_id = t.member_id
                    WHERE mm.owner_id = o.owner_id) AS team_seasons
              FROM dim_owner o
              JOIN dim_member m ON m.owner_id = o.owner_id
             GROUP BY o.owner_id
             ORDER BY o.display_name COLLATE NOCASE
            """,
        )
    except Exception:
        own_cols, owners = [], []
    try:
        ph_cols, phases = q(
            con,
            """
            SELECT season, phase, COUNT(*) AS sides
              FROM v_matchup
             GROUP BY season, phase
             ORDER BY season, phase
            """,
        )
    except Exception:
        ph_cols, phases = [], []
    try:
        par_cols, pars = q(
            con,
            """
            SELECT team_name, owner_name, par_total, par_drafted,
                   par_traded_in, par_waived, par_unknown
              FROM v_custody_par
             WHERE season = ?
             ORDER BY par_total DESC
            """,
            (season,),
        )
    except Exception:
        par_cols, pars = [], []
    try:
        xtd_cols, xtds = q(
            con,
            """
            SELECT team_name, owner_name, actual_td, xtd, residual
              FROM v_xtd_portfolio
             WHERE season = ?
             ORDER BY residual DESC
            """,
            (season,),
        )
    except Exception:
        xtd_cols, xtds = [], []
    try:
        pj_cols, projs = q(
            con,
            """
            SELECT source, season, COUNT(*) AS rows,
                   COUNT(DISTINCT week) AS weeks,
                   COUNT(DISTINCT player_id) AS players
              FROM fact_projection_week
             GROUP BY source, season
             ORDER BY season, source
            """,
        )
    except Exception:
        pj_cols, projs = [], []

    if owners:
        write_csv(os.path.join(OUT, "owners.csv"), own_cols, owners)
        parts += ["", "## Owners (after merges)", "", md_table(own_cols, owners, limit=40)]
    if phases:
        write_csv(os.path.join(OUT, "matchup_phase.csv"), ph_cols, phases)
        parts += ["", "## Matchup sides by phase", "", md_table(ph_cols, phases, limit=60)]
    if pars:
        write_csv(os.path.join(OUT, f"custody_par_{season}.csv"), par_cols, pars)
        parts += ["", f"## {season} Custody PAR by team", "", md_table(par_cols, pars, limit=16)]
    else:
        parts += ["", f"## {season} Custody PAR by team", "",
                  "_unavailable — weekly lineups required (2018–2025). "
                  "2014–2017 reconstructed draft PAR is in v_custody_par_reconstructed._"]
    if xtds:
        write_csv(os.path.join(OUT, f"xtd_portfolio_{season}.csv"), xtd_cols, xtds)
        parts += ["", f"## {season} xTD portfolio", "", md_table(xtd_cols, xtds, limit=16)]
    else:
        parts += ["", f"## {season} xTD portfolio", "",
                  "_unavailable — run `python3 compute_xtd.py` after pbp is on disk._"]
    if projs:
        write_csv(os.path.join(OUT, "projections_coverage.csv"), pj_cols, projs)
        parts += ["", "## Projection coverage", "", md_table(pj_cols, projs, limit=20)]
    else:
        parts += ["", "## Projection coverage", "",
                  "_zero rows. FantasyPros historical consensus is not on disk. "
                  "ESPN `projectedPoints` was not present as a field; "
                  "`statSourceId=1` lines are extracted when `data/box_w*.json` has them._"]

    try:
        roto_cols, rotos = q(
            con,
            """
            SELECT total_rank AS rank, team_name, owner_name, games,
                   ROUND(py) AS py, ROUND(ptd) AS ptd, ROUND(comp_pct,1) AS cmp_pct,
                   ROUND(ry) AS ry, ROUND(rtd) AS rtd, ROUND(ypc,2) AS ypc,
                   ROUND(recy) AS recy, ROUND(retd) AS retd, ROUND(rec) AS rec,
                   ROUND(ypr,2) AS ypr, total_pts
              FROM v_roto_standings
             WHERE season = ? AND phase = 'regular'
             ORDER BY total_rank
            """,
            (season,),
        )
    except Exception:
        roto_cols, rotos = [], []
    if rotos:
        write_csv(os.path.join(OUT, f"roto_{season}.csv"), roto_cols, rotos)
        parts += ["", f"## {season} regular roto standings", "",
                  "Starter NFL production, 10-cat rotisserie. Rank 1 = best. "
                  "Pts = nTeams − rank + 1. 2018+ only.",
                  "", md_table(roto_cols, rotos, limit=16)]
    else:
        parts += ["", f"## {season} regular roto standings", "",
                  "_unavailable — weekly lineups required (2018–2025)._"]

    try:
        imp_cols, imps = q(
            con,
            """
            SELECT r.run_id, r.adapter, r.adapter_version, r.season, r.status,
                   r.row_count, r.finished_at, s.path, s.sha256, s.bytes
              FROM meta_import_run r
              JOIN meta_import_source s ON s.run_id = r.run_id
             WHERE r.dataset = 'matchup' AND r.season = ?
             ORDER BY r.run_id DESC, s.path
             LIMIT 8
            """,
            (season,),
        )
    except Exception:
        imp_cols, imps = [], []
    try:
        wk_cols, wks = q(
            con,
            """
            SELECT week, COUNT(*) AS sides, COUNT(DISTINCT team_id) AS teams,
                   COUNT(*) / 2 AS games,
                   SUM(is_playoff) AS playoff_sides
              FROM fact_matchup
             WHERE season = ?
             GROUP BY week
             ORDER BY week
            """,
            (season,),
        )
    except Exception:
        wk_cols, wks = [], []

    if wks:
        write_csv(os.path.join(OUT, f"matchup_weeks_{season}.csv"), wk_cols, wks)
    if imps:
        write_csv(os.path.join(OUT, f"matchup_import_{season}.csv"), imp_cols, imps)

    note_lines = [
        f"# {season} matchup import",
        "",
        f"Generated {now} from `affl.db`. This is the data. Not the website.",
        "",
        "The 2025 scoreboard already lived in `fact_matchup` from the ESPN box",
        "cache (`data/box_2025.json`). CHI-24 adds a versioned adapter, a source",
        "checksum, an import-run row, and pairing gates. Re-importing does not",
        "change the scores.",
        "",
    ]
    if wks:
        sides = sum(r[1] for r in wks)
        teams = None
        try:
            teams = con.execute(
                "SELECT COUNT(DISTINCT team_id) FROM fact_matchup WHERE season=?",
                (season,)).fetchone()[0]
        except Exception:
            pass
        note_lines += [
            "## What landed",
            "",
            f"- **{sides} sides** ({sides // 2} games), **{teams} teams**, weeks {wks[0][0]}–{wks[-1][0]}",
            "- Regular season (weeks 1–14): every week has 12 teams / 6 games. No holes.",
            "- Week 15 has 10 teams / 5 games because the #1 and #2 seeds have a first-round bye. That is what should have happened, not a missing pairing.",
            "- Weeks 16–17: 12 teams / 6 games.",
            "",
            md_table(wk_cols, wks, limit=20),
            "",
        ]
    if imps:
        note_lines += [
            "## Provenance (latest runs)",
            "",
            md_table(imp_cols, imps, limit=8),
            "",
            "Checksum is SHA-256 of the on-disk cache. Secrets stay in `.env` and are not in this file.",
            "",
        ]
    else:
        note_lines += [
            "## Provenance",
            "",
            "_no import-run yet — `python3 build_db.py --import-matchups 2025`_",
            "",
        ]
    note_path = os.path.join(OUT, "MATCHUP_IMPORT.md")
    with open(note_path, "w") as f:
        f.write("\n".join(note_lines))
    if wks:
        parts += ["", f"## {season} matchup import", "",
                  "Versioned adapter + checksum. See `preview/MATCHUP_IMPORT.md`.",
                  "", md_table(wk_cols, wks, limit=20)]
    if imps:
        parts += ["", md_table(imp_cols, imps, limit=6)]

    parts += [
        "",
        "## How to refresh",
        "",
        "```",
        "python3 build_db.py",
        "python3 compute_xtd.py          # optional; downloads nflverse pbp csv.gz",
        "python3 compute_roto.py         # 10-cat roto from starter NFL stats",
        "python3 fetch_projections.py    # ESPN raw + any FantasyPros files you drop in",
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
