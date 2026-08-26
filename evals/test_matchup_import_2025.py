#!/usr/bin/env python3
"""CHI-24 / AFFL-004: 2025 matchup importer gates.

Runs against the real ESPN box cache and affl.db. Proves:

  1. Adapter output matches the warehouse (same 202 sides).
  2. Re-import is idempotent (fingerprint unchanged).
  3. Source checksum + import-run metadata are retained.
  4. Pairings: regular weeks 12 teams / 6 games; week 15 byes are not holes.
  5. Secrets in .env never appear in adapter output, diagnostics, or preview.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import adapters.espn_box_v1 as espn_box
import build_db

DB = ROOT / "affl.db"
DATA = ROOT / "data"
BOX = DATA / "box_2025.json"
LEAGUE = DATA / "league_2025.json"
SEASON = 2025
fails = []


def fail(msg):
    fails.append(msg)


def connect(rw=False):
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    uri = f"file:{DB}" if rw else f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def fingerprint(con, season):
    rows = list(con.execute("""
        SELECT season, week, team_id, opponent_id,
               ROUND(points, 4), ROUND(opponent_points, 4),
               is_home, tier, is_playoff
          FROM fact_matchup WHERE season=?
         ORDER BY week, team_id
    """, (season,)))
    blob = "\n".join("|".join("" if c is None else str(c) for c in r) for r in rows)
    return hashlib.sha256(blob.encode()).hexdigest(), len(rows)


def secret_needles():
    """Values from .env that must never appear in artifacts. Never printed."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return []
    out = []
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("ESPN_SWID", "ESPN_S2") and v and "XXXX" not in v and "your_url" not in v:
            if len(v) >= 8:
                out.append(v)
    return out


def scan_for_secrets(label, text, needles):
    for n in needles:
        if n and n in text:
            fail(f"{label} contains a runtime secret")
            return


def test_cache_present():
    if not BOX.exists():
        fail(f"missing {BOX} — ESPN cache should already be on disk")
    if not LEAGUE.exists():
        fail(f"missing {LEAGUE}")
    print(f"cache box_2025.json {BOX.stat().st_size} bytes")
    print(f"cache league_2025.json {LEAGUE.stat().st_size} bytes")


def test_adapter_matches_warehouse():
    con = connect()
    dim = con.execute("SELECT reg_weeks FROM dim_season WHERE season=?", (SEASON,)).fetchone()
    payload = espn_box.extract(str(DATA), SEASON, reg_weeks=dim[0] if dim else 14)
    if payload["adapter"] != "espn_box" or payload["adapter_version"] != "v1":
        fail(f"adapter identity {payload['adapter']} {payload['adapter_version']}")
    db = [tuple(r) for r in con.execute("""
        SELECT season, week, team_id, opponent_id, points, opponent_points,
               is_home, tier, is_playoff
          FROM fact_matchup WHERE season=?
         ORDER BY week, team_id
    """, (SEASON,))]
    rows = sorted(payload["rows"], key=lambda r: (r[1], r[2]))

    def norm(r):
        return (int(r[0]), int(r[1]), int(r[2]), int(r[3]),
                round(float(r[4]), 4), round(float(r[5]), 4),
                int(r[6]), r[7], int(r[8]))

    if [norm(r) for r in db] != [norm(r) for r in rows]:
        fail(f"adapter rows != warehouse ({len(rows)} vs {len(db)})")
    else:
        print(f"adapter espn_box v1 matches warehouse: {len(rows)} sides")
    box_src = next((s for s in payload["sources"] if s["path"].endswith("box_2025.json")), None)
    if not box_src or len(box_src["sha256"]) != 64:
        fail("adapter did not checksum data/box_2025.json")
    else:
        print(f"source {box_src['path']} sha256={box_src['sha256']}")
    con.close()
    return payload


def test_2025_facts():
    con = connect()
    sides = con.execute("SELECT COUNT(*) FROM fact_matchup WHERE season=2025").fetchone()[0]
    teams = con.execute("SELECT COUNT(DISTINCT team_id) FROM fact_matchup WHERE season=2025").fetchone()[0]
    weeks = [r[0] for r in con.execute(
        "SELECT DISTINCT week FROM fact_matchup WHERE season=2025 ORDER BY 1")]
    phases = {r[0]: r[1] for r in con.execute(
        "SELECT phase, COUNT(*) FROM v_matchup WHERE season=2025 GROUP BY phase")}
    mirrors = con.execute("""
        SELECT COUNT(*) FROM fact_matchup a LEFT JOIN fact_matchup b
          ON b.season=a.season AND b.week=a.week AND b.team_id=a.opponent_id
         WHERE a.season=2025 AND b.team_id IS NULL
    """).fetchone()[0]
    print(f"2025 sides={sides} teams={teams} weeks={weeks[0]}-{weeks[-1]}")
    print(f"2025 phases {phases}")
    if sides != 202:
        fail(f"2025 sides should be 202, got {sides}")
    if teams != 12:
        fail(f"2025 teams should be 12, got {teams}")
    if weeks != list(range(1, 18)):
        fail(f"2025 weeks should be 1-17, got {weeks}")
    if phases.get("regular") != 168:
        fail(f"2025 regular sides should be 168, got {phases.get('regular')}")
    if phases.get("championship") != 10:
        fail(f"2025 championship sides should be 10, got {phases.get('championship')}")
    if phases.get("consolation") != 24:
        fail(f"2025 consolation sides should be 24, got {phases.get('consolation')}")
    if mirrors:
        fail(f"2025 missing mirrors: {mirrors}")

    holes = []
    for r in con.execute("""
        SELECT week, COUNT(*) AS sides, COUNT(DISTINCT team_id) AS teams
          FROM fact_matchup WHERE season=2025 AND is_playoff=0
         GROUP BY week ORDER BY week
    """):
        if r["sides"] != 12 or r["teams"] != 12:
            holes.append(dict(r))
    if holes:
        fail(f"regular pairing holes (expected 12 teams / 6 games): {holes}")
    else:
        print("regular pairing: 14 weeks x 12 teams / 6 games")

    w15 = con.execute("""
        SELECT COUNT(*) AS sides, COUNT(DISTINCT team_id) AS teams
          FROM fact_matchup WHERE season=2025 AND week=15
    """).fetchone()
    if w15["sides"] != 10 or w15["teams"] != 10:
        fail(f"week 15 should be 10 teams / 5 games (byes), got {dict(w15)}")

    all_ids = {r[0] for r in con.execute(
        "SELECT DISTINCT team_id FROM fact_matchup WHERE season=2025")}
    w15_ids = {r[0] for r in con.execute(
        "SELECT DISTINCT team_id FROM fact_matchup WHERE season=2025 AND week=15")}
    byes = sorted(all_ids - w15_ids)
    ranks = {r["team_id"]: r["final_rank"] for r in con.execute(
        "SELECT team_id, name, final_rank FROM dim_team WHERE season=2025")}
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=2025")}
    bye_ranks = sorted(ranks[t] for t in byes)
    print(f"week 15 byes: {[(t, names[t], ranks[t]) for t in byes]}")
    if bye_ranks != [1, 2]:
        fail(f"week 15 byes should be final_rank 1 and 2, got {bye_ranks} ids={byes}")
    else:
        print("week 15 is first-round byes for #1 and #2 — not a pairing hole")
    con.close()


def test_idempotent_reimport():
    con = connect(rw=True)
    build_db.init(con)
    before_fp, before_n = fingerprint(con, SEASON)
    print(f"fingerprint before {before_fp} n={before_n}")
    con.close()

    cmd = [sys.executable, str(ROOT / "build_db.py"), "--import-matchups", "2025"]
    runs = []
    for i in range(2):
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        runs.append(proc)
        if proc.returncode != 0:
            fail(f"import-matchups run {i+1} exited {proc.returncode}: {proc.stderr[-400:]}")
        print(proc.stdout.strip())

    con = connect()
    after_fp, after_n = fingerprint(con, SEASON)
    print(f"fingerprint after  {after_fp} n={after_n}")
    if after_fp != before_fp or after_n != before_n:
        fail(f"re-import changed 2025 matchups ({before_n}->{after_n})")
    else:
        print("idempotent: fingerprint unchanged after two re-imports")

    n_runs = con.execute("""
        SELECT COUNT(*) FROM meta_import_run
         WHERE dataset='matchup' AND season=2025 AND adapter='espn_box'
           AND adapter_version='v1'
    """).fetchone()[0]
    if n_runs < 2:
        fail(f"expected at least 2 import-run rows for 2025 matchup, got {n_runs}")
    latest = con.execute("""
        SELECT run_id, status, row_count, diagnostics
          FROM meta_import_run
         WHERE dataset='matchup' AND season=2025
         ORDER BY run_id DESC LIMIT 1
    """).fetchone()
    if latest["status"] != "ok":
        fail(f"latest import-run status={latest['status']}")
    if latest["row_count"] != 202:
        fail(f"latest import-run row_count={latest['row_count']}")
    diag = json.loads(latest["diagnostics"] or "{}")
    if diag.get("holes"):
        fail(f"pairing diagnostics reported holes: {diag['holes']}")
    srcs = list(con.execute("""
        SELECT path, sha256, bytes FROM meta_import_source WHERE run_id=?
    """, (latest["run_id"],)))
    box_src = next((s for s in srcs if s["path"] == "data/box_2025.json"), None)
    if not box_src:
        fail(f"import-run sources missing data/box_2025.json: {[s['path'] for s in srcs]}")
    else:
        raw = BOX.read_bytes()
        expect = hashlib.sha256(raw).hexdigest()
        if box_src["sha256"] != expect:
            fail("stored sha256 does not match file bytes")
        if box_src["bytes"] != len(raw):
            fail(f"stored bytes {box_src['bytes']} != {len(raw)}")
        print(f"import-run {latest['run_id']} checksum ok  runs={n_runs}")
    con.close()

    needles = secret_needles()
    for i, proc in enumerate(runs):
        scan_for_secrets(f"import stdout run {i+1}", proc.stdout + proc.stderr, needles)
    return runs


def test_no_secret_leak(payload):
    needles = secret_needles()
    if not needles:
        print("no live ESPN secrets in .env to scan (ok if placeholders)")
    texts = []
    texts.append(("adapter module", (ROOT / "adapters" / "espn_box_v1.py").read_text()))
    texts.append(("adapter extract json", json.dumps(payload, default=str)))
    con = connect()
    try:
        rows = list(con.execute("""
            SELECT diagnostics FROM meta_import_run WHERE dataset='matchup'
        """))
        texts.append(("import diagnostics", "".join((r[0] or "") for r in rows)))
        srcs = list(con.execute("SELECT path, sha256 FROM meta_import_source"))
        texts.append(("import sources", json.dumps([tuple(r) for r in srcs])))
    except Exception as e:
        fail(f"could not read import metadata: {e}")
    con.close()
    for name in ("MATCHUP_IMPORT.md", "matchup_import_2025.csv",
                 "matchup_weeks_2025.csv", "SUMMARY.md"):
        p = ROOT / "preview" / name
        if p.exists():
            texts.append((f"preview/{name}", p.read_text()))
    for label, text in texts:
        scan_for_secrets(label, text, needles)
    # importer must not import fetch (fetch loads .env at import time)
    adapter_src = (ROOT / "adapters" / "espn_box_v1.py").read_text()
    if "import fetch" in adapter_src or "from fetch" in adapter_src:
        fail("adapter imports fetch.py, which loads .env")
    if ".env" in adapter_src and "never opens" not in adapter_src:
        fail("adapter mentions .env in a way that suggests it reads it")
    print("secrets scan: adapter / diagnostics / preview")


def main():
    test_cache_present()
    payload = test_adapter_matches_warehouse()
    test_2025_facts()
    test_idempotent_reimport()
    test_no_secret_leak(payload)
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-24: 2025 matchup importer is idempotent, checksummed, pairings complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
