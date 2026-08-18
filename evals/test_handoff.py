#!/usr/bin/env python3
"""CHI-82: validate the repository's mandatory handoff entrypoint."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "START-HERE.md"
AGENTS = ROOT / "AGENTS.md"
fails = []


def require(condition, message):
    if not condition:
        fails.append(message)


require(START.is_file(), "missing root START-HERE.md")
text = START.read_text(encoding="utf-8") if START.is_file() else ""
lower = text.lower()

anchors = (
    "## 1. Project coordinates",
    "## 2. Required read order",
    "## 3. Sources of truth and evidence gates",
    "## 4. Identity contract",
    "## 5. Pipeline commands and mutations",
    "## 6. Local review loop",
    "## 7. Linear and status rules",
    "## 8. Brand and design rules",
    "## 9. Current work and blockers",
    "## 10. Copy/paste task handoff template",
    "## 11. Do not do these things",
)
for anchor in anchors:
    require(anchor in text, f"missing anchor: {anchor}")

required = (
    "/Users/chilly/Projects/ccDesktopAFFL",
    "rdsciv/affl-analytics",
    "verify/full-audit",
    "51418",
    "https://rdsciv.github.io/affl-analytics/",
    "https://linear.app/childressllc/project/affl-sourcebook-v1-88ad883cc233",
    "Childressllc",
    "affl.db",
    "208,168",
    "24,762",
    "m01 → m07",
    "m03 → m08",
    "m20 → m10",
    "m22",
    "python3 fetch.py all",
    "python3 build_db.py --check",
    "python3 inspect_data.py --season 2025",
    "python3 export_site.py",
    "python3 -m http.server 8765",
    "site/logos/affl-mark.png",
    "site/logos/affl-banner.png",
    "CHI-72",
    "CHI-75",
    "CHI-76",
    "CHI-80",
    "CHI-81",
    "CHI-82",
)
for value in required:
    require(value in text, f"missing required value: {value}")

require("there is no affl 2026 season before the draft" in lower,
        "must state no AFFL 2026 season before draft")
require("must not exist in `dim_season` or `dim_team` before the draft" in lower,
        "must forbid pre-draft 2026 dim_season/dim_team rows")
require("do not run `export_site.py` casually" in lower,
        "must warn against casual export_site.py use")
require("done" in lower and "production pages" in lower,
        "must define Done as production-reviewed work")
require(AGENTS.is_file(), "missing AGENTS.md pointer")
if AGENTS.is_file():
    agent_text = AGENTS.read_text(encoding="utf-8")
    require("START-HERE.md" in agent_text, "AGENTS.md does not point to START-HERE.md")
    require(len(agent_text.splitlines()) <= 8, "AGENTS.md should remain a tiny pointer")

line_count = len(text.splitlines())
require(200 <= line_count <= 350, f"START-HERE.md line count {line_count}, expected 200–350")

if fails:
    print("FAIL")
    for failure in fails:
        print(" -", failure)
    sys.exit(1)

print(f"PASS: START-HERE.md {line_count} lines; required anchors and 2026 correction present")
