#!/usr/bin/env python3
"""2014–2017 snapshot rosters: never call missing weekly rows 'not rostered'."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)
BANNED = ("not rostered", "not on an AFFL roster")


def brace_block(src, start):
    i = src.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


def fn_body(js, name):
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", js)
    if not m:
        return ""
    return brace_block(js, m.start())


def main():
    path = SITE / "pre2018_rosters.json"
    if not path.exists():
        fail("site/pre2018_rosters.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    data = json.loads(path.read_text())
    ben = ((data.get("2014") or {}).get("5536") or {})
    print(f"2014 pid 5536: tid={ben.get('tid')} owner={ben.get('owner')} draftTid={ben.get('draftTid')} slot={ben.get('slot')}")
    if ben.get("tid") != 7:
        fail(f"2014 pid 5536 tid {ben.get('tid')} != 7")
    if ben.get("owner") != "m18":
        fail(f"2014 pid 5536 owner {ben.get('owner')} != m18")

    site = json.loads((SITE / "data.json").read_text())
    feelers = next((f for f in site.get("franchises") or [] if f.get("owner") == "m18"), None)
    if not feelers or "Feelers" not in (feelers.get("currentName") or ""):
        fail("franchiseName m18 is not Feelers")
    else:
        print(f"m18 currentName={feelers.get('currentName')}")

    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()

    if "pre2018_rosters.json" not in js:
        fail("players.js does not fetch pre2018_rosters.json")
    if "function isPre2018" not in js:
        fail("players.js missing isPre2018")
    if "function preSnap" not in js:
        fail("players.js missing preSnap")
    if "function heroTeamLine" not in js:
        fail("players.js missing heroTeamLine")

    if "weekly lineup not recovered" not in js and "lineup not recovered" not in js:
        fail("players.js legend/copy missing lineup not recovered")
    if "snapshot" not in js.lower():
        fail("players.js copy missing snapshot")
    if "weekly lineup not recovered" not in html and "lineup not recovered" not in html and "snapshot" not in html:
        fail("players.html legend missing lineup not recovered / snapshot")

    # phrases must not appear inside isPre2018(...) { } bodies
    for m in re.finditer(r"isPre2018\s*\(", js):
        block = brace_block(js, m.start())
        for phrase in BANNED:
            if phrase in block:
                fail(f"players.js uses '{phrase}' inside an isPre2018 branch")

    # and must not share a source line with a year < 2018 test
    for i, line in enumerate(js.splitlines(), 1):
        if "< 2018" in line or "isPre2018(" in line:
            for phrase in BANNED:
                if phrase in line:
                    fail(f"players.js line {i} uses '{phrase}' with a pre-2018 test")

    journey = fn_body(js, "renderJourney")
    if not journey:
        fail("renderJourney missing")
    else:
        if "isPre2018(logYear)" not in journey:
            fail("renderJourney missing isPre2018(logYear) path")
        if re.search(r"Undrafted|waiver wire", journey.split("else if (p.draft")[0] if "else if (p.draft" in journey else journey[:1800]):
            fail("pre-2018 journey path still says undrafted/waiver")
        if "tName(snapTid" not in journey and "tName(snap.tid" not in journey:
            fail("pre-2018 journey does not use tName(snap tid) for franchise")
        if "${logYear} · ${tName(snapTid" not in journey and "${logYear} · ${tName(snap.tid" not in journey:
            fail("pre-2018 journey missing 'YEAR · franchise' line")

    hero = fn_body(js, "heroTeamLine")
    if "finished with" not in hero or "tName" not in hero:
        fail("hero finished-with path missing franchise tName")
    if "Undrafted" in hero:
        fail("heroTeamLine says undrafted")

    if "players.js?v=" not in html:
        fail("players.html did not cache-bust players.js")
    if "not on an AFFL roster" not in html and "not on an AFFL roster" not in js:
        fail("2018+ three-state copy missing")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/pre2018_rosters.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail(f"pre2018_rosters.json HTTP {c2}")
        else:
            print("pre2018_rosters.json HTTP 200")
        r3 = urllib.request.urlopen("http://127.0.0.1:8765/players.js?v=14", timeout=5)
        c3 = getattr(r3, "status", None) or r3.getcode()
        if c3 != 200:
            fail(f"players.js HTTP {c3}")
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
