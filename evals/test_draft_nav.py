#!/usr/bin/env python3
"""CHI-53 / AFFL-033: Draft page FantasyGenius navigability.

ADD-ONLY. BOARD/TABLE toggle, position chips, sortable headers,
player/franchise links, FG sections. Existing draft lab / overview / recap stay.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def fail(msg):
    fails.append(msg)


def canon(i):
    return MERGE.get(str(i), str(i))


def main():
    html = (SITE / "draft.html").read_text()
    js = (SITE / "draft.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years/2025.json").read_text())
    bio = json.loads((SITE / "player_bio.json").read_text())

    # --- cache ---
    if "draft.js?v=17" not in html:
        fail("draft.html did not bump draft.js cache to v=17")
    if "styles.css?v=16" not in html and "styles.css?v=15" not in html:
        fail("draft.html missing styles.css cache bust")

    # --- BOARD / TABLE toggle ---
    if 'data-view="board"' not in html or 'data-view="table"' not in html:
        fail("draft.html missing BOARD/TABLE toggle")
    if "BOARD" not in html or "TABLE" not in html:
        fail("draft.html missing BOARD/TABLE labels")
    if "S.view" not in js or 'view: "table"' not in js and "view: 'table'" not in js:
        fail("draft.js missing default TABLE view")
    if "function renderNavBoard" not in js and "function buildNavGrid" not in js:
        fail("draft.js missing franchise x round board builder")
    if "nav-board" not in html or "nav-board" not in css:
        fail("missing nav-board grid markup/css")
    if "franchise" not in js.lower() or "round" not in js:
        fail("board is not described as franchise x round")
    if "rounds of 12" not in js and "overall" not in js:
        fail("auction board missing overall-into-rounds-of-12 path")

    # --- position chips ---
    chips = ["ALL", "QB", "RB", "WR", "TE", "K", "DST"]
    for c in chips:
        if f'data-pos="{c}"' not in html:
            fail(f"draft.html missing position chip {c}")
    if "board-pos-chips" not in html or "S.pos" not in js:
        fail("position chips not wired")

    # --- sortable headers ---
    if "thead th.s" not in css and "th.s" not in css:
        fail("styles.css missing sortable header rules")
    if "bindAllDraftSorts" not in js and "bindNavTableSort" not in js:
        fail("draft.js missing generic table sort")
    if 'data-k="overall"' not in html or 'data-k="name"' not in html:
        fail("board table headers are not click-sortable")
    if html.count('class="s"') < 20:
        fail(f"too few sortable headers: {html.count('class=\"s\"')}")

    # --- links ---
    if "A.playerLink" not in js:
        fail("player names are not A.playerLink / players.html?pid= links")
    common = (SITE / "common.js").read_text()
    if "players.html" not in common or "pid" not in common:
        fail("common.js playerLink does not target players.html?pid=")
    if "teams.html?squad=" not in js:
        fail("franchise names are not teams.html?squad= links")
    if "function teamLink" not in js:
        fail("draft.js missing teamLink")

    # --- existing sections still present ---
    for needle in (
        "Draft Lab",
        "Draft Overview",
        "The Board",
        "Visual board",
        "Spend vs Return",
        "Value Board",
        "Franchise Draft",
        "id=\"draft-lab\"",
        "id=\"draft-overview\"",
        "id=\"draft-recap\"",
        "id=\"lab-board\"",
    ):
        if needle not in html:
            fail(f"existing draft section missing: {needle}")
    if "Draft War" in html or "Draft War" in js:
        if "Draft War" not in html:
            fail("Draft War string was removed")
    if "all-time" not in html.lower() and "All-time" not in html:
        fail("all-time value section string missing")
    if "function renderLab" not in js or "function renderOverview" not in js:
        fail("existing lab/overview renderers missing")
    if "function renderRecap" not in js:
        fail("franchise recap renderer missing")

    # --- new FG sections ---
    for sid in ("fg-awards", "fg-heatmap", "fg-stacks", "fg-college", "fg-homers", "fg-cuffs", "fg-age-scatter"):
        if f'id="{sid}"' not in html:
            fail(f"draft.html missing #{sid}")
    if "DOUBLE" not in js or "TRIPLE" not in js:
        fail("stacks missing DOUBLE/TRIPLE labels")
    if "pass-catcher" not in js and "QB stack" not in js:
        fail("QB + pass-catcher stacks missing")
    if "handcuff" not in js.lower():
        fail("handcuffs missing")
    if "heatMode" not in js or "PICKS" not in html or "AGE" not in html:
        fail("strategy heatmap missing PICKS/AGE toggle")
    if "homerMode" not in js or "FRANCHISE" not in html:
        fail("homers missing FRANCHISE/NFL toggle")
    if "function renderFgAgeScatter" not in js or "A.ageOn" not in js and "p.age" not in js:
        fail("age-of-team scatter missing")
    if "player_bio" not in html and "player_bio" not in js:
        fail("age scatter does not mention player_bio")

    # --- identity ---
    if "Tittsburgh" in html or "Tittsburgh" in js:
        fail("Tittsburgh leaked onto the draft page")
    if "function ownerKey" not in js or "A.canon" not in js:
        fail("MERGE / ownerKey missing")
    members = data.get("members") or {}
    for name in ("Jason Kafka", "Tanner Dunn", "Patrick O'Neill", "Alex Renney"):
        if name in html:
            fail(f"owner name {name} appears in draft.html")

    # --- real 2025 data (do not invent) ---
    board = (y2025.get("draft") or {}).get("board") or []
    print(f"2025 board picks={len(board)} auction={y2025.get('draft', {}).get('auction')}")
    if len(board) < 100:
        fail("2025 board too small to grid")
    teams = (data.get("seasons") or {}).get("2025", {}).get("teams") or []
    owner_of = {t["id"]: canon(t.get("owner")) for t in teams}
    nfl_g = defaultdict(list)
    col_g = defaultdict(list)
    cuff_g = defaultdict(list)
    for p in board:
        oid = owner_of.get(p.get("tid")) or owner_of.get(int(p.get("tid") or 0))
        if not oid:
            continue
        nfl = p.get("nfl")
        pos = "DST" if p.get("pos") == "D/ST" else p.get("pos")
        if nfl:
            nfl_g[(oid, nfl)].append(p)
            if pos:
                cuff_g[(oid, nfl, pos)].append(p)
        rec = bio.get(str(p.get("pid"))) or {}
        college = rec.get("college")
        if college:
            col_g[(oid, college)].append(p)
    nfl2 = sum(1 for v in nfl_g.values() if len(v) >= 2)
    nfl3 = sum(1 for v in nfl_g.values() if len(v) >= 3)
    col2 = sum(1 for v in col_g.values() if len(v) >= 2)
    cuff2 = sum(1 for v in cuff_g.values() if len(v) >= 2)
    qbpc = 0
    for (oid, nfl), picks in nfl_g.items():
        if len(picks) < 2:
            continue
        poss = {("DST" if x.get("pos") == "D/ST" else x.get("pos")) for x in picks}
        if "QB" in poss and (poss & {"WR", "TE"}):
            qbpc += 1
    print(f"2025 NFL 2+ stacks={nfl2} 3+={nfl3} college 2+={col2} handcuffs={cuff2} QB+WR/TE={qbpc}")
    if nfl2 and "function renderFgStacks" not in js:
        fail("2025 has NFL stacks but renderer missing")
    if col2 and "function renderFgCollege" not in js:
        fail("2025 has college stacks but renderer missing")
    if cuff2 and "function renderFgCuffs" not in js:
        fail("2025 has handcuffs but renderer missing")

    # color by position
    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        if f"pos-{pos}" not in css and f"pos-{pos}" not in js:
            fail(f"board cells not color-coded for {pos}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/draft.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"draft.html HTTP {code}")
        else:
            print("draft.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
