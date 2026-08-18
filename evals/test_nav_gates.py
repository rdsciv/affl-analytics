#!/usr/bin/env python3
"""CHI-29 / AFFL-009: verification and navigation release gates.

Primary nav may only list modules whose required grain is verified for 2025.
Unavailable modules stay out. Pre-2018 lineup/tx pages must not invent rows.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
PREVIEW = ROOT / "preview"
fails = []

NAV_PAGES = [
    "index.html", "scoreboard.html", "players.html", "draft.html",
    "trades.html", "roto.html", "teams.html", "history.html", "awards.html",
    "dictionary.html", "wrapped.html",
]
NAV_ORDER = ["Dashboard", "Scoreboard", "Players", "Draft", "Trades", "Roto", "Teams", "History", "Awards", "Dictionary", "Wrapped"]
# Pages that must NOT appear in primary nav until their grain is verified.
BANNED_NAV = ("genius", "projections", "lab", "auction-lab")

# 2025 required grain per nav module
NAV_GRAIN = {
    "Dashboard": "matchup+standings",
    "Scoreboard": "matchup",
    "Players": "roster_week",
    "Draft": "draft_pick",
    "Trades": "transaction",
    "Roto": "roster_week+nfl_week",
    "Teams": "team-season",
    "History": "franchise-career",
    "Awards": "roster_week",
    "Dictionary": "docs",
    "Wrapped": "matchup+standings",
}


def fail(msg):
    fails.append(msg)


def nav_labels(html):
    m = re.search(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    if not m:
        return []
    return re.findall(r"<a[^>]*>([^<]+)</a>", m.group(1))


def main():
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    # --- warehouse evidence for 2025 ---
    s = con.execute("SELECT * FROM dim_season WHERE season=2025").fetchone()
    if not s or not s["has_rosters"] or not s["has_tx"]:
        fail("2025 dim_season missing has_rosters/has_tx")
    n_mu = con.execute("SELECT COUNT(*) FROM fact_matchup WHERE season=2025").fetchone()[0]
    n_rw = con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=2025").fetchone()[0]
    n_dp = con.execute("SELECT COUNT(*) FROM fact_draft_pick WHERE season=2025").fetchone()[0]
    n_tx = con.execute("SELECT COUNT(*) FROM fact_transaction WHERE season=2025").fetchone()[0]
    n_nfl = con.execute("SELECT COUNT(*) FROM fact_nfl_week WHERE season=2025").fetchone()[0]
    print(f"2025 grain matchup={n_mu} roster={n_rw} draft={n_dp} tx={n_tx} nfl={n_nfl}")
    if n_mu < 200:
        fail("2025 matchups missing — Dashboard/Scoreboard cannot be in nav")
    if n_rw < 1000:
        fail("2025 roster weeks missing — Players/Roto cannot be in nav")
    if n_dp < 100:
        fail("2025 draft missing — Draft cannot be in nav")
    if n_tx < 100:
        fail("2025 transactions missing — Trades cannot be in nav")
    if n_nfl < 1000:
        fail("2025 nfl weeks missing — Roto cannot be in nav")

    # pre-2018 lineup/tx must be unavailable
    for year in (2014, 2015, 2016, 2017):
        row = con.execute("SELECT has_rosters, has_tx FROM dim_season WHERE season=?", (year,)).fetchone()
        rw = con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=?", (year,)).fetchone()[0]
        tx = con.execute("SELECT COUNT(*) FROM fact_transaction WHERE season=?", (year,)).fetchone()[0]
        if row["has_rosters"] or rw:
            fail(f"{year} has roster weeks — CONTRACTS says unavailable")
        if row["has_tx"] or tx:
            fail(f"{year} has transactions — CONTRACTS says unavailable")
    print("2014-2017 lineup/tx grain is unavailable (correct)")

    # History grain: franchise career on data.json
    data = json.loads((SITE / "data.json").read_text())
    frs = data.get("franchises") or []
    n_fr = len(frs)
    print(f"History grain franchises={n_fr}")
    # 18 historic + Gabagooners m22 (0 seasons) = 19. Floor 19 after m22 join.
    if n_fr < 19:
        fail(f"History grain: data.json franchises {n_fr} < 19")
    owners = {f.get("owner") for f in frs if isinstance(f, dict)}
    if "m22" not in owners:
        fail("History grain missing Gabagooners owner m22")
    if "m07" not in owners:
        fail("History grain missing Kafka/Chupacabras m07")

    # --- primary nav ---
    for page in NAV_PAGES:
        p = SITE / page
        if not p.exists():
            fail(f"missing {page}")
            continue
        labels = nav_labels(p.read_text())
        if labels != NAV_ORDER:
            fail(f"{page} nav {labels} != {NAV_ORDER}")
        low = " ".join(labels).lower()
        for ban in BANNED_NAV:
            if ban in low:
                fail(f"{page} primary nav contains unavailable module {ban}")
    print(f"primary nav locked: {NAV_ORDER}")

    # scoreboard chips years without rosters
    sb = (SITE / "scoreboard.js").read_text()
    if "hasRosters" not in sb:
        fail("scoreboard.js does not gate on hasRosters")
    roto = (SITE / "roto.js").read_text()
    if "unavailable" not in roto:
        fail("roto.js does not label unavailable years")
    # roto must not invent pre-2018
    if "2014" in roto and "zero" in roto.lower() and "pre-2018" not in roto.lower():
        fail("roto.js may be zero-filling pre-2018")

    PREVIEW.mkdir(exist_ok=True)
    lines = [
        "# Navigation and verification gates",
        "",
        "CHI-29 / AFFL-009. Unavailable modules stay out of primary nav.",
        "",
        "## Primary nav (2025 verified grain)",
        "",
        "| page | grain | 2025 rows |",
        "| --- | --- | --- |",
        f"| Dashboard | matchup+standings | {n_mu} matchups |",
        f"| Scoreboard | matchup | {n_mu} |",
        f"| Players | roster_week | {n_rw} |",
        f"| Draft | draft_pick | {n_dp} |",
        f"| Trades | transaction | {n_tx} |",
        f"| Roto | roster_week+nfl_week | {n_rw} / {n_nfl} |",
        f"| Teams | team-season | 12 |",
        f"| History | franchise-career | {n_fr} franchises |",
        f"| Awards | roster_week | {n_rw} |",
        f"| Wrapped | matchup+standings | {n_mu} matchups |",
        "",
        "Not in primary nav: Genius, Projections, Auction Lab.",
        "",
        "## Pre-2018",
        "",
        "Weekly lineups and the transaction feed are unavailable. "
        "Scoreboard chips those years. Roto career marks them missing, not zero.",
        "",
        "## How to refresh",
        "",
        "```",
        "python3 evals/test_nav_gates.py",
        "```",
        "",
    ]
    path = PREVIEW / "NAV.md"
    path.write_text("\n".join(lines))
    print(path)
    con.close()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-29: 2025 nav modules have verified grain; unavailable stay out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
