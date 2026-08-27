#!/usr/bin/env python3
"""CHI-129 — nflsavant look on existing AFFL Savant, CHI-127 locks held.

Gates:
- savant.html keeps the shared AFFL nav and required explorer IDs
- light nflsavant chrome is scoped (body.sv + savant.css)
- scoring stays std / non-PPR; no PPR option ships
- default season is All / career; Auction $ is an X/Y metric
- dots default to franchise color; table identity is a color bar, not a logo
- 2014–15 bids stay unavailable (null), never coerced to $0
- empty stays empty; no invented PPR / half-PPR / League Legacy scoring
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BASE = "http://127.0.0.1:8765"
fails = []


def fail(msg):
    fails.append(msg)


def get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        fail(f" - {path} not reachable on 8765: {e}")
        return ""


NAV = ["Dashboard", "Scoreboard", "Players", "Savant", "Draft", "Trades",
       "Roto", "Teams", "History", "Awards", "Dictionary", "Wrapped"]

html = get("/savant.html")
css = get("/savant.css?v=4")
js = get("/savant.js?v=8")

if html:
    if 'class="sv"' not in html and "class='sv'" not in html:
        fail(" - savant.html is not body.sv (nflsavant scoped theme)")
    if "savant.css" not in html:
        fail(" - savant.html does not load savant.css")
    labels = re.findall(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    if not labels:
        fail(" - savant.html has no .site-nav")
    else:
        got = re.findall(r"<a [^>]*>([^<]+)</a>", labels[0])
        if got != NAV:
            fail(f" - savant.html nav {got} != {NAV}")
    if 'href="savant.html" class="on"' not in html:
        fail(" - savant.html does not mark itself current")
    for need in ("sv-scatter", "x-metric", "y-metric", "view-picker", "season-picker"):
        if need not in html:
            fail(f" - savant.html missing #{need}")
    if 'id="page-home"' not in html or 'id="page-explore"' not in html:
        fail(" - savant.html missing home/explore views")
    if 'id="page-players"' not in html or 'id="page-fantasy"' not in html:
        fail(" - savant.html missing players/fantasy views")
    if 'id="page-leaderboards"' not in html or 'id="page-compare"' not in html:
        fail(" - savant.html missing leaderboards/compare views")
    if "Tale of the tape" not in html and "tale of the tape" not in html:
        fail(" - compare view is not the tale of the tape")
    if 'id="lb-week"' not in html or "Full season" not in html:
        fail(" - leaderboards missing a Full-season week lock")
    if re.search(r'option[^>]*value=["\']ppr["\']', html, re.I):
        fail(" - savant.html ships a PPR scoring option")
    if 'value="std"' not in html or "non-PPR" not in html:
        fail(" - fantasy scoring is not locked to std / non-PPR")
    if "half-PPR" in html or "half PPR" in html or "League Legacy" in html:
        fail(" - savant.html mentions League Legacy / half-PPR")

if css:
    for tok in ("--sv-teal", "--sv-card", ".sv-bar", ".sv-chip", ".sv-mast"):
        if tok not in css:
            fail(f" - savant.css missing {tok}")
    if "color-scheme: light" not in css:
        fail(" - savant.css is not a light theme")
    if ".side-menu" not in css:
        fail(" - savant.css does not suppress the Excel sheet rail")
    if "sv-heat-hi" not in css or "sv-heat-lo" not in css:
        fail(" - savant.css missing teal/rose heat chips")
    if ".sv-sq" not in css:
        fail(" - savant.css missing team color squares")
    if ".sv-pbar" not in css:
        fail(" - savant.css missing compare percentile bars")

if js:
    if "tooltip" not in js or "callbacks" not in js:
        fail(" - savant.js has no tooltip callbacks")
    if '"scatter"' not in js:
        fail(" - savant.js is not drawing a scatter")
    if 'season: ALL' not in js and 'season: "all"' not in js:
        fail(" - default season is not All")
    if 'color: "franchise"' not in js:
        fail(" - default color is not franchise")
    if 'label: "Auction $"' not in js:
        fail(" - Auction $ is not an X/Y metric")
    if "never 0" not in js and "never $0" not in js:
        fail(" - savant.js dropped the snake-year never-$0 lock")
    if "sv-bar" not in js:
        fail(" - savant.js does not paint team color bars")
    if "restoreSavantChrome" not in js:
        fail(" - savant.js does not restore the top nav from the sheet rail")
    if "nflLogoHTML" in js or "logos/nfl/" in js:
        fail(" - savant.js paints unconstrained NFL logos")
    if re.search(r"\bPPR\b", js) and "non-PPR" not in js:
        fail(" - savant.js mentions PPR without the non-PPR lock")
    if "cpoe" not in js or "empty: true" not in js:
        fail(" - leaderboards do not keep CPOE / success / aDOT empty")
    if "sqHTML" not in js:
        fail(" - compare/leaderboards do not paint team color squares")
    if "renderLeaderboards" not in js or "renderCompare" not in js:
        fail(" - savant.js missing leaderboards/compare renderers")

meta_raw = get("/savant/meta.json")
if meta_raw:
    meta = json.loads(meta_raw)
    if 2026 in meta.get("seasons", []):
        fail(" - savant meta lists 2026")
    scoring = str(meta.get("scoring") or "")
    if "PPR" in scoring and "non-PPR" not in scoring:
        fail(f" - meta scoring is not non-PPR: {scoring}")

bids_raw = get("/savant/bids.json")
if bids_raw:
    bids = json.loads(bids_raw)
    for y in ("2014", "2015"):
        bag = bids.get(y)
        if bag:
            fail(f" - bids.json has {y}; snake drafts must be omitted, never $0")
    for y, bag in bids.items():
        if not isinstance(bag, dict):
            continue
        zeros = sum(1 for v in bag.values() if v == 0 or v == 0.0)
        if zeros:
            fail(f" - {y}: {zeros} auction bids are 0; missing stays unavailable")

if fails:
    print("FAIL")
    for f in fails:
        print(f)
    sys.exit(1)

print("CHI-129: nflsavant chrome on AFFL Savant; non-PPR; All + Auction $ + franchise bars")
print("PASS")
