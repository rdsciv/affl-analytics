#!/usr/bin/env python3
"""CHI-181: sitewide player profile densify (shared template). Adams is QA only."""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()
    css = (SITE / "styles.css").read_text()

    bust_js = re.search(r"players\.js\?v=(\d+)", html)
    bust_css = re.search(r"styles\.css\?v=(\d+)", html)
    if not bust_js:
        fail("players.html missing players.js cache-bust")
    elif int(bust_js.group(1)) < 55:
        fail(f"players.js cache still v={bust_js.group(1)}")
    if not bust_css:
        fail("players.html missing styles.css cache-bust")
    elif int(bust_css.group(1)) < 57:
        fail(f"styles.css cache still v={bust_css.group(1)}")

    # Landing locks stay: Compare, WOPR, Database, Colleges in that source order.
    order = [html.find(s) for s in ('id="pl-compare"', 'id="wopr-persist"', 'id="pl-db"', 'id="pl-colleges"')]
    if any(i < 0 for i in order):
        fail("Compare / WOPR / Database / Colleges landing chrome missing")
    elif order != sorted(order):
        fail("Compare / WOPR / Database / Colleges source order changed")

    load_fn = js.split("async function loadPlayer", 1)[-1].split("function renderYearChips", 1)[0]
    if re.search(r"renderChart\s*\(\s*focus\s*,\s*careerRows\s*\)", load_fn):
        fail("loadPlayer still paints careerRows on the top weekly chart (duplicate All-games)")
    if re.search(r"renderChart\s*\(\s*focus\s*,\s*rows\s*\)", load_fn):
        fail("loadPlayer still passes rows (All=careerRows) to renderChart")
    if not re.search(r"playerYears\s*\([^)]*\)\s*\[\s*0\s*\]", load_fn):
        fail("All-years top chart is not latest year (playerYears(...)[0])")
    if "renderCareerChart(focus, careerRows)" not in load_fn:
        fail("career weekly chart must still receive careerRows")
    if "renderChart(focus, chartRows)" not in load_fn:
        fail("top weekly chart must use chartRows")

    hero = html.find('id="pl-hero"')
    strip = html.find('id="pl-fg-strip"')
    weekly = html.find('id="pl-chart"')
    career = html.find('id="pl-career-chart"')
    chi = html.find('id="pl-chi114"')
    if min(hero, strip, weekly, career, chi) < 0:
        fail("profile sections missing hero / strip / weekly / career / chi114")
    elif not (hero < strip < weekly < career < chi):
        fail("first screen order must be hero → career strip → weekly → career chart → CHI-114 later")

    if 'class="players-pack"' not in html:
        fail("players.html body missing players-pack")
    if 'id="squad-row"' not in html:
        fail("team picker row missing #squad-row (needed to hide on profile)")
    if "profile-mode" not in js:
        fail("setPageMode does not toggle profile-mode")
    if 'hide("#year-row"' not in js and "hide('#year-row'" not in js:
        fail("profile mode does not hide the season picker")
    if 'hide("#squad-row"' not in js and "hide('#squad-row'" not in js:
        fail("profile mode does not hide the team picker")

    if "resolvePlayerName" not in js:
        fail("players.js does not use resolvePlayerName")
    if re.search(r'name:\s*m\.name\s*\|\|\s*md\.name\s*\|\|\s*\(["\']#["\']\s*\+\s*pid\)', js):
        fail("stubPlayer still paints #espnId")
    if re.search(r'["\']Player ["\']\s*\+\s*pid', js) or "Player ${" in js:
        fail("players.js still paints Player {espnId}")
    if re.search(r"\b16800\b", js) or re.search(r"\bAdams\b", js):
        fail("players.js has Adams/pid-specific profile logic; densify must be the shared path")
    if "affl_career_starts.json" not in js:
        fail("leaders/career book must still read affl_career_starts.json")
    if 'hide("#pl-compare", true)' not in js or 'hide("#wopr-persist", true)' not in js:
        fail("Compare/WOPR must stay hidden on landing")
    if "hide(\"#pl-colleges\", profile)" not in js and "hide('#pl-colleges', profile)" not in js:
        fail("Colleges must remain landing-only (under leaders)")
    if "yearN <= 1" not in js and "years.size <= 1" not in js:
        fail("single-season profiles must hide the duplicate career chart")

    if "function weekLabel" not in js:
        fail("players.js missing weekLabel (blank chart ticks)")

    if "CHI-181" not in css:
        fail("styles.css missing CHI-181 density block")
    if "profile-mode #year-row" not in css:
        fail("CSS does not hide landing pickers on profile")
    if "#pl-chi114 .chart-wrap.tall { height: 200px; }" not in css and "height: 200px" not in css:
        fail("CHI-114 profile charts were not shortened")
    for needle in ("max-width: 72px", "max-height: 72px", "max-width: 28px", "max-height: 22px"):
        if needle not in css.split("CHI-181", 1)[-1]:
            fail(f"CHI-181 density block missing logo cap {needle}")

    for i in ("pl-hero", "pl-chart", "pl-career-chart", "pl-journey", "pl-fg-strip",
              "pl-custody", "pl-achievements", "pl-avg-line", "pl-compare", "wopr-persist"):
        if f'id="{i}"' not in html:
            fail(f"existing #{i} was removed")

    for path in (
        "/players.html?pid=16800&log=all",
        "/players.html?pid=4040715&log=all",
        "/players.html",
    ):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8765" + path, timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            body = r.read().decode("utf-8", "replace")
            if code != 200:
                fail(f"{path} HTTP {code}")
            elif 'id="pl-chart"' not in body or "players.js?v=55" not in body:
                fail(f"8765 {path} missing weekly canvas or v=55")
            elif 'id="pl-db"' not in body or 'id="pl-colleges"' not in body:
                fail(f"8765 {path} lost landing leaders/colleges chrome")
            else:
                print(path, "HTTP 200")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{path} not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-181: latest-year top chart; career chart kept; first-screen order packed; cache v=55/57")
    return 0


if __name__ == "__main__":
    sys.exit(main())
