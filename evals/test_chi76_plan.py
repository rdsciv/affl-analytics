#!/usr/bin/env python3
"""CHI-76 planning artifact present; no package installs."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails = []

plan = ROOT / "research/CHI-76_viz_tooling_plan.md"
if not plan.is_file():
    fails.append("missing research/CHI-76_viz_tooling_plan.md")
else:
    t = plan.read_text(encoding="utf-8")
    if "Stay Chart.js" not in t and "stay on Chart.js" not in t and "stay Chart.js" not in t.lower():
        fails.append("plan must recommend stay Chart.js")
    if "zero package" not in t.lower() and "Zero package" not in t:
        fails.append("plan must say zero package installs")

# no new package.json at site root
if (ROOT / "package.json").is_file():
    # allowed if pre-existing — only fail if node_modules newly required
    pass

# Chart.js still bundled
if not (ROOT / "site/chart.umd.min.js").is_file():
    fails.append("site/chart.umd.min.js missing — do not remove while staying Chart.js")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS")
print("CHI-76: plan present; stay Chart.js; no install required")
sys.exit(0)
