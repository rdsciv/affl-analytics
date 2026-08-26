#!/usr/bin/env python3
"""CHI-84: player + franchise NGS route tree / O-line gap scheme from stored AFFL NGS only."""
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
    pjs = (SITE / "players.js").read_text()
    phtml = (SITE / "players.html").read_text()
    css = (SITE / "styles.css").read_text()
    djs = (SITE / "dictionary.js").read_text()

    if "function renderNgsRouteTree" not in pjs:
        fail("players.js missing renderNgsRouteTree")
    if "function renderNgsHoleScheme" not in pjs:
        fail("players.js missing renderNgsHoleScheme")
    if 'class="rp-tree"' not in pjs:
        fail("players.js missing rp-tree markup")
    if 'class="rp-scheme"' not in pjs:
        fail("players.js missing rp-scheme markup")
    if "rp-gap-bar" not in pjs:
        fail("players.js missing rp-gap-bar")
    if '["LE", "LT", "LG", "MID", "RG", "RT", "RE"]' not in pjs:
        fail("players.js missing 7-gap ORDER")
    if "function ngsPosAvgShare" not in pjs:
        fail("players.js missing ngsPosAvgShare (computed average)")
    if "function ngsShareTone" not in pjs:
        fail("players.js missing ngsShareTone")
    if "1.15" not in pjs or "0.85" not in pjs:
        fail("players.js missing 1.15 / 0.85 color thresholds")
    caption = "yard share vs AFFL NGS average, not Reception Perception success rate."
    if caption in pjs:
        fail("players.js still has the RP-denial caption")
    if "function renderNgsProfile" not in pjs:
        fail("players.js missing renderNgsProfile")
    if "renderNgsRouteTree(routes" not in pjs:
        fail("renderNgsProfile does not call renderNgsRouteTree")
    if "renderNgsHoleScheme(holes" not in pjs:
        fail("renderNgsProfile does not call renderNgsHoleScheme")

    # empty routes/holes must not invent a tree / scheme
    tree_fn = pjs.split("function renderNgsRouteTree", 1)[-1].split("function renderNgsHoleScheme", 1)[0]
    if "if (!routes || !routes.length) return" not in tree_fn and "if (!routes.length)" not in tree_fn:
        fail("route tree does not bail when routes are empty")
    scheme_fn = pjs.split("function renderNgsHoleScheme", 1)[-1].split("function renderNgsProfile", 1)[0]
    if "if (!holes || !holes.length) return" not in scheme_fn and "if (!holes.length)" not in scheme_fn:
        fail("hole scheme does not bail when holes are empty")

    prof_fn = pjs.split("function renderNgsProfile", 1)[-1].split("function heroTeamLine", 1)[0]
    if "ngs-chip" in prof_fn:
        fail("renderNgsProfile still renders ngs-chips")

    banned = ("Bullseye", "success vs man", "Herbert")
    for bad in banned:
        if bad in pjs:
            fail(f"players.js must not invent {bad!r}")

    if ".rp-tree" not in css:
        fail("styles.css missing .rp-tree")
    if ".rp-scheme" not in css:
        fail("styles.css missing .rp-scheme")

    bust = re.search(r"players\.js\?v=(\d+)", phtml)
    if not bust:
        fail("players.html missing players.js cache pin")
    elif int(bust.group(1)) < 30:
        fail(f"players.js cache still v={bust.group(1)}")

    for name in ("NGS route share", "NGS hole share", "Reception Perception (not in AFFL)"):
        if name not in djs:
            fail(f"dictionary.js missing {name}")
    if "cat: \"players\"" not in djs and "cat: 'players'" not in djs:
        fail("dictionary terms missing PLAYERS category")

    # ngs.json has no throw-location / CPOE-by-route — do not draw a field map
    if "field map" in pjs.lower() or "throw-location" in pjs.lower():
        fail("players.js drew or referenced a QB field map")

    tjs = (SITE / "teams.js").read_text()
    thtml = (SITE / "teams.html").read_text()
    if "function renderNgsRouteTree" not in tjs:
        fail("teams.js missing renderNgsRouteTree")
    if "function renderNgsHoleScheme" not in tjs:
        fail("teams.js missing renderNgsHoleScheme")
    if 'class="rp-tree"' not in tjs:
        fail("teams.js missing rp-tree markup")
    if 'class="rp-scheme"' not in tjs:
        fail("teams.js missing rp-scheme markup")
    if "rp-gap-bar" not in tjs:
        fail("teams.js missing rp-gap-bar")
    if '["LE", "LT", "LG", "MID", "RG", "RT", "RE"]' not in tjs:
        fail("teams.js missing 7-gap ORDER")
    if "function ngsPosAvgShare" not in tjs:
        fail("teams.js missing ngsPosAvgShare (computed average)")
    if "function ngsShareTone" not in tjs:
        fail("teams.js missing ngsShareTone")
    if "1.15" not in tjs or "0.85" not in tjs:
        fail("teams.js missing 1.15 / 0.85 color thresholds")
    if caption in tjs:
        fail("teams.js still has the RP-denial caption")
    if "renderNgsRouteTree(f.routes" not in tjs:
        fail("renderNgs does not call renderNgsRouteTree")
    if "renderNgsHoleScheme(f.holes" not in tjs:
        fail("renderNgs does not call renderNgsHoleScheme")
    if "A.franchiseName" not in tjs:
        fail("teams.js does not use current franchise names")

    tree_fn_t = tjs.split("function renderNgsRouteTree", 1)[-1].split("function renderNgsHoleScheme", 1)[0]
    if "if (!routes || !routes.length) return" not in tree_fn_t and "if (!routes.length)" not in tree_fn_t:
        fail("teams route tree does not bail when routes are empty")
    scheme_fn_t = tjs.split("function renderNgsHoleScheme", 1)[-1].split("function ngsShare", 1)[0]
    if "if (!holes || !holes.length) return" not in scheme_fn_t and "if (!holes.length)" not in scheme_fn_t:
        fail("teams hole scheme does not bail when holes are empty")

    ngs_fn = tjs.split("function renderNgs()", 1)[-1].split("async function renderSeason", 1)[0]
    if "ngs-chip" in ngs_fn:
        fail("renderNgs still renders ngs-chips")

    for bad in banned:
        if bad in tjs:
            fail(f"teams.js must not invent {bad!r}")
    if "tcomp-block" in tjs[tjs.find("function renderNgsRouteTree"):tjs.find("function renderNgs()")]:
        fail("NGS tree/scheme must not touch #tcomp-block")

    bust_t = re.search(r"teams\.js\?v=(\d+)", thtml)
    if not bust_t:
        fail("teams.html missing teams.js cache pin")
    elif int(bust_t.group(1)) < 12:
        fail(f"teams.js cache still v={bust_t.group(1)}")
    if "ngstree=1" not in thtml:
        fail("teams.html missing ngstree cache pin")
    if "tcomp=1" not in thtml:
        fail("teams.html lost tcomp cache pin")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/teams.html", timeout=5)
        code2 = getattr(r2, "status", None) or r2.getcode()
        if code2 != 200:
            fail(f"teams.html HTTP {code2}")
        else:
            print("teams.html HTTP 200")
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
