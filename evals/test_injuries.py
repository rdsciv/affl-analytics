#!/usr/bin/env python3
"""CHI-42: NFL injury/depth from local cache. Never ESPN from JS."""
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

NEED = ("athleteId", "name", "status", "comment", "team", "date")
# ESPN-shaped statuses we have seen on sports.core injury payloads.
# Not a display whitelist — used only to reject invented values like fake IR.
ESPNISH = re.compile(
    r"^(Active|Questionable|Doubtful|Out|Injured Reserve|Injury Reserve|"
    r"Out for Season|Suspension|Day-To-Day|Healthy|PUP|NFI|Suspended)?$",
    re.I,
)


def main():
    cache_path = SITE / "injuries.json"
    if not cache_path.exists():
        fail("site/injuries.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    cache = json.loads(cache_path.read_text())
    if not isinstance(cache, dict) or not cache:
        fail("injuries.json is not a keyed object")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    script = (ROOT / "scripts" / "fetch_injuries.py").read_text()
    js = (SITE / "scoreboard.js").read_text()
    html = (SITE / "scoreboard.html").read_text()
    common = (SITE / "common.js").read_text()

    # --- cache shape ---
    named = []
    for aid, rec in cache.items():
        if not isinstance(rec, dict):
            fail("%s is not an object" % aid)
            continue
        for k in NEED:
            if k not in rec:
                fail("%s missing %s" % (aid, k))
        if rec.get("athleteId") not in (None, "") and str(rec.get("athleteId")) != str(aid):
            fail("%s athleteId mismatch %s" % (aid, rec.get("athleteId")))
        st = rec.get("status") or ""
        if st and not ESPNISH.match(st):
            fail("%s status %r is not ESPN-shaped" % (aid, st))
        if rec.get("name") and st:
            named.append((aid, rec["name"], st, rec.get("team") or ""))

    if not named:
        fail("cache has no named row with a status")
    else:
        print("sample", named[0][1], named[0][2], named[0][3])

    # at least one known name/status from the file itself (not invented here)
    file_names = {rec.get("name") for rec in cache.values() if rec.get("name")}
    if "Jalen Hurts" in file_names:
        h = cache.get("4040715") or {}
        print("Hurts status=%s team=%s" % (h.get("status"), h.get("team")))
        if h.get("name") != "Jalen Hurts":
            fail("Hurts name %s" % h.get("name"))
        if not h.get("status"):
            fail("Hurts status empty")
    elif not any(n[1] for n in named):
        fail("no known name in cache")

    n = len(cache)
    print("cached injuries", n)
    if n < 32:
        fail("expected injuries across the league, got %s" % n)

    # --- no invented IR ---
    if re.search(r'status\s*=\s*["\']IR["\']', script):
        fail("fetch script assigns invented IR")
    if re.search(r'status\s*=\s*["\']IR["\']', js):
        fail("scoreboard.js assigns invented IR")
    if "Injured Reserve" not in json.dumps(cache) and re.search(r'\bIR\b', js) and "INJ_RANK" not in js:
        pass
    # statuses in the file must come from the cache rows, not a JS hardcoded IR list
    if '"IR"' in js and "rec.status" not in js and "r.status" not in js:
        fail("JS may invent IR instead of using cache status")

    # --- fetch script uses the right ESPN sources ---
    if "sports.core.api.espn.com" not in script or "/injuries?limit=100" not in script:
        fail("fetch script does not call sports.core per-team injuries")
    if "site.api.espn.com" not in script or "depthcharts" not in script:
        fail("fetch script does not call site.api depthcharts")
    if "/nfl/injuries" in script and "teams/{id}/injuries" not in script:
        fail("fetch script uses the league-wide dump")

    # --- JS never hits ESPN ---
    espn_hit = re.compile(r"https?://\S*espn\.com", re.I)
    for name, body in (("scoreboard.js", js), ("scoreboard.html", html)):
        if espn_hit.search(body):
            fail("%s calls espn.com from the browser" % name)
        if "site.api.espn.com" in body or "sports.core.api.espn.com" in body or "site.web.api.espn.com" in body:
            fail("%s hits ESPN sports API" % name)
    if "injuries.json" not in js:
        fail("scoreboard.js does not load injuries.json")

    # --- markup ---
    for needle in ("nfl-injury-card", "nfl-injury-list", "NFL injury"):
        if needle not in html:
            fail("scoreboard.html missing %s" % needle)
    if "not AFFL roster" not in html and "not AFFL roster" not in js:
        fail("caption does not say NFL injury/depth, not AFFL roster")
    if "function renderNflInjuries" not in js:
        fail("renderNflInjuries missing")

    depth_path = SITE / "depthcharts.json"
    if depth_path.exists():
        depth = json.loads(depth_path.read_text())
        hurts = depth.get("4040715") or {}
        print("Hurts depth", hurts.get("depth"))
        if hurts.get("depth") != "PHI QB1":
            fail("Hurts is not PHI QB1 in depth cache: %s" % hurts.get("depth"))
    else:
        print("depthcharts.json missing (optional)")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/scoreboard.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail("scoreboard.html HTTP %s" % code)
        else:
            print("scoreboard.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/injuries.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail("injuries.json HTTP %s" % c2)
        else:
            print("injuries.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail("not reachable on 8765: %s" % e)

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
