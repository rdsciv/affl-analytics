#!/usr/bin/env python3
"""CHI-43: rookie college career line from local cache. Never ESPN from JS."""
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

JEANTY = "4890973"
JOSH = "3918298"  # veteran, 3+ NFL seasons


def main():
    cache_path = SITE / "college_stats.json"
    if not cache_path.exists():
        fail("site/college_stats.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    cache = json.loads(cache_path.read_text())
    script = (ROOT / "scripts" / "fetch_college_stats.py").read_text()
    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()
    common = (SITE / "common.js").read_text()

    jeanty = cache.get(JEANTY) or {}
    print("Jeanty college=%s years=%s line=%s" % (
        jeanty.get("college"), jeanty.get("years"), jeanty.get("line")))
    if jeanty.get("name") != "Ashton Jeanty":
        fail("Jeanty name %s" % jeanty.get("name"))
    if jeanty.get("college") != "Boise State":
        fail("Jeanty college %s" % jeanty.get("college"))
    line = str(jeanty.get("line") or "")
    # ESPN common/v3 career rushing totals (confirmed 2024 season 374-2601-29)
    if line != "750-4769-50":
        fail("Jeanty line %r is not the ESPN career cache 750-4769-50" % line)
    years = jeanty.get("years") or []
    if years != [2022, 2023, 2024]:
        fail("Jeanty years %s" % years)
    src = str(jeanty.get("source") or "")
    if "espn.com" not in src or "college-football" not in src or JEANTY not in src:
        fail("Jeanty source is not the ESPN college-football cache URL: %s" % src)
    if "374-2601-29" in js or "750-4769-50" in js:
        fail("players.js hardcodes Jeanty college numbers")

    if JOSH in cache:
        fail("Josh Allen veteran has a college_stats cache entry")

    n = len(cache)
    if n < 5 or n > 12:
        fail("expected 5-9 rookies cached, got %s" % n)
    for pid, rec in cache.items():
        for k in ("name", "college", "years", "line", "source"):
            if k not in rec:
                fail("%s missing %s" % (pid, k))
        if rec.get("line") and not re.search(r"\d", str(rec["line"])):
            fail("%s line has no digits: %s" % (pid, rec.get("line")))

    if "college_stats.json" not in js:
        fail("players.js does not load college_stats.json")
    if "function isRookieOrFirstAffl" not in js:
        fail("players.js missing isRookieOrFirstAffl")
    if "function collegeCacheRec" not in js:
        fail("players.js missing collegeCacheRec")
    if "pl-college-line" not in js:
        fail("players.js does not render pl-college-line")
    if "function renderCollege" not in js:
        fail("renderCollege missing")
    for field in ("breakoutAge", "dominator", "earlyDeclare"):
        if field not in js:
            fail("existing college chrome lost %s" % field)

    espn_hit = re.compile(r"https?://\S*espn\.com", re.I)
    for name, body in (("players.js", js), ("common.js", common), ("players.html", html)):
        if espn_hit.search(body):
            fail("%s calls espn.com from the browser" % name)
        if "site.web.api.espn.com" in body or "sports.core.api.espn.com" in body:
            fail("%s hits ESPN sports API" % name)

    if "college-football/athletes" not in script:
        fail("fetch script does not call college-football athletes")
    if "4890973" not in script:
        fail("fetch script does not include Jeanty")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail("players.html HTTP %s" % code)
        else:
            print("players.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/college_stats.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail("college_stats.json HTTP %s" % c2)
        else:
            print("college_stats.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail("not reachable on 8765: %s" % e)

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
