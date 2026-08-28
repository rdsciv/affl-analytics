#!/usr/bin/env python3
"""CHI-138: Players database default is QB, career AFFL pts; sort stored metrics only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "site/players.js").read_text()
html = (ROOT / "site/players.html").read_text()
idx = json.loads((ROOT / "site/player_index.json").read_text())
fails = []


def fail(m):
    fails.append(m)


if 'pos: "QB"' not in js:
    fail("PP.pos default is not QB")
if re.search(r'const PP = \{[^}]*pos: "ALL"', js):
    fail("PP still defaults pos ALL")
block = re.search(r"const DB_SORTS = \[([\s\S]*?)\];", js)
if not block:
    fail("DB_SORTS missing")
else:
    body = block.group(1).lower()
    if "success" in body:
        fail("success rate invented in DB_SORTS")
    if "ypc" in body:
        fail("YPC is not on the career row; do not invent it")
if 'id="pp-sort"' not in html:
    fail("players.html missing #pp-sort")
if "players.js?v=38" not in html:
    fail("players.js pin not v=38")
if 'key: "tot"' not in js or 'key: "xtd"' not in js or 'key: "td"' not in js:
    fail("DB_SORTS missing tot/td/xtd")
for need in ["Russell Wilson", "Aaron Rodgers", "Matthew Stafford"]:
    if not any(v.get("name") == need and v.get("pos") == "QB" for v in idx.values()):
        fail(f"{need} missing from player_index as QB")
if "unavailable" not in js:
    fail("missing stays unavailable not in players.js")
if "paintDbChips" not in js:
    fail("pos chips still hard-coded ALL on")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS")
print("CHI-138: default QB; sort tot/td/xtd/starts/yds; no success rate")
