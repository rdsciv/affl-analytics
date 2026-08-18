#!/usr/bin/env python3
"""CHI-41: player news / next-game / headshot fallback from local cache. Never ESPN from JS."""
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

HURTS = "4040715"
NEED = ("name", "college", "draft", "nextGame", "news", "headshotFallback")


def main():
    cache_path = SITE / "player_overview.json"
    if not cache_path.exists():
        fail("site/player_overview.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    cache = json.loads(cache_path.read_text())
    script = (ROOT / "scripts" / "fetch_player_overview.py").read_text()
    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()
    common = (SITE / "common.js").read_text()

    if not isinstance(cache, dict) or not cache:
        fail("player_overview.json is not a keyed object")

    hurts = cache.get(HURTS) or {}
    ng = hurts.get("nextGame") or {}
    news = hurts.get("news") or []
    news0 = (news[0].get("headline") if news and isinstance(news[0], dict) else "") or ""
    print("Hurts next=%s news0=%s" % (ng.get("shortName") or ng.get("name") or "", news0))
    if hurts.get("name") != "Jalen Hurts":
        fail("Hurts name %s" % hurts.get("name"))
    if not isinstance(ng, dict) or not (ng.get("shortName") or ng.get("name")):
        fail("Hurts nextGame empty")
    if not news or not news0:
        fail("Hurts news empty — do not invent; cache must carry ESPN headlines")
    if any(not (n.get("headline") or "").strip() for n in news if isinstance(n, dict)):
        fail("Hurts news has a blank headline")

    n = len(cache)
    print("cached players", n)
    if n < 8 or n > 16:
        fail("expected Hurts + 8-15 2025 AFFL starters, got %s" % n)
    for pid, rec in cache.items():
        if not isinstance(rec, dict):
            fail("%s is not an object" % pid)
            continue
        for k in NEED:
            if k not in rec:
                fail("%s missing %s" % (pid, k))
        if rec.get("news") is None:
            fail("%s news is null (use [])" % pid)
        for item in rec.get("news") or []:
            if not isinstance(item, dict) or not (item.get("headline") or "").strip():
                fail("%s invented/blank news item" % pid)
                break

    if "player_overview.json" not in js:
        fail("players.js does not load player_overview.json")
    if "function overviewRec" not in js:
        fail("players.js missing overviewRec")
    if "function nextGameChipHTML" not in js:
        fail("players.js missing nextGameChipHTML")
    if "function renderOverview" not in js:
        fail("players.js missing renderOverview")
    if "function heroHeadshotUrl" not in js:
        fail("players.js missing heroHeadshotUrl")
    if "pl-next-chip" not in js:
        fail("players.js does not render next-game chip")
    if "pl-news-list" not in js and "pl-news-hed" not in js:
        fail("players.js does not render news list")
    if 'id="pl-overview"' not in html:
        fail("players.html missing pl-overview")

    # Headshot fallback is cache-only and only when current url is empty.
    if "if (existing) return existing" not in js:
        fail("heroHeadshotUrl is not gated on an existing headshot url")
    if "headshotFallback" not in js:
        fail("players.js does not read cache headshotFallback")
    if "a.espncdn.com" in js:
        fail("players.js constructs ESPN headshot URLs instead of using the cache")
    if re.search(r"heroHeadshotUrl[\s\S]{0,200}existing\s*\|\|", js):
        fail("heroHeadshotUrl ORs a fallback before checking empty")

    # CHI-43 rookie college line must stay
    if "function collegeCacheRec" not in js or "pl-college-line" not in js:
        fail("CHI-43 rookie college line was broken")
    if "function renderCollege" not in js:
        fail("renderCollege missing")

    espn_hit = re.compile(r"https?://\S*espn\.com", re.I)
    for name, body in (("players.js", js), ("common.js", common), ("players.html", html)):
        if espn_hit.search(body):
            fail("%s calls espn.com from the browser" % name)
        if "site.web.api.espn.com" in body or "site.api.espn.com" in body:
            fail("%s hits ESPN sports API" % name)

    if "athletes/{id}/overview" not in script and "/athletes/" not in script:
        fail("fetch script does not call common/v3 athlete overview")
    if "4040715" not in script:
        fail("fetch script does not include Hurts")
    if "a.espncdn.com/i/headshots/nfl/players/full" not in script:
        fail("fetch script does not store ESPN headshot fallback")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail("players.html HTTP %s" % code)
        else:
            print("players.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/player_overview.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail("player_overview.json HTTP %s" % c2)
        else:
            print("player_overview.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail("not reachable on 8765: %s" % e)

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
