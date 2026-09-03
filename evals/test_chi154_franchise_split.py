#!/usr/bin/env python3
"""CHI-154: Fairview Fat Cats (m06) and L.O.B. Thunder (m16) stay separate franchises.

Fat Cats took that seat in 2015. Thunder played 2014 only, under a different
owner. Nothing on the site may fold Thunder's 2014 season into the Fat Cats
career, rename Thunder into Fat Cats, or paint Fat Cats on a 2014 surface.
Guards the shipped site payload plus the chrome that enforces it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

CATS, THUNDER = "m06", "m16"
CATS_NAME, THUNDER_NAME = "Fairview Fat Cats", "L.O.B. Thunder"
CATS_YEARS = list(range(2015, 2026))
THUNDER_YEARS = [2014]
HANDOFF = 2015


def main():
    data = json.loads((SITE / "data.json").read_text())
    common = (SITE / "common.js").read_text()
    app = (SITE / "app.js").read_text()
    sb = (SITE / "scoreboard.js").read_text()
    franchises = data.get("franchises") or []
    seasons = data.get("seasons") or {}

    def only(owner, name):
        hits = [f for f in franchises if f.get("owner") == owner]
        if len(hits) != 1:
            fail("expected exactly 1 franchise row for %s, got %s" % (owner, len(hits)))
            return None
        f = hits[0]
        if f.get("currentName") != name:
            fail("%s currentName is %r, expected %r" % (owner, f.get("currentName"), name))
        return f

    cats = only(CATS, CATS_NAME)
    thunder = only(THUNDER, THUNDER_NAME)

    # --- career books never merge ---
    if cats:
        if cats.get("years") != CATS_YEARS:
            fail("Fat Cats years %s, expected %s" % (cats.get("years"), CATS_YEARS))
        if 2014 in (cats.get("years") or []):
            fail("Fat Cats career claims 2014 (Thunder's only season)")
        if cats.get("seasons") != len(CATS_YEARS):
            fail("Fat Cats seasons %s, expected %s" % (cats.get("seasons"), len(CATS_YEARS)))
        if (cats.get("wins"), cats.get("losses"), cats.get("ties")) != (80, 68, 0):
            fail("Fat Cats record %s-%s-%s, expected 80-68-0"
                 % (cats.get("wins"), cats.get("losses"), cats.get("ties")))
        games = (cats.get("wins") or 0) + (cats.get("losses") or 0) + (cats.get("ties") or 0)
        if games != 148:
            fail("Fat Cats career games %s, expected 148 (a 161/176 total means a fold)" % games)
        if not cats.get("active"):
            fail("Fat Cats should be a current franchise")
        print("Fat Cats %s-%s (%s games) over %s seasons %s-%s"
              % (cats["wins"], cats["losses"], games, cats["seasons"],
                 CATS_YEARS[0], CATS_YEARS[-1]))
    if thunder:
        if thunder.get("years") != THUNDER_YEARS:
            fail("Thunder years %s, expected %s" % (thunder.get("years"), THUNDER_YEARS))
        if thunder.get("seasons") != 1:
            fail("Thunder seasons %s, expected 1" % thunder.get("seasons"))
        if (thunder.get("wins"), thunder.get("losses")) != (4, 9):
            fail("Thunder record %s-%s, expected 4-9"
                 % (thunder.get("wins"), thunder.get("losses")))
        if thunder.get("active"):
            fail("Thunder is historic, not a current franchise")
        print("Thunder %s-%s in %s only, held separate"
              % (thunder["wins"], thunder["losses"], THUNDER_YEARS[0]))
    if cats and thunder and cats.get("ownerName") == thunder.get("ownerName"):
        fail("Fat Cats and Thunder share an owner name — different owners is the whole point")

    # --- no merge rule may alias one seat onto the other ---
    m = re.search(r"const MERGE = \{([^}]*)\}", common)
    if not m:
        fail("common.js MERGE table not found")
    else:
        merge = dict(re.findall(r"(\w+)\s*:\s*[\"'](\w+)[\"']", m.group(1)))
        for a, b in merge.items():
            if CATS in (a, b) and THUNDER in (a, b):
                fail("common.js MERGE folds %s into %s" % (a, b))
        if CATS in merge or THUNDER in merge:
            fail("MERGE remaps %s / %s away from its own seat" % (CATS, THUNDER))
        print("MERGE %s leaves both seats alone" % merge)

    # --- historic toggle carries Thunder, never the Cats ---
    hist = re.search(r"HISTORIC_IDS = \[([^\]]*)\]", app)
    if not hist:
        fail("app.js HISTORIC_IDS not found (historic toggle gone)")
    else:
        ids = re.findall(r"[\"'](\w+)[\"']", hist.group(1))
        if THUNDER not in ids:
            fail("Thunder missing from HISTORIC_IDS — it would vanish from the records book")
        if CATS in ids:
            fail("Fat Cats listed as historic; they are a current franchise")
    if "affl:show-former" not in app:
        fail("app.js lost the show-former hook that reveals historic franchises")

    # --- season rosters: the seat changes hands in 2015 ---
    for year, season in sorted(seasons.items()):
        y = int(year)
        owners = {t.get("owner") for t in (season.get("teams") or [])}
        names = {t.get("name") for t in (season.get("teams") or [])}
        if y < HANDOFF:
            if CATS in owners:
                fail("%s season lists Fat Cats (m06) before the 2015 handoff" % y)
            if CATS_NAME in names:
                fail("%s season names a team %r" % (y, CATS_NAME))
        else:
            if THUNDER in owners:
                fail("%s season still lists Thunder (m16) after 2014" % y)
    t14 = seasons.get("2014") or {}
    o14 = {t.get("owner") for t in (t14.get("teams") or [])}
    if THUNDER not in o14:
        fail("2014 season is missing Thunder entirely")
    n14 = {t.get("name") for t in (t14.get("teams") or [])}
    if THUNDER_NAME not in n14:
        fail("2014 Thunder row is not named %r (current-name rule must not rename it)" % THUNDER_NAME)
    o15 = {t.get("owner") for t in ((seasons.get("2015") or {}).get("teams") or [])}
    if CATS not in o15:
        fail("2015 season is missing the Fat Cats")
    print("2014 seat = Thunder, 2015 seat = Fat Cats")

    # --- 2014 payload never paints the Cats ---
    y2014 = SITE / "years" / "2014.json"
    if y2014.exists():
        raw = y2014.read_text()
        for needle in ("Fairview", "Fat Cats"):
            if needle in raw:
                fail("site/years/2014.json mentions %r" % needle)
    else:
        fail("site/years/2014.json missing")

    # --- Scoreboard deep link keeps its sticky drop notice ---
    for needle in ("sb-drop-notice", "urlDropSquad", "franchisePlayedSeason"):
        if needle not in sb:
            fail("scoreboard.js lost %s (Fat Cats-on-2014 deep link would render)" % needle)
    if sb.count("urlDropSquad") < 3:
        fail("scoreboard.js drop notice does not survive a clear-to-All redraw")
    if "franchisePlayedSeason" not in common:
        fail("common.js no longer exports franchisePlayedSeason")
    print("scoreboard deep-link guard intact")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
