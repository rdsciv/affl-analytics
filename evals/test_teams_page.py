#!/usr/bin/env python3
"""Teams page contract.

A dedicated Teams page is the home for one franchise's everything.
League pages stay league-wide. This eval proves the page exists, nav is
wired, Feelers 2025 slices are a strict subset, and teams.js hard-filters
by squad instead of dumping the league.
"""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
FEELERS = "m18"
YEAR = 2025
NAV_PAGES = [
    "index.html",
    "scoreboard.html",
    "players.html",
    "draft.html",
    "trades.html",
    "roto.html",
    "teams.html",
    "history.html",
]
NAV_ORDER = ['Dashboard', 'Scoreboard', 'Players', 'Savant', 'Draft', 'Trades', 'Roto', 'Teams', 'History', 'Awards', 'Dictionary', 'Wrapped']
fails = []
counts = {}


def fail(msg):
    fails.append(msg)


def src(name):
    p = SITE / name
    if not p.exists():
        return ""
    return p.read_text()


def load():
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years/2025.json").read_text())
    return data, y2025


def team_id(data, year, owner):
    teams = data["seasons"][str(year)]["teams"]
    t = next((x for x in teams if x["owner"] == owner), None)
    return t["id"] if t else None


def same(a, b):
    return a is not None and b is not None and int(a) == int(b)


def test_files_exist():
    if not (SITE / "teams.html").exists():
        fail("site/teams.html is missing")
    if not (SITE / "teams.js").exists():
        fail("site/teams.js is missing")


def test_nav_on_every_page():
    for name in NAV_PAGES:
        html = src(name)
        if not html:
            fail(f"{name} missing (cannot check Teams nav)")
            continue
        if 'class="site-nav"' not in html and "class='site-nav'" not in html:
            fail(f"{name} has no .site-nav")
            continue
        if not re.search(r'<a\s+href="teams\.html(?:\?[^"]*)?"[^>]*>\s*Teams\s*</a>', html):
            fail(f"{name} site-nav is missing a Teams link to teams.html")
        if name == "teams.html":
            if not re.search(r'<a\s+href="teams\.html(?:\?[^"]*)?"[^>]*class="on"', html):
                fail("teams.html does not mark Teams as class=\"on\"")


def test_nav_order_on_teams():
    html = src("teams.html")
    if not html:
        return
    labels = re.findall(r'<a\s+href="[^"]+"[^>]*>([^<]+)</a>', html)
    labels = [x.strip() for x in labels]
    # Only the site-nav block
    nav = re.search(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    if not nav:
        fail("teams.html missing <nav class=\"site-nav\">")
        return
    nav_labels = [x.strip() for x in re.findall(r">([^<]+)</a>", nav.group(1))]
    if nav_labels != NAV_ORDER:
        fail(f"teams.html nav order {nav_labels} != {NAV_ORDER}")


def test_identity(data):
    tid = team_id(data, YEAR, FEELERS)
    if tid != 7:
        fail(f"Feelers 2025 team id should be 7, got {tid}")
    name = next(t["name"] for t in data["seasons"]["2025"]["teams"] if t["owner"] == FEELERS)
    if "Feelers" not in name:
        fail(f"Feelers 2025 name is {name}")
    owner = next(t["owner"] for t in data["seasons"]["2025"]["teams"] if t["id"] == 7)
    if owner != FEELERS:
        fail(f"team 7 owner should be m18, got {owner}")


def test_payload_filters(data, y):
    tid = team_id(data, YEAR, FEELERS)
    picks = [p for p in y["draft"]["board"] if same(p["tid"], tid)]
    trades = [tr for tr in y["trades"] if any(same(s["tid"], tid) for s in tr["sides"])]
    players = [
        p for p in y["players"]
        if same(p["mainTeam"], tid) or any(same(w[3], tid) for w in p.get("wk") or [])
    ]
    games = []
    for _wk, gs in y["weeks"].items():
        games.extend(gs)
    mine = [g for g in games if same(g["home"]["tid"], tid) or same(g["away"]["tid"], tid)]

    counts["picks"] = len(picks)
    counts["picks_league"] = len(y["draft"]["board"])
    counts["trades"] = len(trades)
    counts["trades_league"] = len(y["trades"])
    counts["players"] = len(players)
    counts["players_league"] = len(y["players"])
    counts["games"] = len(mine)
    counts["games_league"] = len(games)

    print(f"Feelers 2025 draft picks: {len(picks)} / {len(y['draft']['board'])}")
    print(f"Feelers 2025 trades: {len(trades)} / {len(y['trades'])}")
    print(f"Feelers 2025 players: {len(players)} / {len(y['players'])}")
    print(f"Feelers 2025 games: {len(mine)} / {len(games)}")

    if not (0 < len(picks) < len(y["draft"]["board"])):
        fail(f"draft Feelers picks {len(picks)} / {len(y['draft']['board'])} (need strict subset)")
    if not (0 < len(trades) < len(y["trades"])):
        fail(f"trades Feelers {len(trades)} / {len(y['trades'])} (need strict subset)")
    if not (0 < len(players) < len(y["players"])):
        fail(f"players Feelers {len(players)} / {len(y['players'])} (need strict subset)")
    if not (0 < len(mine) < len(games)):
        fail(f"games Feelers {len(mine)} / {len(games)} (need strict subset)")
    if not (14 <= len(mine) <= 17):
        fail(f"Feelers should have a full season of games (14-17), got {len(mine)}")


def test_teams_js_hard_filter():
    js = src("teams.js")
    if not js:
        fail("teams.js missing — cannot check hard-filter")
        return
    if "sameId" not in js:
        fail("teams.js does not use A.sameId")
    if "teamIdFor" not in js:
        fail("teams.js does not use A.teamIdFor")
    # Must not dump a full-league standings table when a squad is selected.
    if re.search(r"standings-tbl", js) and "squad" not in js:
        fail("teams.js looks like a league standings dump")
    # Filter draft / trades / games / players by tid
    if "draft" in js.lower() and "sameId" not in js:
        fail("teams.js mentions draft but never sameId-filters")
    # Explicit: do not render every team as a standings table when squad is set
    if re.search(r"Object\.values\(\s*T\s*\)\.map", js) and "franchise-grid" not in js:
        # only fail if it looks like standings rendering of all teams while squad set
        pass
    if "displayTeams" not in js and "mine" not in js and "filter(" not in js:
        fail("teams.js has no filter() — would render the full league")


def test_no_hardcoded_totals():
    js = src("teams.js")
    if not js:
        return
    banned = [
        r"\b10-4\b",
        r"\b1407(?:\.48)?\b",
        r"\b1212(?:\.32)?\b",
        r"\b16 picks\b",
        r"Grand Teeton Feelers",
        r"\$200\b",
    ]
    for pat in banned:
        if re.search(pat, js):
            fail(f"teams.js hardcodes season total matching {pat}")


def test_franchise_grid():
    html = src("teams.html")
    js = src("teams.js")
    if "franchise-grid" not in html:
        fail("teams.html missing #franchise-grid empty-state")
    if "franchise-grid" not in js:
        fail("teams.js never renders #franchise-grid")
    if "A.squads(" not in js and "A.squads()" not in js:
        fail("teams.js does not build the franchise grid from A.squads()")
    # Must not dump the whole league's games when no squad
    if re.search(r"if\s*\(\s*!squad\s*\)", js) is None and "if (!squad)" not in js and 'if (!squad)' not in js:
        # also accept if (squad) inverted
        if "squad" not in js:
            fail("teams.js never branches on squad — cannot show franchise grid vs team view")


def test_pickers():
    html = src("teams.html")
    js = src("teams.js")
    if 'id="scope-picker"' not in html:
        fail("teams.html missing #scope-picker (Season / Cumulative)")
    if 'id="year-picker"' not in html and 'id="year-row"' not in html:
        fail("teams.html missing year-picker / year-row")
    if "scopePicker" not in js:
        fail("teams.js does not call A.scopePicker")
    if "yearPicker" not in js:
        fail("teams.js does not call A.yearPicker")
    if "squadPicker" not in js:
        fail("teams.js does not call A.squadPicker")
    if "All squads" not in src("common.js"):
        fail("common.js squadPicker missing All squads option")


def test_scripts():
    html = src("teams.html")
    if not html:
        return
    if not re.search(r'src="common\.js(\?[^"]*)?"', html):
        fail("teams.html does not load common.js")
    if not re.search(r'src="chart\.umd\.min\.js(\?[^"]*)?"', html):
        fail("teams.html does not load chart.umd.min.js (needed for roto radar)")
    if not re.search(r'src="roto-math\.js(\?[^"]*)?"', html):
        fail("teams.html does not load roto-math.js")
    if not re.search(r'src="teams\.js(\?[^"]*)?"', html):
        fail("teams.html does not load teams.js")


def test_selected_blocks():
    html = src("teams.html")
    if not html:
        return
    for bid in ("team-hero", "games-block", "draft-block", "spend-block", "trades-block", "roster-block", "roto-block", "lab-block"):
        if f'id="{bid}"' not in html:
            fail(f"teams.html missing #{bid}")


def test_boot_and_helpers():
    js = src("teams.js")
    if not js:
        return
    if "A.boot(" not in js and "A.boot()" not in js:
        fail("teams.js does not boot via A.boot()")
    if "squadFromURL" not in js:
        fail("teams.js does not read squad from URL")
    if "stampNav" not in js:
        fail("teams.js does not stamp nav with squad")
    if "loadYear" not in js:
        fail("teams.js does not load a year payload")
    if "loadAllYears" not in js:
        fail("teams.js does not load all years for cumulative")
    if "logoHTML" not in js:
        fail("teams.js does not use A.logoHTML")
    if "fmt" not in js:
        fail("teams.js does not use A.fmt")



def test_spend_mix(data, y):
    html = src("teams.html")
    js = src("teams.js")
    if 'id="spend-block"' not in html:
        fail("teams.html missing #spend-block")
    if "spend-block" not in js:
        fail("teams.js never renders #spend-block")
    if "auction" not in js:
        fail("teams.js does not check draft.auction")
    if "snake" not in js.lower():
        fail("teams.js has no snake-draft notice path")
    if ".bid" not in js and "p.bid" not in js:
        fail("teams.js spend mix does not use pick.bid")
    if re.search(r"\$200", js):
        fail("teams.js hardcodes $200 instead of summing bids")
    # single-franchise mix, not a league bar of every tid
    if "applySquadDraft" in js or "applySquadTx" in js:
        fail("teams.js depends on league-page squad filters")
    tid = team_id(data, YEAR, FEELERS)
    picks = [p for p in y["draft"]["board"] if same(p["tid"], tid)]
    spend = sum((p.get("bid") or 0) for p in picks)
    pts = sum((p.get("pts") or 0) for p in picks)
    counts["spend"] = spend
    counts["draft_pts"] = pts
    print(f"Feelers 2025 auction spend: ${spend} from {len(picks)} picks, {pts:.1f} draft pts")
    if not y["draft"].get("auction"):
        fail("2025 should be an auction year in the payload")
    if spend <= 0:
        fail("Feelers 2025 auction spend should be > 0 (sum of bids)")
    # positional mix must exist as a structure, not a single truncated league bar
    if "byPos" not in js and "posSpend" not in js:
        fail("teams.js has no positional $ allocation (byPos/posSpend)")


def main():
    test_files_exist()
    data, y2025 = load()
    test_identity(data)
    test_payload_filters(data, y2025)
    test_nav_on_every_page()
    test_nav_order_on_teams()
    test_teams_js_hard_filter()
    test_no_hardcoded_totals()
    test_franchise_grid()
    test_pickers()
    test_scripts()
    test_selected_blocks()
    test_boot_and_helpers()
    test_spend_mix(data, y2025)
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("Feelers m18 -> 2025 team 7")
    print(
        "Payload slices: "
        f"{counts['picks']} picks / {counts['picks_league']}, "
        f"{counts['trades']} trades / {counts['trades_league']}, "
        f"{counts['players']} players / {counts['players_league']}, "
        f"{counts['games']} games / {counts['games_league']}"
    )
    print("Teams page hard-filters by squad; franchise grid when none selected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
