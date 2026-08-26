#!/usr/bin/env python3
"""CHI-63 / AFFL-041: Historic teams toggle; Chupacabras stay current.

Copy AFFL_Pillars former-teams behavior:
  localStorage affl:show-former, \'1\' = show, default hide.
  Label: Historic teams.
  Season-scoped views stay unfiltered.

Chupacabras (m07 / Jason Kafka, merge m01→m07) are current for 2026.
Historic is the five Pillars former franchises minus Chupacabras.
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

HISTORIC_IDS = ("m12", "m10", "m04", "m09", "m16", "m19", "m14")
HISTORIC_NAMES = (
    "Muck City Mad Dawgs",
    "Winston-Salem Wake Snakes",
    "Charleston Chewbacca",
    "Pawtucket Patriots",
    "L.O.B. Thunder",
    "Pasco Pounders",
    "Poulsbo Pollywogs",
)
CHUPA_IDS = ("m07", "m01")
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def fail(msg):
    fails.append(msg)


def canon(oid):
    if oid is None or oid == "":
        return oid
    return MERGE.get(str(oid), str(oid))


def parse_historic_ids(js):
    block = re.search(r"const HISTORIC_OWNERS = \{([^}]+)\}", js, re.S)
    if not block:
        return set()
    return set(re.findall(r"\b(m\d+)\s*:", block.group(1)))


def is_historic_js(js, oid):
    """Mirror common.js isHistoric against the source HISTORIC_OWNERS map."""
    if oid is None or oid == "":
        return False
    raw = str(oid)
    c = canon(raw)
    if c == "m07" or raw == "m07" or raw == "m01":
        return False
    hist = parse_historic_ids(js)
    return raw in hist or c in hist


def main():
    common = (SITE / "common.js").read_text()
    teams = (SITE / "teams.js").read_text()
    app = (SITE / "app.js").read_text()
    history = (SITE / "history.js").read_text()
    css = (SITE / "styles.css").read_text()
    index_html = (SITE / "index.html").read_text()
    teams_html = (SITE / "teams.html").read_text()
    history_html = (SITE / "history.html").read_text()
    data = json.loads((SITE / "data.json").read_text())

    if 'SHOW_FORMER_KEY = "affl:show-former"' not in common:
        fail("common.js missing affl:show-former key")
    if 'localStorage.getItem(SHOW_FORMER_KEY) === "1"' not in common:
        fail("showFormer must persist like Pillars (\'1\' = show)")
    if "Historic teams" not in common:
        fail("toggle label is not Historic teams")
    if "function isHistoric" not in common:
        fail("common.js missing isHistoric")
    if "function visibleFranchises" not in common:
        fail("common.js missing visibleFranchises")
    if "function mountHistoricToggle" not in common:
        fail("common.js missing mountHistoricToggle")
    if "c === \"m07\"" not in common and 'c === "m07"' not in common:
        fail("isHistoric does not carve out Chupacabras m07")
    if "m01" not in common:
        fail("isHistoric missing m01 merge exception for Chupacabras")

    hist_ids = parse_historic_ids(common)
    if hist_ids != set(HISTORIC_IDS):
        fail(f"HISTORIC_OWNERS {sorted(hist_ids)} != {list(HISTORIC_IDS)}")
    if "m07" in hist_ids or "m01" in hist_ids:
        fail("Chupacabras id landed in HISTORIC_OWNERS")
    if "m22" in hist_ids:
        fail("Gabagooners id landed in HISTORIC_OWNERS")

    for oid in CHUPA_IDS:
        if is_historic_js(common, oid):
            fail(f"Chupacabras {oid} classified historic")
    if is_historic_js(common, "m07"):
        fail("m07 classified historic")

    by_owner = {f.get("owner"): f for f in data.get("franchises") or []}
    chupa = by_owner.get("m07")
    if not chupa:
        fail("data.json missing Chupacabras m07")
    else:
        name = chupa.get("currentName") or ""
        if "Chupacabra" not in name:
            fail(f"m07 currentName is {name!r}, expected Chupacabras")
        if is_historic_js(common, chupa.get("owner")):
            fail("Chupacabras franchise row classified historic")
        # files say last season 2023 / active false — still current
        years = chupa.get("years") or []
        if years and max(years) < 2025 and not chupa.get("active"):
            print("Chupacabras last=%s active=%s — still current" % (max(years), chupa.get("active")))

    for oid, name in zip(HISTORIC_IDS, HISTORIC_NAMES):
        if not is_historic_js(common, oid):
            fail(f"{name} ({oid}) is not historic")
        rec = by_owner.get(oid)
        if not rec:
            fail(f"data.json missing {name} {oid}")
        elif name not in (rec.get("currentName") or ""):
            fail("%s currentName %r != %s" % (oid, rec.get("currentName"), name))

    # merge source for Wake Snakes is historic via canon
    if not is_historic_js(common, "m20"):
        fail("m20 (merge into Wake Snakes) is not historic via canon")

    # default hides historic
    if "if (showFormer()) return rows.slice()" not in common:
        fail("visibleFranchises does not default-hide historic")
    if ".fr-card.former { display: none; }" not in css:
        fail("styles do not hide former cards by default")
    if "html.show-former .fr-card.former" not in css:
        fail("styles missing show-former reveal for former cards")
    if ".former-toggle" not in css:
        fail("styles missing .former-toggle")

    if "A.visibleFranchises(A.squads())" not in teams:
        fail("teams.js grid does not filter via visibleFranchises")
    if "A.isHistoric(f.owner)" not in teams:
        fail("teams.js former class is not isHistoric (Chupacabras would be hidden)")
    if "affl:show-former" not in teams:
        fail("teams.js does not listen for the toggle")

    if "visibleFranchises(DATA.franchises" not in app:
        fail("app.js home franchise table does not filter via visibleFranchises")
    if "affl:show-former" not in app:
        fail("app.js does not listen for the toggle")

    if "function careerRows" not in history:
        fail("history.js missing careerRows")
    if "A.visibleFranchises(ROWS)" not in history:
        fail("history.js careerRows does not use visibleFranchises")
    if "careerRows().slice()" not in history:
        fail("history.js franchise table does not use careerRows")
    if "affl:show-former" not in history:
        fail("history.js does not listen for the toggle")

    # season-scoped History standings stay on full season data
    season_fn = history.split("function renderSeasonStandings", 1)[-1].split("function ", 1)[0]
    if "careerRows" in season_fn or "visibleFranchises" in season_fn:
        fail("season standings were filtered by the historic toggle")

    if "common.js" not in index_html:
        fail("index.html does not load common.js (toggle will not mount)")
    if "common.js" not in teams_html or "common.js" not in history_html:
        fail("teams.html / history.html missing common.js")

    # HTTP 200
    for page in ("teams.html", "history.html", "index.html"):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8765/" + page, timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            if code != 200:
                fail(f"{page} HTTP {code}")
            else:
                print(f"{page} HTTP 200")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{page} not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
