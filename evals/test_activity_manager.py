#!/usr/bin/env python3
"""CHI-112: Activity by Manager Y-axis uses current franchise names, never dashes."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "site/trades.js").read_text()

def fail(msg):
    print("FAIL", msg)
    sys.exit(1)

if "function renderActivity" not in js:
    fail("renderActivity missing")
if "const names = rows.map((r) => tName(r.tid))" not in js:
    fail("chart labels must come from tName")
if "labels: names" not in js:
    fail("Chart labels: names missing")
if "autoSkip: false" not in js:
    fail("autoSkip must be false")
if "ticks: { display: true" not in js:
    fail("y ticks must display")
if "afterFit(scale)" not in js:
    fail("afterFit padding missing")

# The live fail: +tid smashed owner ids (m07) to NaN → "—"
if "tid: +tid" in js:
    fail("tid: +tid still smashes owner ids to NaN")

# tName must not paint a dash
for bad in ('|| "—"', "|| '—'", '|| "-"', "|| '-'"):
    if bad in js.split("function tName")[1].split("function ring")[0]:
        fail(f"tName still falls back to a dash: {bad}")
if 'return "unavailable"' not in js and "return 'unavailable'" not in js:
    fail("tName must fall back to unavailable, not a dash")

chunk = js.split("function renderActivity")[1].split("function renderTrades")[0]
if "short(r.tid)" in chunk:
    fail("chart labels must be full franchise names, not short()")

helper = ROOT / "evals/test_chi112_names.js"
if helper.exists():
    r = subprocess.run(["node", str(helper)], capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, end="")
        fail("name helper failed")

print("ok activity manager")
