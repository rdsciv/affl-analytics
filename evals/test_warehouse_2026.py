#!/usr/bin/env python3
"""CHI-75 + CHI-72 owner map: no AFFL 2026 season before the draft.

Planning membership (site CURRENT_2026 rail) is navigation only.
NFL 2026 rows in player_season are roster identity, not an AFFL season.
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
COMMON = ROOT / "site" / "common.js"
BUILD = ROOT / "build_db.py"
fails = []
fail = lambda m: fails.append(m)

# 2025 twelve minus Pounders/Pollywogs, plus Chupacabras + Gabagooners
PLANNING_2026 = (
    "m11", "m06", "m08", "m05", "m02", "m18",
    "m15", "m17", "m21", "m13", "m22", "m07",
)
GONE = ("m19", "m14")  # Pounders, Pollywogs


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    # --- CHI-75: warehouse must not claim an AFFL 2026 season ---
    seasons = [r[0] for r in con.execute("SELECT season FROM dim_season ORDER BY 1")]
    if 2026 in seasons:
        fail("dim_season still has 2026 (CHI-75: no AFFL season before draft)")
    if seasons != list(range(2014, 2026)):
        fail(f"dim_season expected 2014–2025, got {seasons}")

    n_team_2026 = con.execute(
        "SELECT COUNT(*) FROM dim_team WHERE season=2026"
    ).fetchone()[0]
    if n_team_2026:
        fail(f"dim_team has {n_team_2026} season=2026 rows (must be 0)")

    for table in (
        "fact_draft_pick",
        "fact_matchup",
        "fact_transaction",
        "fact_trade",
        "fact_roster_week",
    ):
        n = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE season=2026"
        ).fetchone()[0]
        if n:
            fail(f"{table} has {n} 2026 AFFL rows (must be 0)")

    # Build path must not call the retired stub loader
    build_src = BUILD.read_text(encoding="utf-8") if BUILD.is_file() else ""
    if re.search(r"load_2026_stub\s*\(", build_src):
        # allow the def and the raise message, not a live call from main
        live = [
            ln for ln in build_src.splitlines()
            if "load_2026_stub(" in ln
            and not ln.strip().startswith("#")
            and not ln.strip().startswith("def ")
            and "raise" not in ln
            and "retired" not in ln
        ]
        # any remaining call that isn't inside the def's docstring path
        live_calls = [
            ln for ln in live
            if "load_2026_stub(con" in ln or "load_2026_stub (" in ln
        ]
        if live_calls:
            fail(f"build_db.py still calls load_2026_stub: {live_calls}")
    if "refuse_affl_2026_season" not in build_src:
        fail("build_db.py missing refuse_affl_2026_season (CHI-75 safety belt)")

    # Site planning rail exists and lists 12 members (nav only)
    if not COMMON.is_file():
        fail("missing site/common.js")
    else:
        js = COMMON.read_text(encoding="utf-8")
        block = re.search(r"const CURRENT_2026 = \[(.*?)\];", js, re.S)
        if not block:
            fail("CURRENT_2026 missing from site/common.js")
        else:
            rows = re.findall(
                r'owner:\s*"([^"]+)"\s*,\s*name:\s*"([^"]+)"',
                block.group(1),
            )
            if len(rows) != 12:
                fail(f"CURRENT_2026 has {len(rows)} entries, need 12")
            mids = {o for o, _ in rows}
            names = " ".join(n for _, n in rows)
            missing = [m for m in PLANNING_2026 if m not in mids]
            if missing:
                fail(f"CURRENT_2026 missing members {missing}")
            for gone in GONE:
                if gone in mids:
                    fail(f"{gone} still in CURRENT_2026 planning rail")
            if "m22" not in mids or "Gabagooner" not in names:
                fail("Gabagooners not on CURRENT_2026 rail")
            if "m07" not in mids or "Chupacabra" not in names:
                fail("Chupacabras/m07 not on CURRENT_2026 rail")

    # --- Owner map (still CHI-72 / CONTRACTS; independent of season stub) ---
    kafka = con.execute(
        "SELECT owner_id, is_active FROM dim_owner WHERE display_name='Jason Kafka'"
    ).fetchone()
    if not kafka or kafka["owner_id"] != "m07":
        fail(
            f"Kafka owner_id is "
            f"{None if not kafka else kafka['owner_id']}, need m07"
        )
    if not kafka or not kafka["is_active"]:
        fail("Kafka/Chupacabras not current")
    m01 = con.execute(
        "SELECT owner_id FROM dim_member WHERE member_id='m01'"
    ).fetchone()
    m07 = con.execute(
        "SELECT owner_id FROM dim_member WHERE member_id='m07'"
    ).fetchone()
    if not m07 or m07[0] != "m07":
        fail("m07 is not the canonical Kafka owner")
    if not m01 or m01[0] != "m07":
        fail("m01 is not merged onto m07")
    leftover = con.execute(
        "SELECT 1 FROM dim_owner WHERE owner_id='m01'"
    ).fetchone()
    if leftover:
        fail("stale dim_owner m01 still present (m07→m01 not fully stopped)")

    gaba = con.execute(
        "SELECT owner_id, display_name, is_active FROM dim_owner WHERE owner_id='m22'"
    ).fetchone()
    if not gaba:
        fail("Gabagooners owner m22 missing")
    elif gaba["display_name"] != "Andy Pietromonaco":
        fail(f"m22 name {gaba['display_name']!r}, expected Andy Pietromonaco")
    elif not gaba["is_active"]:
        fail("Gabagooners m22 not current")
    hist = con.execute(
        "SELECT COUNT(*) FROM dim_team WHERE member_id='m22'"
    ).fetchone()[0]
    if hist:
        fail(f"Gabagooners have {hist} team-seasons (must be 0 history)")

    for mid, label in (("m19", "Pounders"), ("m14", "Pollywogs")):
        row = con.execute(
            "SELECT is_active FROM dim_owner WHERE owner_id=?", (mid,)
        ).fetchone()
        if row and row[0]:
            fail(f"{label} {mid} still marked active")

    # NFL 2026 roster identity is allowed (not an AFFL season)
    nfl = con.execute(
        "SELECT COUNT(*) FROM player_season WHERE season=2026"
    ).fetchone()[0]
    if nfl <= 0:
        fail("2026 NFL roster rows == 0 (player_season identity expected)")

    print(
        f"affl_2026_season=0 nfl_players_2026={nfl} "
        f"kafka={kafka['owner_id'] if kafka else None} "
        f"planning_rail=12"
    )
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print(
        "CHI-75: no AFFL 2026 dim_season/dim_team; "
        "owner map + CURRENT_2026 rail OK; NFL 2026 identity retained"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
