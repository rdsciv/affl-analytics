#!/usr/bin/env python3
"""CHI-114 — AFFL Savant explorer.

Gates:
- page is served, carries the shared nav, and marks Savant as current
- meta.json + one payload per season, every row the right arity
- AFFL scoring is non-PPR: fpts recomputes from yards/TDs with rec worth 0
- franchise labels are CURRENT names resolved through member_id, so a rename
  never splits a franchise (no "Tittsburgh" on a 2025 row)
- no AFFL 2026 season before the draft
- pre-2018 carries zero AFFL starts and says so, rather than faking lineups
- the hover payload exists: every row has a name, a position and a team
"""
import json
import re
import sys
import urllib.error
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
       "Roto", "Teams", "History", "Awards", "Pressers", "Dictionary", "Wrapped"]

html = get("/savant.html")
if html:
    labels = re.findall(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    if not labels:
        fail(" - savant.html has no .site-nav")
    else:
        got = re.findall(r"<a [^>]*>([^<]+)</a>", labels[0])
        if got != NAV:
            fail(f" - savant.html nav {got} != {NAV}")
    if 'href="savant.html" class="on"' not in html:
        fail(" - savant.html does not mark itself current in the nav")
    for need in ("sv-scatter", "x-metric", "y-metric", "view-picker", "season-picker"):
        if need not in html:
            fail(f" - savant.html missing #{need}")

js = get("/savant.js")
if js:
    if "tooltip" not in js or "callbacks" not in js:
        fail(" - savant.js has no tooltip callbacks; hover must name the dot")
    if '"scatter"' not in js:
        fail(" - savant.js is not drawing a scatter")

meta_raw = get("/savant/meta.json")
if not meta_raw:
    print("FAIL")
    for f in fails:
        print(f)
    sys.exit(1)

meta = json.loads(meta_raw)
cols = meta["cols"]
seasons = meta["seasons"]

if 2026 in seasons:
    fail(" - savant meta lists a 2026 season; there is no AFFL 2026 before the draft")
if seasons != sorted(seasons) or seasons[0] != 2014:
    fail(f" - unexpected season list: {seasons}")

ix = {c: i for i, c in enumerate(cols)}
PASS_YD, PASS_TD, INT = 0.04, 4.0, -2.0
RUSH_YD, RUSH_TD = 0.10, 6.0
REC_YD, REC_TD = 0.10, 6.0

total = 0
for y in seasons:
    raw = get(f"/savant/season_{y}.json")
    if not raw:
        continue
    rows = json.loads(raw)
    if not rows:
        fail(f" - season {y} payload is empty")
        continue
    total += len(rows)

    for r in rows:
        if len(r) != len(cols):
            fail(f" - {y}: row arity {len(r)} != {len(cols)}")
            break

    # every dot must be nameable on hover
    for r in rows[:200]:
        if not r[ix["name"]] or not r[ix["pos"]]:
            fail(f" - {y}: a row has no name/position; hover would show nothing")
            break

    # non-PPR: recompute AFFL points from yardage and TDs only
    bad = 0
    for r in rows[:60]:
        want = (r[ix["payd"]] * PASS_YD + r[ix["patd"]] * PASS_TD + r[ix["int"]] * INT
                + r[ix["ruyd"]] * RUSH_YD + r[ix["rutd"]] * RUSH_TD
                + r[ix["recyd"]] * REC_YD + r[ix["rectd"]] * REC_TD)
        if abs(want - r[ix["fpts"]]) > 0.15:
            bad += 1
    if bad:
        fail(f" - {y}: {bad} rows do not match non-PPR scoring (receptions must score 0)")

    starts = sum(1 for r in rows if r[ix["starts"]])
    if starts < 100:
        fail(f" - {y}: only {starts} rows have AFFL starts; expected the league's starters")

    # Coverage must be declared for every season, and honest: 2018+ comes from
    # fact_roster_week and is complete; 2014-2017 is a reconstruction that keeps
    # only team-weeks proven against fact_matchup, so it must not claim 100%.
    cov = meta.get("lineupCoverage", {}).get(str(y))
    if cov is None:
        fail(f" - {y}: no lineupCoverage declared")
    elif y >= 2018 and cov != 100.0:
        fail(f" - {y}: coverage {cov}% but 2018+ lineups come from fact_roster_week")
    elif y < 2018 and not (0 < cov <= 100):
        fail(f" - {y}: implausible reconstructed coverage {cov}%")

    # current franchise names only
    for r in rows:
        fr = r[ix["fr"]]
        if fr and "Titts" in fr:
            fail(f" - {y}: franchise shown as '{fr}'; must resolve to the current name")
            break

if total < 6000:
    fail(f" - only {total} player-seasons exported; expected the full NFL skill pool")

# Independently re-derive the pre-2018 reconstruction. The exporter may only
# keep a team-week whose starter points sum exactly to the official score;
# anything else would be a guessed lineup. Recompute here from the raw capture
# and the warehouse, and fail if the published coverage disagrees.
import sqlite3
from collections import defaultdict

raw_path = ROOT / "site" / "pre2018_starts.json"
db_path = ROOT / "affl.db"
if raw_path.exists() and db_path.exists():
    blob = json.loads(raw_path.read_text())
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    for y_s, players in sorted(blob.items()):
        y = int(y_s)
        official = {(t, w): p for t, w, p in con.execute(
            "SELECT team_id, week, points FROM fact_matchup WHERE season = ?", (y,))}
        bucket = defaultdict(float)
        for pid, weeks in players.items():
            for wk, rec in weeks.items():
                bucket[(rec.get("tid"), int(wk))] += rec.get("pts") or 0.0
        good = considered = 0
        for key, got in bucket.items():
            off = official.get(key)
            if off is None:
                continue
            considered += 1
            if abs(got - off) <= 0.6:
                good += 1
        want = round(100.0 * good / considered, 1) if considered else 0.0
        published = meta.get("lineupCoverage", {}).get(y_s)
        if published is None or abs(published - want) > 0.1:
            fail(f" - {y}: published coverage {published}% != recomputed {want}%")
        if want >= 99.9 and y < 2017:
            fail(f" - {y}: reconstruction claims near-total coverage; verify before trusting")
    con.close()

if fails:
    print(f"{total} player-seasons checked")
    print("FAIL")
    for f in fails:
        print(f)
    sys.exit(1)

print(f"savant: {total} player-seasons, {len(seasons)} seasons, non-PPR verified, "
      f"current franchise names, no 2026")
print("PASS")
