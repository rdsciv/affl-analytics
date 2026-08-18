#!/usr/bin/env python3
"""CHI-51 / weekly bars: #pl-chart paints any year chip; #pl-career-chart exists."""
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

    if 'id="pl-chart"' not in html:
        fail("players.html missing #pl-chart")
    if 'id="pl-career-chart"' not in html:
        fail("players.html missing #pl-career-chart")
    if html.find('id="pl-career-chart"') < html.find('id="pl-chart"'):
        fail("#pl-career-chart must sit under the weekly #pl-chart card, not replace it")

    if "function renderChart" not in js:
        fail("players.js missing renderChart")
    if "function renderCareerChart" not in js:
        fail("players.js missing renderCareerChart")

    chart_fn = js.split("function renderChart", 1)[-1].split("function renderCareerChart", 1)[0]
    career_fn = js.split("function renderCareerChart", 1)[-1].split("function ngsSeries", 1)[0]
    load_fn = js.split("async function loadPlayer", 1)[-1].split("function renderYearChips", 1)[0]
    chips_fn = js.split("function renderYearChips", 1)[-1].split("function seasonXtd", 1)[0]

    if "A.years()[0]" in chart_fn:
        fail("renderChart is gated to A.years()[0] (latest year only)")
    if "logYear" not in chart_fn and "rows" not in chart_fn:
        fail("renderChart does not use the year-chip rows")
    if "loadPlayer" not in chips_fn:
        fail("year chips do not reload the player (weekly bars will not repaint)")
    if "data-y" not in chips_fn:
        fail("year chips missing data-y")
    if load_fn.find("setPageMode") == -1 or load_fn.find("renderChart") == -1:
        fail("loadPlayer missing setPageMode or renderChart")
    elif load_fn.find("setPageMode") > load_fn.find("renderChart"):
        fail("renderChart runs before setPageMode(profile); hidden canvas stays blank")
    if "renderCareerChart" not in load_fn:
        fail("loadPlayer does not paint the career bar chart")
    if "careerRows" not in load_fn:
        fail("loadPlayer does not keep an all-years row set for the career chart")
    if "#pl-career-chart" not in career_fn and "pl-career-chart" not in career_fn:
        fail("renderCareerChart does not target #pl-career-chart")
    if "barStyle" not in career_fn:
        fail("career chart does not reuse started/benched/nfl colors")

    # FG extras must still be present
    for i in ("pl-fg-strip", "pl-custody", "pl-achievements", "pl-avg-line"):
        if f'id="{i}"' not in html:
            fail(f"FG extra #{i} was removed")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html missing players.js cache")
    elif int(bust.group(1)) < 26:
        fail(f"players.js cache still v={bust.group(1)}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        body = r.read().decode("utf-8", "replace")
        if code != 200:
            fail(f"players.html HTTP {code}")
        elif 'id="pl-chart"' not in body or 'id="pl-career-chart"' not in body:
            fail("8765 players.html missing one of the bar canvases")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("both canvases present; renderChart not latest-year-only; career chart exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
