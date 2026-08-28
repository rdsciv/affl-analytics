#!/usr/bin/env python3
"""CHI-143: blank/dash chart axis labels are an automatic block."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
site = ROOT / "site"
fails = []

# Activity chart is the known live fail. Other pages may still use em-dash
# as a numeric empty (fmt), which is fine — this gate is chart *axis labels*.
trades = (site / "trades.js").read_text()
if "tid: +tid" in trades:
    fails.append("trades.js still coerces owner ids with tid: +tid")
tname = trades.split("function tName")[1].split("const short")[0]
if "—" in tname or "return \"-\"" in tname or "return '-'" in tname:
    fails.append("trades.js tName still paints a dash")
if "labels: names" not in trades:
    fails.append("trades.js Activity chart missing labels: names")

# Any Chart.js labels: that are a hardcoded dash
for p in site.glob("*.js"):
    text = p.read_text()
    if re.search(r"labels:\s*\[\s*['\"][-—]['\"]", text):
        fails.append(f"{p.name} hardcodes a dash chart label")
    # y-axis callback that returns em-dash / hyphen for a category
    if re.search(r"ticks:\s*\{[^}]*callback:\s*\([^)]*\)\s*=>\s*['\"][-—]['\"]", text, re.S):
        fails.append(f"{p.name} tick callback returns a dash")

if fails:
    print("FAIL CHI-143")
    for f in fails:
        print(" ", f)
    sys.exit(1)
print("ok chi143 gate")
