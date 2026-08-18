#!/usr/bin/env python3
"""Draft age + NFL logos: bios exist, UI wired, Josh Allen age is live from birth date."""
import json, sys
from datetime import date
from pathlib import Path
SITE = Path(__file__).resolve().parents[1] / "site"
fails = []
def fail(m): fails.append(m)
bio = json.loads((SITE / "player_bio.json").read_text())
josh = bio.get("3918298") or {}
if not josh: fail("Josh Allen missing from player_bio")
birth = josh.get("birth")
if birth != "1996-05-21":
    fail(f"Josh Allen birth {birth}")
# live age is computed in the browser from birth vs today — not a frozen Sept 1 table
cjs = (SITE / "common.js").read_text()
if "function ageOn" not in cjs:
    fail("common.js missing live ageOn")
if "ageByYear && rec.ageByYear" in cjs:
    fail("playerBio still reads frozen ageByYear")
if "onNextMidnight" not in cjs:
    fail("no midnight refresh")
y,m,d = [int(x) for x in birth.split("-")]
b = date(y,m,d); a = date.today()
years = a.year - b.year - ((a.month, a.day) < (b.month, b.day))
print(f"Josh Allen is {years} today ({birth})")
logo = SITE / "logos/nfl/buf.png"
if not logo.exists() or logo.stat().st_size < 500:
    fail("BUF logo missing")
html = (SITE / "draft.html").read_text()
js = (SITE / "draft.js").read_text()
pjs = (SITE / "players.js").read_text()
cjs = (SITE / "common.js").read_text()
if 'id="age-block"' not in html: fail("draft age block missing")
if "renderAge" not in js: fail("renderAge missing")
if "nflLogoHTML" not in cjs: fail("nflLogoHTML missing")
if "nflLogoHTML" not in pjs: fail("player profile missing NFL logo")
if "age today" not in pjs: fail("player profile missing live age")
if "age-asof" not in html: fail("as-of date input missing")
if "onNextMidnight" not in js: fail("draft.js missing midnight tick")
if "auction-lab" in html.lower() and 'class="on"' in html:
    pass
nav = html
if "Auction Lab" in nav:
    fail("Auction Lab leaked into Draft nav")

print("FAIL" if fails else "PASS")
[print(" -", f) for f in fails]
sys.exit(1 if fails else 0)
