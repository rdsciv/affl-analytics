#!/usr/bin/env python3
"""CHI-112: Activity by Manager Y-axis uses current franchise names.

Fails the live bug: renderActivity/renderKPIs tid: +tid, tName dash
fallback, missing labels: names / tName path. Runs the node helper
against extracted trades.js tName with owner-id keys.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def fn_chunk(src: str, start: str, stop: str) -> str:
    if start not in src:
        fail(f"missing {start}")
        return ""
    rest = src.split(start, 1)[1]
    return rest.split(stop, 1)[0] if stop in rest else rest


def main() -> int:
    js = (ROOT / "site/trades.js").read_text()
    html = (ROOT / "site/trades.html").read_text()

    act = fn_chunk(js, "function renderActivity", "function renderTrades")
    kpi = fn_chunk(js, "function renderKPIs", "function renderActivity")
    tname = fn_chunk(js, "function tName", "const short")

    if "tid: +tid" in act:
        fail("renderActivity still does tid: +tid on txByTeam entries")
    if "tid: +tid" in kpi:
        fail("renderKPIs still does tid: +tid on txByTeam entries")
    if "tid: +tid" in js:
        fail("trades.js still contains tid: +tid")

    if "labels: names" not in act:
        fail("renderActivity missing labels: names")
    if "tName(r.tid)" not in act:
        fail("renderActivity labels path missing tName(r.tid)")
    if "autoSkip: false" not in act:
        fail("autoSkip must be false")
    if "ticks: { display: true" not in act:
        fail("y ticks must display")
    if "afterFit(scale)" not in act:
        fail("afterFit padding missing")
    if "short(r.tid)" in act:
        fail("chart labels must be full franchise names, not short()")

    for bad in ('|| "—"', "|| '—'", '|| "-"', "|| '-'", 'return "—"', "return '—'", 'return "-"', "return '-'"):
        if bad in tname:
            fail(f"tName still falls back to a dash: {bad}")
    if "—" in tname or re.search(r'return\s+["\']-["\']', tname):
        fail("tName body still contains a dash fallback")
    if "Player " in tname:
        fail("tName must never invent Player N")
    if 'return "unavailable"' not in tname and "return 'unavailable'" not in tname:
        fail("tName must fall back to unavailable")
    if "A.franchiseName(id)" not in tname:
        fail("tName must call A.franchiseName(id) first")
    if "A.canon" not in tname:
        fail("tName must consult T[A.canon?.(id)]")
    if "function ownerKey" not in js:
        fail("ownerKey missing — ESPN sentinel -2147483648 must be dropped")
    if 'n !== "unavailable"' not in act and "n !== 'unavailable'" not in act:
        fail("renderActivity must drop unnamed / unavailable rows")
    if "2147483648" not in (ROOT / "evals/test_chi112_names.js").read_text():
        fail("name helper must assert the 2018 ESPN sentinel is dropped")

    bust = re.search(r"trades\.js\?v=(\d+)", html)
    if not bust:
        fail("trades.html missing trades.js cache bust")
    elif int(bust.group(1)) < 7:
        fail(f"trades.js cache still v={bust.group(1)}")

    helper = ROOT / "evals/test_chi112_names.js"
    if not helper.is_file():
        fail("missing evals/test_chi112_names.js")
    else:
        r = subprocess.run(["node", str(helper)], capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            fail("name helper failed")

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("CHI-112: owner-id keys stay strings; tName is current franchise names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
