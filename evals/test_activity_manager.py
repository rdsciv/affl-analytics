#!/usr/bin/env python3
"""CHI-112: Activity by Manager Y-axis uses franchise names and does not skip ticks."""
from pathlib import Path
js = (Path(__file__).resolve().parents[1] / "site/trades.js").read_text()
assert "function renderActivity" in js
assert "const names = rows.map((r) => tName(r.tid))" in js
assert "labels: names" in js
assert "autoSkip: false" in js
assert "ticks: { display: true" in js
assert "afterFit(scale)" in js
chunk = js.split("function renderActivity")[1].split("function renderTrades")[0]
assert "short(r.tid)" not in chunk
print("ok activity manager")
