#!/usr/bin/env python3
"""CHI-142: Season All|year and Team All|name, both default All.

Fails if All+year are both selected, if Players/Trades still render a year-chip
row (All + 2014–2025 pills) instead of one Season <select>, if the
Cumulative|Season toggle still exists on the required pages, if the word
squad appears in the new chrome, or if the default is not All/All.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []

REQUIRED = (
    "history.html",
    "teams.html",
    "trades.html",
    "savant.html",
    "players.html",
    "draft.html",
)
CHEAP = ("awards.html", "index.html")
PAGES = REQUIRED + CHEAP


def fail(msg):
    fails.append(msg)


def src(name):
    return (SITE / name).read_text()


def parse_merge(common):
    block = re.search(r"const MERGE = \{([^}]+)\}", common)
    if not block:
        fail("common.js missing MERGE")
        return {}
    return dict(re.findall(r"(m\d+)\s*:\s*\"(m\d+)\"", block.group(1)))


def franchise_years(data, owner, merge):
    def canon(i):
        if i is None or i == "":
            return i
        return merge.get(str(i), str(i))

    c = canon(owner)
    out = []
    for y, s in (data.get("seasons") or {}).items():
        teams = (s or {}).get("teams") or []
        if any(canon(t.get("owner")) == c for t in teams):
            out.append(int(y))
    return sorted(out, reverse=True)


def test_common(common):
    if "function seasonSelect" not in common:
        fail("common.js missing seasonSelect")
    if "function seasonPicker" not in common:
        fail("common.js missing seasonPicker")
    if "function seasonFromURL" not in common:
        fail("common.js missing seasonFromURL")
    fn = re.search(r"function seasonSelect\(el, year, onPick, yearList\) \{([\s\S]*?)\n  \}", common)
    if not fn:
        fail("cannot parse seasonSelect")
    else:
        body = fn.group(1)
        if "season-chip" in body or "data-y=\"all\">All</button>" in body:
            fail("seasonSelect still paints year chips")
        if "<select" not in body and "tagName === \"SELECT\"" not in body:
            fail("seasonSelect does not paint a Season <select>")
        if 'value="all"' not in body and ">All</option>" not in body:
            fail("seasonSelect does not paint an All option")
        if "allOn" not in body:
            fail("seasonSelect does not gate All vs year with a single selected")
        if "selected" not in body:
            fail("seasonSelect does not mark only one option selected")
        if "n > 2025" not in body and "n <= 2025" not in body:
            fail("seasonSelect does not lock out 2026")
        if "n >= 2014" not in body:
            fail("seasonSelect does not start at 2014")

    url = re.search(r"function seasonFromURL\(\) \{([\s\S]*?)\n  \}", common)
    if not url:
        fail("cannot parse seasonFromURL")
    else:
        body = url.group(1)
        if "return null" not in body:
            fail("seasonFromURL does not default All (null) on a bare URL")
        if 'get("year")' not in body:
            fail("seasonFromURL does not read ?year=")

    if "All squads" in common:
        fail("common.js chrome still says All squads")
    if 'aria-label="Squad"' in common:
        fail("common.js picker still labeled Squad")
    if 'aria-label="Team"' not in common:
        fail("common.js team picker is not labeled Team")
    picker = re.search(r"function squadPicker\(el, squad, onPick\) \{([\s\S]*?)\n  \}", common)
    if not picker:
        fail("common.js missing squadPicker")
    else:
        body = picker.group(1)
        if "All squads" in body:
            fail("squadPicker still paints All squads")
        if ">All</option>" not in body:
            fail("squadPicker default option is not All")
        if "squad" in body.lower() and "All squads" in body:
            fail("squadPicker chrome still uses squad")

    from_url = re.search(r"function squadFromURL\(\) \{([\s\S]*?)\n  \}", common)
    if not from_url:
        fail("common.js missing squadFromURL")
    else:
        body = from_url.group(1)
        if "localStorage.getItem" in body:
            fail("squadFromURL still restores a team from localStorage (bare URL is not All)")
        if 'get("team")' not in body:
            fail("squadFromURL does not read ?team=")


def test_page_html(name, html):
    if 'id="scope-picker"' in html:
        fail(f"{name} still has #scope-picker (Cumulative|Season toggle)")
    if re.search(r'picker-label">\s*Squad\s*<', html):
        fail(f"{name} chrome still says Squad")
    if "All squads" in html:
        fail(f"{name} chrome still says All squads")
    if 'aria-label="Squad"' in html:
        fail(f"{name} chrome still aria-labels Squad")
    if re.search(r">Cumulative</button>", html):
        fail(f"{name} still has a Cumulative chip")
    if name != "index.html" and 'picker-label">Team<' not in html and 'for="team-picker">Team<' not in html:
        if name in REQUIRED:
            fail(f"{name} missing Team picker label")
    if name != "index.html":
        if 'picker-label">Season<' not in html and 'for="season-picker">Season<' not in html and 'id="season-picker"' not in html and 'id="year-picker"' not in html:
            fail(f"{name} missing Season control")

    if name in ("players.html", "trades.html", "history.html", "teams.html", "draft.html"):
        if 'class="week-picker" id="year-picker"' in html or re.search(r'id="year-picker"[^>]*></div>', html):
            fail(f"{name} Season is still a year-chip row (week-picker pills)")
        if not re.search(r'<select[^>]*(id="year-picker"|id="season-picker")', html):
            fail(f"{name} missing one Season <select>")
        year_pills = [y for y in range(2014, 2026) if re.search(r'<button[^>]*data-y="%d"' % y, html)]
        all_pill = re.search(r'<button[^>]*data-y="all"', html)
        if all_pill and year_pills:
            fail(f"{name} still renders All + year pills {year_pills} instead of one Season select")
        sel = re.search(r'<select[^>]*(?:id="year-picker"|id="season-picker")[^>]*>([\s\S]*?)</select>', html)
        if sel:
            opts = re.findall(r'<option[^>]*selected[^>]*>', sel.group(1))
            if len(opts) > 1:
                fail(f"{name} Season select has {len(opts)} selected options")
            if 'value="all" selected' not in sel.group(1) and "value='all' selected" not in sel.group(1):
                fail(f"{name} Season select default is not All")

    if name in ("awards.html", "index.html"):
        all_btn = re.search(r'<button[^>]*data-y="all"[^>]*>', html)
        if not all_btn:
            fail(f"{name} missing All chip")
        elif not re.search(r'\bon\b', all_btn.group(0)):
            fail(f"{name} All chip is not on by default")
        for y in range(2014, 2026):
            yb = re.search(r'<button[^>]*data-y="%d"[^>]*>' % y, html)
            if yb and re.search(r'\bon\b', yb.group(0)):
                fail(f"{name} {y} chip is on together with All")
        if "2026" in html and re.search(r'data-y="2026"', html):
            fail(f"{name} paints a 2026 chip")


def test_page_js(name, js):
    if "A.scopePicker(" in js or "scopePicker(" in js and "function scopePicker" not in js:
        if "A.scopePicker(" in js:
            fail(f"{name} still calls scopePicker (Cumulative|Season toggle)")
    if "All squads" in js:
        fail(f"{name} still paints All squads")
    if re.search(r'data-y="cum">Cumulative<', js):
        fail(f"{name} still paints a Cumulative chip")
    if name in ("teams.js", "trades.js", "draft.js", "history.js", "players.js", "awards.js"):
        if "A.seasonSelect(" not in js and "A.seasonPicker(" not in js and "seasonSelect(" not in js and "seasonPicker(" not in js:
            fail(f"{name} does not mount seasonSelect")
    if name in ("players.js", "trades.js"):
        if "A.seasonSelect(" not in js and "seasonSelect(" not in js:
            fail(f"{name} does not mount A.seasonSelect")
    if name == "app.js":
        if 'data-y="all">All</button>' not in js:
            fail("app.js does not paint All")
        if "years.includes(qsYear) ? qsYear : null" not in js:
            fail("app.js default is not All when no year query")


def test_franchise_years(data, common):
    merge = parse_merge(common)
    if merge.get("m01") != "m07":
        fail(f"MERGE m01 -> {merge.get('m01')} (need m07 Chupacabras)")
    m07 = franchise_years(data, "m07", merge)
    m22 = franchise_years(data, "m22", merge)
    m01 = franchise_years(data, "m01", merge)
    if 2024 in m07 or 2025 in m07:
        fail(f"Chupacabras year chips include unplayed years: {m07}")
    if 2016 not in m07:
        fail(f"Chupacabras missing 2016 (Glory Holes merge): {m07}")
    if m22:
        fail(f"Gabagooners have year chips {m22}; need 0 seasons")
    if m01 != m07:
        fail(f"m01 years {m01} != m07 {m07} (MERGE)")


def test_http():
    for page in PAGES:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8765/" + page, timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            if code != 200:
                fail(f"{page} HTTP {code}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{page} not reachable on 8765: {e}")


def main():
    common = src("common.js")
    data = json.loads((SITE / "data.json").read_text())
    test_common(common)
    test_franchise_years(data, common)
    for page in PAGES:
        html = src(page)
        test_page_html(page, html)
        js_name = {
            "history.html": "history.js",
            "teams.html": "teams.js",
            "trades.html": "trades.js",
            "savant.html": "savant.js",
            "players.html": "players.js",
            "draft.html": "draft.js",
            "awards.html": "awards.js",
            "index.html": "app.js",
        }[page]
        test_page_js(js_name, src(js_name))
        if "2026" in html and re.search(r'option value="2026"|data-y="2026"', html):
            fail(f"{page} offers 2026")
    test_http()

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("CHI-142: All|year + All|team, one selected, default All/All, no squad chrome")
    return 0


if __name__ == "__main__":
    sys.exit(main())
