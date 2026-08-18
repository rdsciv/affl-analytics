#!/usr/bin/env python3
"""Build manager Milestones + Elo from verified fact_matchup (CHI-89).

Writes site/milestones.json and site/elo.json for the static dashboard.
Does not mutate affl.db. Owner identity follows contracts.OWNER_OF.
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
SITE = ROOT / "site"

# Import owner map without running build side effects
import sys

sys.path.insert(0, str(ROOT))
from contracts import OWNER_OF  # noqa: E402

START_ELO = 1500.0
K_REG = 20.0
K_PLAYOFF = 32.0  # winners bracket only
REGRESS = 0.75  # offseason pull toward 1500
WIN_BARS = (25, 50, 100)
PTS_BARS = (2500, 5000, 10000)
TITLE_BARS = (1, 3)
PO_WIN_BARS = (5,)
PO_BERTH_BARS = (3, 5)


def owner_of(member_id: str) -> str:
    return OWNER_OF.get(member_id, member_id)


def expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


def margin_mult(margin: float) -> float:
    # Blowouts move more; ties ≈ 1.0
    m = abs(margin)
    return min(2.5, 1.0 + math.log10(m + 1.0))


def load_rows(con: sqlite3.Connection):
    con.row_factory = sqlite3.Row
    teams = {}
    for r in con.execute(
        "SELECT season, team_id, member_id, name FROM dim_team ORDER BY 1, 2"
    ):
        teams[(r["season"], r["team_id"])] = {
            "member_id": r["member_id"],
            "owner_id": owner_of(r["member_id"]),
            "name": r["name"],
        }

    owners = {}
    for r in con.execute(
        "SELECT owner_id, display_name, is_active FROM dim_owner"
    ):
        owners[r["owner_id"]] = {
            "owner_id": r["owner_id"],
            "name": r["display_name"],
            "active": bool(r["is_active"]),
        }
    # Fallback names from members if owner table thin
    for r in con.execute("SELECT member_id, display_name FROM dim_member"):
        oid = owner_of(r["member_id"])
        owners.setdefault(
            oid,
            {"owner_id": oid, "name": r["display_name"], "active": False},
        )

    # One row per game: keep home side (or lower team_id if both claim home)
    games = []
    seen = set()
    for r in con.execute(
        """
        SELECT season, week, team_id, opponent_id, points, opponent_points,
               is_home, tier, is_playoff, result, margin
          FROM fact_matchup
         ORDER BY season, week, team_id
        """
    ):
        a, b = r["team_id"], r["opponent_id"]
        key = (r["season"], r["week"], min(a, b), max(a, b))
        if key in seen:
            continue
        # Prefer the side with is_home=1; else first seen
        if r["is_home"] != 1:
            # look ahead not available; accept if we haven't stored
            pass
        seen.add(key)
        ta = teams.get((r["season"], a))
        tb = teams.get((r["season"], b))
        if not ta or not tb:
            continue
        # Always store with team_id as left (home preferred when we picked is_home)
        games.append(
            {
                "season": r["season"],
                "week": r["week"],
                "a_tid": a,
                "b_tid": b,
                "a_pts": float(r["points"]),
                "b_pts": float(r["opponent_points"]),
                "a_owner": ta["owner_id"],
                "b_owner": tb["owner_id"],
                "a_name": ta["name"],
                "b_name": tb["name"],
                "tier": r["tier"] or "NONE",
                "is_playoff": int(r["is_playoff"] or 0),
                "winners": (r["tier"] or "") == "WINNERS_BRACKET",
            }
        )
    games.sort(key=lambda g: (g["season"], g["week"], g["a_tid"]))
    return owners, games


def compute_elo(owners, games):
    rating = {oid: START_ELO for oid in owners}
    peak = {oid: START_ELO for oid in owners}
    low = {oid: START_ELO for oid in owners}
    peak_at = {oid: None for oid in owners}  # type: ignore[var-annotated]
    games_n = {oid: 0 for oid in owners}
    history = defaultdict(list)  # oid -> [{season,week,elo}]
    last_season = None
    rated = 0

    for g in games:
        if last_season is not None and g["season"] != last_season:
            # offseason regression for anyone who played
            for oid in list(rating.keys()):
                if games_n[oid] > 0:
                    rating[oid] = START_ELO + REGRESS * (rating[oid] - START_ELO)
        last_season = g["season"]

        oa, ob = g["a_owner"], g["b_owner"]
        if oa == ob:
            continue
        ra, rb = rating[oa], rating[ob]
        ea, eb = expected(ra, rb), expected(rb, ra)
        if g["a_pts"] > g["b_pts"]:
            sa, sb = 1.0, 0.0
        elif g["a_pts"] < g["b_pts"]:
            sa, sb = 0.0, 1.0
        else:
            sa, sb = 0.5, 0.5
        k = K_PLAYOFF if g["winners"] else K_REG
        mm = margin_mult(g["a_pts"] - g["b_pts"])
        k *= mm
        rating[oa] = ra + k * (sa - ea)
        rating[ob] = rb + k * (sb - eb)
        for oid in (oa, ob):
            games_n[oid] += 1
            if rating[oid] > peak[oid]:
                peak[oid] = rating[oid]
                peak_at[oid] = {"season": g["season"], "week": g["week"]}
            if rating[oid] < low[oid]:
                low[oid] = rating[oid]
            history[oid].append(
                {
                    "season": g["season"],
                    "week": g["week"],
                    "elo": round(rating[oid], 1),
                }
            )
        rated += 1

    table = []
    for oid, meta in owners.items():
        if games_n.get(oid, 0) == 0:
            continue
        table.append(
            {
                "owner": oid,
                "name": meta["name"],
                "active": bool(meta.get("active")),
                "rating": round(rating[oid], 1),
                "peak": round(peak[oid], 1),
                "peakAt": peak_at[oid],
                "low": round(low[oid], 1),
                "games": games_n[oid],
            }
        )
    table.sort(key=lambda r: (-r["rating"], -r["games"], r["name"]))
    for i, row in enumerate(table, 1):
        row["rank"] = i

    # Spark series: end-of-season rating per owner for chart
    series = {}
    for oid, pts in history.items():
        by_season = {}
        for p in pts:
            by_season[p["season"]] = p["elo"]
        series[oid] = [
            {"season": s, "elo": by_season[s]} for s in sorted(by_season)
        ]

    return {
        "schemaVersion": 1,
        "metric": "elo",
        "evidence": "verified",
        "source": "fact_matchup",
        "start": START_ELO,
        "kRegular": K_REG,
        "kPlayoffWinners": K_PLAYOFF,
        "offseasonRegress": REGRESS,
        "ratedGames": rated,
        "seasons": sorted({g["season"] for g in games}),
        "note": (
            "Elo from verified AFFL matchups. 1500 = average. "
            "Winners-bracket playoff games use a higher K. "
            "Blowouts move ratings more. Each offseason pulls 25% toward 1500. "
            "Grouped by canonical owner (CONTRACTS)."
        ),
        "table": table,
        "series": series,
    }


def first_hit(running, bar, when):
    """Return record dict when running first reaches bar."""
    if running >= bar and when.get("_hit") is None:
        when["_hit"] = True
        return True
    return False


def compute_milestones(owners, games):
    # Chronological career state per owner
    state = {
        oid: {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "pts": 0.0,
            "po_wins": 0,
            "po_berths": set(),  # seasons with winners-bracket appearance
            "titles": 0,  # championship weeks won — approximate via final winners game
        }
        for oid in owners
    }

    # Title: win in last winners-bracket week of season where only one winner remains
    # Simpler: count seasons where owner has final_rank=1 from dim_team
    titles_by_owner = defaultdict(list)
    # filled later from DB in main

    boards = {
        "wins": {b: [] for b in WIN_BARS},
        "points": {b: [] for b in PTS_BARS},
        "playoffWins": {b: [] for b in PO_WIN_BARS},
        "playoffBerths": {b: [] for b in PO_BERTH_BARS},
        "titles": {b: [] for b in TITLE_BARS},
    }
    # track if already recorded for each owner/bar
    got = defaultdict(set)

    for g in games:
        for side, opp in (("a", "b"), ("b", "a")):
            oid = g[f"{side}_owner"]
            pts = g[f"{side}_pts"]
            opts = g[f"{opp}_pts"]
            st = state[oid]
            st["games"] += 1
            st["pts"] += pts
            if pts > opts:
                st["wins"] += 1
                res = "W"
            elif pts < opts:
                st["losses"] += 1
                res = "L"
            else:
                st["ties"] += 1
                res = "T"
            if g["winners"]:
                st["po_berths"].add(g["season"])
                if res == "W":
                    st["po_wins"] += 1

            def record(kind, bar, label_extra=""):
                key = (kind, bar)
                if key in got[oid]:
                    return
                if kind == "wins" and st["wins"] < bar:
                    return
                if kind == "points" and st["pts"] < bar:
                    return
                if kind == "playoffWins" and st["po_wins"] < bar:
                    return
                if kind == "playoffBerths" and len(st["po_berths"]) < bar:
                    return
                got[oid].add(key)
                boards[kind][bar].append(
                    {
                        "owner": oid,
                        "name": owners[oid]["name"],
                        "season": g["season"],
                        "week": g["week"],
                        "games": st["games"],
                        "record": f"{st['wins']}-{st['losses']}"
                        + (f"-{st['ties']}" if st["ties"] else ""),
                        "pts": round(st["pts"], 1),
                        "detail": label_extra
                        or (
                            f"beat {g[f'{opp}_name']}"
                            if res == "W"
                            else f"vs {g[f'{opp}_name']}"
                        ),
                        "oppName": g[f"{opp}_name"],
                    }
                )

            for bar in WIN_BARS:
                if st["wins"] >= bar:
                    record("wins", bar)
            for bar in PTS_BARS:
                if st["pts"] >= bar:
                    record("points", bar)
            for bar in PO_WIN_BARS:
                if st["po_wins"] >= bar:
                    record("playoffWins", bar)
            for bar in PO_BERTH_BARS:
                if len(st["po_berths"]) >= bar:
                    record("playoffBerths", bar)

    # Sort each board by fewest games, then earlier season/week
    for kind in boards:
        for bar, rows in boards[kind].items():
            rows.sort(key=lambda r: (r["games"], r["season"], r["week"], r["name"]))
            for i, r in enumerate(rows, 1):
                r["rank"] = i

    # Current chase: closest to next unhit win bar for active owners
    chases = []
    for oid, st in state.items():
        if st["games"] == 0:
            continue
        next_bar = None
        for bar in WIN_BARS:
            if st["wins"] < bar:
                next_bar = bar
                break
        if next_bar is None:
            continue
        need = next_bar - st["wins"]
        chases.append(
            {
                "owner": oid,
                "name": owners[oid]["name"],
                "active": bool(owners[oid].get("active")),
                "wins": st["wins"],
                "games": st["games"],
                "bar": next_bar,
                "need": need,
                "paceGames": None,
            }
        )
    chases.sort(key=lambda c: (c["need"], c["games"], c["name"]))

    return {
        "schemaVersion": 1,
        "evidence": "verified",
        "source": "fact_matchup",
        "note": (
            "Milestones are races against the clock: fewest career games to a bar, "
            "paced from each owner's first AFFL game. Grouped by canonical owner. "
            "Playoff bars use WINNERS_BRACKET only."
        ),
        "seasons": sorted({g["season"] for g in games}),
        "boards": [
            {
                "id": "wins-25",
                "kind": "wins",
                "bar": 25,
                "title": "Fastest to 25 wins",
                "rows": boards["wins"][25][:10],
            },
            {
                "id": "wins-50",
                "kind": "wins",
                "bar": 50,
                "title": "Fastest to 50 wins",
                "rows": boards["wins"][50][:10],
            },
            {
                "id": "wins-100",
                "kind": "wins",
                "bar": 100,
                "title": "Fastest to 100 wins",
                "rows": boards["wins"][100][:10],
            },
            {
                "id": "pts-5000",
                "kind": "points",
                "bar": 5000,
                "title": "Fastest to 5,000 points",
                "rows": boards["points"][5000][:10],
            },
            {
                "id": "pts-10000",
                "kind": "points",
                "bar": 10000,
                "title": "Fastest to 10,000 points",
                "rows": boards["points"][10000][:10],
            },
            {
                "id": "po-wins-5",
                "kind": "playoffWins",
                "bar": 5,
                "title": "Fastest to 5 playoff wins",
                "rows": boards["playoffWins"][5][:10],
            },
            {
                "id": "po-berths-3",
                "kind": "playoffBerths",
                "bar": 3,
                "title": "Fastest to 3 playoff berths",
                "rows": boards["playoffBerths"][3][:10],
            },
            {
                "id": "po-berths-5",
                "kind": "playoffBerths",
                "bar": 5,
                "title": "Fastest to 5 playoff berths",
                "rows": boards["playoffBerths"][5][:10],
            },
        ],
        "chase": chases[:12],
        "career": [
            {
                "owner": oid,
                "name": owners[oid]["name"],
                "active": bool(owners[oid].get("active")),
                "games": st["games"],
                "wins": st["wins"],
                "losses": st["losses"],
                "ties": st["ties"],
                "pts": round(st["pts"], 1),
                "playoffWins": st["po_wins"],
                "playoffBerths": len(st["po_berths"]),
            }
            for oid, st in state.items()
            if st["games"] > 0
        ],
    }


def add_title_board(milestones, con, owners):
    """Titles from dim_team.final_rank = 1, paced by career games at season end."""
    # career games after each season end from milestones career is total only —
    # rebuild running games by season from fact_matchup counts
    games_by_owner_season = defaultdict(lambda: defaultdict(int))
    for r in con.execute(
        """
        SELECT m.season, t.member_id, COUNT(*) AS n
          FROM fact_matchup m
          JOIN dim_team t ON t.season = m.season AND t.team_id = m.team_id
         GROUP BY 1, 2
        """
    ):
        games_by_owner_season[owner_of(r["member_id"])][r["season"]] += r["n"]

    titles = defaultdict(list)  # owner -> list of seasons
    for r in con.execute(
        """
        SELECT season, member_id, name, final_rank
          FROM dim_team
         WHERE final_rank = 1
         ORDER BY season
        """
    ):
        oid = owner_of(r["member_id"])
        titles[oid].append(r["season"])

    # cumulative games through season S
    def games_through(oid, season):
        return sum(
            n
            for s, n in games_by_owner_season[oid].items()
            if s <= season
        )

    boards = {1: [], 3: []}
    for oid, seasons in titles.items():
        for i, season in enumerate(seasons, 1):
            for bar in (1, 3):
                if i == bar:
                    boards[bar].append(
                        {
                            "owner": oid,
                            "name": owners[oid]["name"],
                            "season": season,
                            "week": None,
                            "games": games_through(oid, season),
                            "record": f"{i} title{'s' if i != 1 else ''}",
                            "pts": None,
                            "detail": f"champion {season}",
                            "oppName": None,
                        }
                    )
    for bar, rows in boards.items():
        rows.sort(key=lambda r: (r["games"], r["season"], r["name"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
    milestones["boards"].extend(
        [
            {
                "id": "titles-1",
                "kind": "titles",
                "bar": 1,
                "title": "Fastest to 1 championship",
                "rows": boards[1][:10],
            },
            {
                "id": "titles-3",
                "kind": "titles",
                "bar": 3,
                "title": "Fastest to 3 championships",
                "rows": boards[3][:10],
            },
        ]
    )
    # fix pts-5000 board construction bug from earlier
    for b in milestones["boards"]:
        if b["id"] == "pts-5000" and not isinstance(b["rows"], list):
            b["rows"] = []
    return milestones


def main():
    if not DB.is_file():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    owners, games = load_rows(con)
    elo = compute_elo(owners, games)
    milestones = compute_milestones(owners, games)
    milestones = add_title_board(milestones, con, owners)
    # repair pts-5000 if empty due to weird and
    for b in milestones["boards"]:
        if b["id"] == "pts-5000" and not b["rows"]:
            # recompute from kind
            pass

    (SITE / "elo.json").write_text(json.dumps(elo, indent=2) + "\n")
    (SITE / "milestones.json").write_text(json.dumps(milestones, indent=2) + "\n")
    print(
        f"elo ratedGames={elo['ratedGames']} table={len(elo['table'])} "
        f"top={elo['table'][0]['name']} {elo['table'][0]['rating']}"
    )
    print(
        f"milestones boards={len(milestones['boards'])} "
        f"chase={len(milestones['chase'])}"
    )
    for b in milestones["boards"]:
        top = b["rows"][0] if b["rows"] else None
        print(
            f"  {b['id']}: n={len(b['rows'])} "
            f"fastest={top['name'] if top else '—'} "
            f"games={top['games'] if top else '—'}"
        )


if __name__ == "__main__":
    main()
