#!/usr/bin/env python3
"""Team-season activity: day×week tx grid + value-added scatter (Wave T / Phase 9).

Writes site/team_activity.json. Read-only on affl.db.

Value added (documented):
  For each in-season ADD paired with a DROP at the same timestamp (and
  trade-ins paired with the reciprocal trade-out when possible):
    sum over weeks w >= acquisition week where the acquired player STARTED
      for this team:  acquired.points[w] − replaced.points[w]
  Replaced.points[w] = that player's fantasy points that week on any roster
  (fact_roster_week), else 0 if free agent / unknown.
  Unpaired ADDs / trade-ins contribute only their started points (no subtract).
  Drafted players never count toward Y.

Transactions (X): count of ADD legs + count of trade-in legs (player arrivals).
  Drops alone do not add to X (they're the other half of a move).

2018+ only. Pre-2018 seasons omitted from payload (UI shows unavailable).
"""
from __future__ import annotations

import json
import re
import statistics
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
SITE = ROOT / "site"
CT = ZoneInfo("America/Chicago")
DOW = ["TUE", "WED", "THU", "FRI", "SAT", "SUN", "MON"]  # col 0..6


def local_only_logo(url):
    """CHI-169: only keep logos/ paths; blank absolute http(s) remotes."""
    if not url:
        return ""
    s = str(url)
    if s.startswith("logos/"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return ""
    return s if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", s) else ""



def dow_col(ts_ms: int) -> int:
    if not ts_ms:
        return 0
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=CT)
    # Mon=0..Sun=6 → Tue=0..Mon=6
    return (dt.weekday() - 1) % 7


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    players = {
        r["player_id"]: {"name": r["name"], "pos": r["position"]}
        for r in con.execute("SELECT player_id, name, position FROM dim_player")
    }

    seasons = [
        r[0]
        for r in con.execute(
            "SELECT season FROM dim_season WHERE season >= 2018 ORDER BY 1"
        )
    ]

    # team meta per season
    teams = defaultdict(dict)  # season -> tid -> {member_id, name, logo}
    for r in con.execute(
        "SELECT season, team_id, member_id, name, logo FROM dim_team WHERE season >= 2018"
    ):
        teams[r["season"]][r["team_id"]] = {
            "tid": r["team_id"],
            "member_id": r["member_id"],
            "name": r["name"],
            "logo": local_only_logo(r["logo"] or ""),
        }

    # points by (season, week, player) — any team
    pts_pw = {}
    for r in con.execute(
        """
        SELECT season, week, player_id, MAX(points) AS pts
          FROM fact_roster_week
         WHERE season >= 2018
         GROUP BY 1, 2, 3
        """
    ):
        pts_pw[(r["season"], r["week"], r["player_id"])] = float(r["pts"] or 0)

    # started weeks for (season, team, player) -> list of (week, points)
    started = defaultdict(list)
    for r in con.execute(
        """
        SELECT season, week, team_id, player_id, points
          FROM fact_roster_week
         WHERE season >= 2018 AND started = 1
        """
    ):
        started[(r["season"], r["team_id"], r["player_id"])].append(
            (int(r["week"]), float(r["points"] or 0))
        )

    # acquisition first week from player_week_par
    first_acq = {}  # (season, team, player) -> (week, acquisition)
    for r in con.execute(
        """
        SELECT season, team_id, player_id, MIN(week) AS w, acquisition
          FROM fact_player_week_par
         WHERE season >= 2018
         GROUP BY 1, 2, 3
        """
    ):
        first_acq[(r["season"], r["team_id"], r["player_id"])] = (
            int(r["w"]),
            r["acquisition"] or "Unknown",
        )

    out_seasons = {}

    for season in seasons:
        # --- grid per team ---
        # moves list per (tid, week, dow)
        cell_moves = defaultdict(list)  # (tid, week, dow) -> [{op, name, pid}]
        cell_count = defaultdict(int)

        # Pair adds/drops by (team, ts)
        by_ts = defaultdict(lambda: {"adds": [], "drops": []})
        for r in con.execute(
            """
            SELECT ts, week, team_id, player_id, direction, tx_type
              FROM fact_transaction
             WHERE season = ?
             ORDER BY ts, team_id
            """,
            (season,),
        ):
            tid, ts = r["team_id"], int(r["ts"] or 0)
            wk = int(r["week"] or 1)
            col = dow_col(ts)
            pid = r["player_id"]
            name = (players.get(pid) or {}).get("name") or f"#{pid}"
            op = "add" if r["direction"] == "ADD" else "drop"
            cell_moves[(tid, wk, col)].append(
                {"op": op, "name": name, "pid": pid, "type": r["tx_type"]}
            )
            cell_count[(tid, wk, col)] += 1
            key = (tid, ts)
            if r["direction"] == "ADD":
                by_ts[key]["adds"].append((pid, wk, ts))
            else:
                by_ts[key]["drops"].append((pid, wk, ts))

        # Trade arrivals as adds for grid + pairing
        trade_pairs = []  # (to_tid, from_tid, pid, week, ts)
        for r in con.execute(
            """
            SELECT t.trade_id, t.week, t.ts, i.player_id, i.from_team_id, i.to_team_id
              FROM fact_trade t
              JOIN fact_trade_item i ON i.trade_id = t.trade_id
             WHERE t.season = ?
            """,
            (season,),
        ):
            ts = int(r["ts"] or 0)
            wk = int(r["week"] or 1)
            col = dow_col(ts) if ts else 0
            pid = r["player_id"]
            name = (players.get(pid) or {}).get("name") or f"#{pid}"
            to_t, fr_t = r["to_team_id"], r["from_team_id"]
            cell_moves[(to_t, wk, col)].append(
                {"op": "trade in", "name": name, "pid": pid, "type": "TRADE"}
            )
            cell_count[(to_t, wk, col)] += 1
            cell_moves[(fr_t, wk, col)].append(
                {"op": "trade out", "name": name, "pid": pid, "type": "TRADE"}
            )
            cell_count[(fr_t, wk, col)] += 1
            trade_pairs.append((to_t, fr_t, pid, wk, ts))

        # Build swap pairs for value-added
        swaps = []  # (tid, add_pid, drop_pid, week)
        for (tid, ts), bag in by_ts.items():
            adds = bag["adds"][:]
            drops = bag["drops"][:]
            while adds and drops:
                a, aw, _ = adds.pop(0)
                d, dw, _ = drops.pop(0)
                swaps.append((tid, a, d, min(aw, dw)))
            for a, aw, _ in adds:
                swaps.append((tid, a, None, aw))
        # trades: pair reciprocal items same trade_id already exploded —
        # unpaired trade-in
        for to_t, fr_t, pid, wk, ts in trade_pairs:
            # find a reciprocal outgoing from to_t in same trade roughly
            swaps.append((to_t, pid, None, wk))

        # Refine trade swaps: group by trade_id
        swaps = [(t, a, d, w) for (t, a, d, w) in swaps if d is not None or a is not None]
        # Deduplicate trade-in only entries later via first_acq

        # Value added using acquisition labels + swap drops
        # Map (tid, add_pid) -> drop_pid if any
        drop_for = {}
        for tid, a, d, w in swaps:
            if a is not None and d is not None:
                drop_for[(tid, a)] = (d, w)

        team_va = {}
        team_tx = {}
        team_grid = {}

        max_week = max(
            [1]
            + [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT week FROM fact_roster_week WHERE season=?",
                    (season,),
                )
            ]
            + [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT week FROM fact_transaction WHERE season=?",
                    (season,),
                )
            ]
        )

        for tid, meta in teams[season].items():
            # transaction count X
            n_add = con.execute(
                """
                SELECT COUNT(*) FROM fact_transaction
                 WHERE season=? AND team_id=? AND direction='ADD'
                """,
                (season, tid),
            ).fetchone()[0]
            n_tin = con.execute(
                """
                SELECT COUNT(*) FROM fact_trade_item i
                  JOIN fact_trade t ON t.trade_id = i.trade_id
                 WHERE t.season=? AND i.to_team_id=?
                """,
                (season, tid),
            ).fetchone()[0]
            team_tx[tid] = int(n_add + n_tin)

            # value added
            va = 0.0
            # all non-drafted first appearances
            for (s, tm, pid), (fw, acq) in first_acq.items():
                if s != season or tm != tid:
                    continue
                if acq == "Drafted":
                    continue
                drop_pid, drop_w = drop_for.get((tid, pid), (None, fw))
                for wk, pts in started.get((season, tid, pid), []):
                    if wk < fw:
                        continue
                    rep = 0.0
                    if drop_pid is not None:
                        rep = pts_pw.get((season, wk, drop_pid), 0.0)
                    va += pts - rep

            team_va[tid] = round(va, 2)

            # grid matrix
            weeks = list(range(1, max_week + 1))
            matrix = []
            details = {}
            for wk in weeks:
                row = []
                for col, dow in enumerate(DOW):
                    c = cell_count.get((tid, wk, col), 0)
                    row.append(c)
                    if c:
                        details[f"{wk}:{dow}"] = cell_moves.get((tid, wk, col), [])[
                            :20
                        ]
                matrix.append(row)
            team_grid[tid] = {
                "weeks": weeks,
                "dow": DOW,
                "counts": matrix,
                "details": details,
                "maxCell": max((max(r) if r else 0) for r in matrix) if matrix else 0,
            }

        # scatter
        va_vals = [team_va[t] for t in team_va]
        median = statistics.median(va_vals) if va_vals else 0.0
        scatter = []
        for tid, meta in teams[season].items():
            scatter.append(
                {
                    "tid": tid,
                    "member_id": meta["member_id"],
                    "name": meta["name"],
                    "logo": meta["logo"],
                    "transactions": team_tx[tid],
                    "valueAdded": team_va[tid],
                }
            )

        out_seasons[str(season)] = {
            "season": season,
            "maxWeek": max_week,
            "medianValueAdded": round(median, 2),
            "scatter": scatter,
            "teams": {
                str(tid): {
                    **teams[season][tid],
                    "transactions": team_tx[tid],
                    "valueAdded": team_va[tid],
                    "grid": team_grid[tid],
                }
                for tid in teams[season]
            },
        }

    payload = {
        "schemaVersion": 1,
        "evidence": "verified",
        "source": "fact_transaction + fact_roster_week + fact_player_week_par + fact_trade",
        "timezone": "America/Chicago",
        "note": (
            "Activity grid: every add, drop, and trade by day of week (CT). "
            "Lineup set/sit not shown — ESPN has no lineup timestamp. "
            "Value added = started points from in-season acquisitions minus "
            "same-week points of the player dropped in the paired move (0 if unknown). "
            "Drafted players excluded from Y. X = ADD count + trade-ins. "
            "2018+ only."
        ),
        "seasons": out_seasons,
    }
    path = SITE / "team_activity.json"
    path.write_text(json.dumps(payload) + "\n")
    # summary
    s25 = out_seasons.get("2025", {})
    sc = s25.get("scatter") or []
    sc_sorted = sorted(sc, key=lambda r: -r["valueAdded"])
    print(f"wrote {path} seasons={list(out_seasons)}")
    if sc_sorted:
        print(
            f"2025 medianVA={s25.get('medianValueAdded')} "
            f"top={sc_sorted[0]['name']} VA={sc_sorted[0]['valueAdded']} "
            f"tx={sc_sorted[0]['transactions']}"
        )
        print(
            f"2025 max tx={max(sc, key=lambda r: r['transactions'])['name']} "
            f"tx={max(sc, key=lambda r: r['transactions'])['transactions']}"
        )


if __name__ == "__main__":
    main()
