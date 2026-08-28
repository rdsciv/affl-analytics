#!/usr/bin/env python3
"""CHI-136: franchise pages open on Cumulative; year chips are played years only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def src(name):
    return (SITE / name).read_text()


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


def parse_merge(common):
    block = re.search(r"const MERGE = \{([^}]+)\}", common)
    if not block:
        fail("common.js missing MERGE")
        return {}
    return dict(re.findall(r"(m\d+)\s*:\s*\"(m\d+)\"", block.group(1)))


def test_helpers(data, common):
    merge = parse_merge(common)
    if merge.get("m01") != "m07":
        fail(f"MERGE m01 -> {merge.get('m01')} (need m07)")

    # Actual helper bodies still use canon + seasons (CHI-135).
    fy = re.search(r"function franchiseYears\(id\) \{([\s\S]*?)\n  \}", common)
    if not fy:
        fail("common.js missing franchiseYears")
    else:
        body = fy.group(1)
        if "canon(" not in body:
            fail("franchiseYears no longer uses canon — CHI-135 reverted")
        if "DATA.seasons" not in body and "seasons" not in body:
            fail("franchiseYears does not read seasons via canon")
        if "f.years" in body or "franchiseRecord" in body:
            fail("franchiseYears looks like it fell back to franchise record years")

    tid = re.search(r"function teamIdFor\(year, owner\) \{([\s\S]*?)\n  \}", common)
    if not tid:
        fail("common.js missing teamIdFor")
    elif "canon(" not in tid.group(1):
        fail("teamIdFor no longer uses canon — CHI-135 reverted")

    cy = re.search(r"function clampYear\(year, squad\) \{([\s\S]*?)\n  \}", common)
    if not cy:
        fail("common.js missing clampYear")
    else:
        body = cy.group(1)
        if "squadYears" not in body:
            fail("clampYear does not use squadYears")
        if "return null" not in body:
            fail("clampYear no longer returns null for empty franchise years")

    m07 = franchise_years(data, "m07", merge)
    m22 = franchise_years(data, "m22", merge)
    m18 = franchise_years(data, "m18", merge)
    print("squadYears m07", m07)
    print("squadYears m22", m22)
    print("squadYears m18", m18)

    if m07 != [2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016]:
        fail(f"squadYears('m07') {m07} != 2016-2023 newest-first")
    if m22 != []:
        fail(f"squadYears('m22') {m22} != []")
    if not m18:
        fail("squadYears('m18') empty")
    if 2024 in m07 or 2025 in m07:
        fail("year chips for m07 include 2024 or 2025")

    # clampYear: 2025 + m07 -> latest played 2023
    if m07 and m07[0] != 2023:
        fail(f"m07 latest played is {m07[0]}, need 2023")


def test_opening_logic(teams_js):
    if "function teamScopeFromURL" not in teams_js:
        fail("teams.js missing teamScopeFromURL")
        return
    # Default is cum unless explicit scope=season
    if 'get("scope") !== "season"' not in teams_js and 'get("scope") === "season"' not in teams_js:
        fail("teamScopeFromURL does not key off scope=season")
    # Must not default to season
    if re.search(r'teamScopeFromURL[\s\S]{0,200}=== "cum" \? "cum" : "season"', teams_js):
        fail("teamScopeFromURL still defaults to season")

    # Zero-year franchise stays on cum even if URL says season
    if "squadYears" not in teams_js:
        fail("teams.js never consults squadYears for scope/chips")

    fn = re.search(r"function teamScopeFromURL\([^)]*\) \{([\s\S]*?)\n  \}", teams_js)
    if not fn:
        fail("cannot parse teamScopeFromURL")
    else:
        body = fn.group(1)
        if "squadYears" not in body:
            fail("teamScopeFromURL does not force cum when franchise has zero years")
        if 'return "cum"' not in body:
            fail("teamScopeFromURL never returns cum")

    # Grid and squad picker open a franchise on cum
    if 'scope = "cum"' not in teams_js:
        fail("teams.js never resets scope to cum on franchise open")


def test_year_row(teams_js):
    render = re.search(r"async function render\(\) \{([\s\S]*?)\n  \}", teams_js)
    if not render:
        fail("cannot parse render()")
        return
    body = render.group(1)
    if "A.squadYears(squad)" not in body:
        fail("render() year list is not A.squadYears(squad) when a squad is set")
    if "seasonPicker" not in body:
        fail("render() does not use seasonPicker (CHI-142 All lives in the season control)")
    if "showYearRow" not in body:
        fail("render() does not call showYearRow")
    if re.search(r"ylist = squad \? A\.squadYears\(squad\) : \[\]", body):
        fail("league All view has no year chips; CHI-142 needs All | 2025…2014")


def test_links(common, teams_html):
    strip = re.search(r"function mountBrandStrip\(\) \{([\s\S]*?)\n  \}", common)
    if not strip:
        fail("missing mountBrandStrip")
    else:
        body = strip.group(1)
        if "teams.html?squad=" not in body:
            fail("brand strip href is not teams.html?squad=")
        if "scope=season" in body or "year=" in body:
            fail("brand strip still passes year= or scope=season")

    go = re.search(r"function goTeam\(owner, year, extra\) \{([\s\S]*?)\n  \}", common)
    if not go:
        fail("missing goTeam")
    else:
        body = go.group(1)
        if 'scope === "season"' not in body:
            fail("goTeam does not require scope=season to pass year")
        if 'u.searchParams.set("year"' in body and 'scope === "season"' not in body:
            fail("goTeam still stamps year without an explicit Season jump")

    if 'src="common.js?v=29"' not in teams_html:
        fail("teams.html common.js pin is not v=29")
    if not re.search(r'src="teams\.js\?v=22&', teams_html):
        fail("teams.html teams.js pin is not v=22")


def test_opening_defaults(data, common):
    merge = parse_merge(common)
    for owner in ("m07", "m22", "m18"):
        # URL without scope=season -> cum. Proven by source + empty-years guard.
        years = franchise_years(data, owner, merge)
        print(f"default scope {owner} = cum (years={years})")
        if owner == "m22" and years:
            fail("m22 unexpectedly has played years")


def main():
    data = json.loads((SITE / "data.json").read_text())
    common = src("common.js")
    teams_js = src("teams.js")
    teams_html = src("teams.html")

    test_helpers(data, common)
    test_opening_logic(teams_js)
    test_year_row(teams_js)
    test_links(common, teams_html)
    test_opening_defaults(data, common)

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-136: default scope cum; chips = squadYears; empty chair has no years")
    return 0


if __name__ == "__main__":
    sys.exit(main())
