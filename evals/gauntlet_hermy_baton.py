#!/usr/bin/env python3
"""
Gauntlet matrix for active Hermy Baton / AFFL Sourcebook tickets.

Run: python3 evals/gauntlet_hermy_baton.py

This is the "core contracts" runner for the current wave.
It exercises the dedicated per-ticket (or per-critical-invariant) evals.

Tickets covered (update as Linear changes):
- CHI-75: no AFFL 2026 season (test_warehouse_2026.py)
- CHI-89: Elo + Milestones on dashboard (test_milestones_elo.py)
- CHI-54: FPpG = pts / NFL games (test_fppg.py)
- CHI-45: Trade join correctness (test_trade_builder_join.py + test_trades_2025.py)
- Wave T / team activity: (test_team_activity.py)
- Git / asset safety: (test_site_git_complete.py)
- Sidecar honesty: (test_sidecars_status.py)
- Handoff / overall: (test_handoff.py)
- CHI-76 plan only: (test_chi76_plan.py)
- CHI-130: franchise-year lock (site/evals/franchise-year-lock.test.mjs, node)
- CHI-33: lineup IQ, incl. the pre-2018 dated team-weeks (test_lineup_iq_2025.py)
- Pre-2018 recovery contract: (test_historical_gates.py)

Rules:
- Run this before claiming any ticket "ready for In QA".
- All must PASS + server must be live on 8765 for full results.
- Add new ticket evals here as they are created.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"

# Core gauntlet tickets + their primary eval(s)
# Order matters: contracts first, then features.
MATRIX = [
    ("CHI-75 (no 2026 + owner map)", "test_warehouse_2026.py"),
    ("CHI-89 (Elo + Milestones)", "test_milestones_elo.py"),
    ("CHI-54 (FPpG denominator)", "test_fppg.py"),
    ("CHI-45 (trade builder join)", "test_trade_builder_join.py"),
    ("CHI-45 (trades 2025)", "test_trades_2025.py"),
    ("Wave T (team activity)", "test_team_activity.py"),
    ("Asset/git completeness guard", "test_site_git_complete.py"),
    ("Sidecars status (CHI-72 honesty)", "test_sidecars_status.py"),
    ("Handoff / START-HERE (CHI-82)", "test_handoff.py"),
    ("CHI-76 viz plan", "test_chi76_plan.py"),
    ("CHI-130 franchise-year lock", "franchise-year-lock.test.mjs"),
    ("CHI-33 lineup IQ (2018+ season, pre-2018 dated)", "test_lineup_iq_2025.py"),
    ("Pre-2018 recovery contract", "test_historical_gates.py"),
]

def run_one(name, script):
    # Node evals live under site/evals and are named .mjs; everything else is a
    # python eval under evals/. Same reporting either way - a lock nobody runs is
    # not a lock.
    if script.endswith(".mjs"):
        path = ROOT / "site" / "evals" / script
        argv = ["node", str(path)]
    else:
        path = EVALS / script
        argv = [sys.executable, str(path)]
    if not path.exists():
        print(f"[{name}] MISSING SCRIPT: {script}")
        return False, "MISSING"

    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ROOT,
        )
        out = (r.stdout or "") + (r.stderr or "")
        last_lines = "\n".join(out.strip().splitlines()[-3:])
        # Some python evals print their failures and still exit 0, so the substring
        # is the real guard there. The node eval reports a tally ("PASS 67  FAIL 0")
        # that the same substring would read as a failure, so it is trusted on its
        # exit code - which it sets correctly.
        passed = r.returncode == 0
        if not script.endswith(".mjs"):
            passed = passed and "FAIL" not in out.upper()
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        if not passed:
            print("  last output:")
            for line in last_lines.splitlines():
                print("   ", line)
        return passed, status
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
        return False, "ERROR"

def main():
    print("=== AFFL Hermy Baton Gauntlet Matrix ===")
    print(f"Running {len(MATRIX)} critical ticket guards\n")

    all_pass = True
    results = []
    for ticket_name, script in MATRIX:
        ok, st = run_one(ticket_name, script)
        results.append((ticket_name, st))
        if not ok:
            all_pass = False

    print("\n=== Summary ===")
    for name, st in results:
        print(f"  {st:6}  {name}")

    passed_count = sum(1 for _, st in results if st == "PASS")
    print(f"\n{passed_count}/{len(MATRIX)} core guards PASS")

    if not all_pass:
        print("\nFAIL — do not claim In QA until all above are green.")
        return 1

    print("\nPASS — core Hermy Baton contracts look good.")
    print("Still run full adjacent regressions + Ryan Chrome review before In QA.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
