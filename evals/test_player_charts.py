#!/usr/bin/env python3
"""CHI-51 / CHI-181: one weekly bar chart; year chips switch range; All = career weeks."""
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
    if 'id="pl-career-chart"' in html:
        fail("redundant #pl-career-chart is still in players.html")

    if "function renderChart" not in js:
        fail("players.js missing renderChart")
    if "function renderCareerChart" in js:
        fail("players.js still has renderCareerChart")

    chart_fn = js.split("function renderChart", 1)[-1].split("function ngsSeries", 1)[0]
    load_fn = js.split("async function loadPlayer", 1)[-1].split("function renderYearChips", 1)[0]
    chips_fn = js.split("function renderYearChips", 1)[-1].split("function seasonXtd", 1)[0]

    if "A.years()[0]" in chart_fn:
        fail("renderChart is gated to A.years()[0] (latest year only)")
    if "logYear" not in chart_fn and "rows" not in chart_fn:
        fail("renderChart does not use the year-chip rows")
    if "weekLabel(r, logYear === \"all\")" not in chart_fn and "weekLabel(r, logYear === 'all')" not in chart_fn:
        fail("All/career weeks are not year-prefixed on the weekly chart")
    if "loadPlayer" not in chips_fn:
        fail("year chips do not reload the player (weekly bars will not repaint)")
    if "data-y" not in chips_fn:
        fail("year chips missing data-y")
    if load_fn.find("setPageMode") == -1 or load_fn.find("renderChart") == -1:
        fail("loadPlayer missing setPageMode or renderChart")
    elif load_fn.find("setPageMode") > load_fn.find("renderChart"):
        fail("renderChart runs before setPageMode(profile); hidden canvas stays blank")
    if "careerRows" not in load_fn:
        fail("loadPlayer does not keep an all-years row set")
    if re.search(r"playerYears\s*\([^)]*\)\s*\[\s*0\s*\]", load_fn):
        fail("All still filters the weekly chart to the latest year")
    if "chartRows" in load_fn:
        fail("loadPlayer still builds chartRows (latest-year subset)")
    if "renderChart(focus, rows)" not in load_fn and not re.search(
        r"renderChart\s*\(\s*focus\s*,\s*rows\s*\)", load_fn
    ):
        fail("renderChart is not called with rows (All = career weeks)")
    if "logYear === \"all\"" not in load_fn and "logYear === 'all'" not in load_fn:
        fail("loadPlayer no longer branches on All")

    for i in ("pl-fg-strip", "pl-custody", "pl-achievements", "pl-avg-line"):
        if f'id="{i}"' not in html:
            fail(f"FG extra #{i} was removed")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html missing players.js cache")
    elif int(bust.group(1)) < 31:
        fail(f"players.js cache still v={bust.group(1)}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        body = r.read().decode("utf-8", "replace")
        if code != 200:
            fail(f"players.html HTTP {code}")
        elif 'id="pl-chart"' not in body:
            fail("8765 players.html missing the weekly canvas")
        elif 'id="pl-career-chart"' in body:
            fail("8765 players.html still has the redundant career canvas")
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
    print("one weekly canvas; All = career weeks; year chips reload the chart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
