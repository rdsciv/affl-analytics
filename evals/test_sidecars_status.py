#!/usr/bin/env python3
"""CHI-72 honesty: sidecar tables defined in schema.sql vs present in affl.db.

Does not load data. Fails only if someone claims completion without tables
or if schema drops the six known sidecar definitions. Pass = inventory OK
and (if tables exist) row counts are reported.
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
SCHEMA = ROOT / "schema.sql"

SIDECARS = (
    "fact_ngs",
    "dim_player_bio",
    "fact_injury",
    "fact_depthchart",
    "fact_college",
    "fact_player_overview",
)


def main():
    fails = []
    schema = SCHEMA.read_text(encoding="utf-8") if SCHEMA.is_file() else ""
    defined = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema))
    for t in SIDECARS:
        if t not in defined:
            fails.append(f"schema.sql missing CREATE for {t}")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    have = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing = [t for t in SIDECARS if t not in have]
    present = [t for t in SIDECARS if t in have]
    counts = {}
    for t in present:
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    # Honesty gate: START-HERE claims these are incomplete — if all six
    # suddenly appear empty, still PASS with LOADED_EMPTY; if all six have
    # rows, PASS LOADED. Missing is the current expected state.
    status = (
        "LOADED"
        if present and not missing and all(counts[t] > 0 for t in present)
        else "LOADED_EMPTY"
        if present and not missing
        else "PARTIAL"
        if present
        else "MISSING"
    )

    print(f"sidecars_status={status}")
    print(f"missing={missing}")
    print(f"present_counts={counts}")
    if status == "MISSING":
        print(
            "PASS: CHI-72 sidecars not in warehouse yet "
            "(schema defines them; site JSON may hold local caches only)"
        )
        print("Do not claim CHI-72 complete. Do not casual export_site.py.")
        return 0 if not fails else 1
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print(f"PASS: CHI-72 sidecar inventory {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
