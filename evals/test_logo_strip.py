#!/usr/bin/env python3
"""CHI-69 / AFFL-046: 2026 header rail — 12 circles, no 2-row dump, real marks."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []

CURRENT = (
    "m11", "m06", "m08", "m05", "m02", "m18",
    "m15", "m17", "m21", "m13", "m22", "m07",
)
HISTORIC = ("m12", "m10", "m04", "m09", "m16", "m19", "m14")
GONE = ("m19", "m14")  # Pounders, Pollywogs — not in the 2026 strip


def fail(msg):
    fails.append(msg)


def parse_current(js):
    block = re.search(r"const CURRENT_2026 = \[(.*?)\];", js, re.S)
    if not block:
        return []
    return re.findall(r'owner:\s*"([^"]+)"', block.group(1))


def parse_historic(js):
    block = re.search(r"const HISTORIC_OWNERS = \{([^}]+)\}", js, re.S)
    if not block:
        return set()
    return set(re.findall(r"\b(m\d+)\s*:", block.group(1)))


def current_row(js, owner):
    m = re.search(r'owner:\s*"' + owner + r'"[^}]+\}', js)
    return m.group(0) if m else ""


def main():
    common = (SITE / "common.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())

    owners = parse_current(common)
    if owners != list(CURRENT):
        fail(f"CURRENT_2026 {owners} != {list(CURRENT)}")
    if len(owners) != 12:
        fail(f"strip is {len(owners)} teams, need 12")
    for gone in GONE:
        if gone in owners:
            fail(f"{gone} (2025 departed) is still in the 2026 strip")
    if "m07" not in owners:
        fail("Chupacabras m07 missing from 2026 strip")
    if "m22" not in owners:
        fail("Gabagooners m22 missing from 2026 strip")

    if "teams.html?squad=" not in common:
        fail("strip links are not teams.html?squad=")
    if "function mountBrandStrip" not in common:
        fail("common.js missing mountBrandStrip")
    if "insertAdjacentElement(\"afterend\"" not in common:
        fail("strip is not inserted after the brand row / mark")
    if ".brand-home" not in common or "brand-strip" not in common:
        fail("strip does not mount from .brand-home")

    # Gabagooners: real png, not a letter tile
    gaba = current_row(common, "m22")
    if not gaba:
        fail("m22 row missing in CURRENT_2026")
    else:
        logo = re.search(r'logo:\s*"([^"]*)"', gaba)
        src = logo.group(1) if logo else ""
        if not src:
            fail("Gabagooners still have an empty logo — letter tile")
        elif not src.lower().endswith(".png"):
            fail(f"Gabagooners img src is {src!r}, need a real png")
        else:
            disk = SITE / src
            if not disk.is_file() or disk.stat().st_size < 1000:
                fail(f"Gabagooners png missing or empty: {src}")
            else:
                print(f"gabagooners png {src} {disk.stat().st_size} bytes")

    # Feelers must keep their own ant/sunset file — not overwritten by Gabagooners
    feel = current_row(common, "m18")
    feel_logo = re.search(r'logo:\s*"([^"]*)"', feel)
    if feel_logo and feel_logo.group(1) == "logos/gabagooners.png":
        fail("Feelers were overwritten with the Gabagooners badge")
    if "d9388077ba8f.jpg" not in feel:
        fail("Feelers lost their existing ant/sunset mark path")

    hist = parse_historic(common)
    if hist != set(HISTORIC):
        fail(f"HISTORIC_OWNERS {sorted(hist)} != {list(HISTORIC)}")
    if "m07" in hist or "m22" in hist:
        fail("current 2026 team landed in HISTORIC_OWNERS")
    if 'c === "m22"' not in common and "c === 'm22'" not in common:
        fail("isHistoric does not carve out Gabagooners m22")

    by_owner = {f.get("owner"): f for f in data.get("franchises") or []}
    g = by_owner.get("m22")
    if not g:
        fail("data.json missing Gabagooners m22 stub")
    else:
        if "Gabagooner" not in (g.get("currentName") or ""):
            fail(f"m22 currentName {g.get('currentName')!r}")
        if g.get("ownerName") != "Andy Pietromonaco":
            fail(f"m22 ownerName {g.get('ownerName')!r}, expected Andy Pietromonaco")
        if g.get("years"):
            fail("Gabagooners stub has fake seasons")
        if g.get("titles"):
            fail("Gabagooners stub has fake titles")
        if not g.get("active"):
            fail("Gabagooners stub is not current")
    chupa = by_owner.get("m07")
    if not chupa or not chupa.get("active"):
        fail("Chupacabras m07 is not marked current")
    for oid, name in (("m19", "Pasco Pounders"), ("m14", "Poulsbo Pollywogs")):
        rec = by_owner.get(oid)
        if not rec:
            fail(f"data.json missing {name} {oid}")
        elif rec.get("active"):
            fail(f"{name} still active")

    if ".brand-strip" not in css or ".brand-team" not in css:
        fail("styles missing .brand-strip / .brand-team")

    # no 2-row dump: rail is a single nowrap row of equal circles
    strip_css = re.search(r"\.brand-strip\s*\{([^}]+)\}", css)
    team_css = re.search(r"\.brand-team\s*\{([^}]+)\}", css)
    if not strip_css:
        fail("styles missing .brand-strip rule")
    else:
        body = strip_css.group(1)
        if "flex-wrap: wrap" in body or "flex-wrap:wrap" in body:
            fail("brand-strip still wraps — two-row dump")
        if "nowrap" not in body:
            fail("brand-strip is not a single nowrap rail")
        if "max-width: 220px" in body or "max-width:220px" in body:
            fail("brand-strip still capped at 220px (crammed chip pile)")
        if "1 0 100%" not in body and "flex-basis: 100%" not in body and "width: 100%" not in body:
            fail("brand-strip is not a full-width own row")
    if not team_css:
        fail("styles missing .brand-team rule")
    else:
        body = team_css.group(1)
        if "border-radius: 50%" not in body and "border-radius:50%" not in body:
            fail("brand-team is not a circle")
        sizes = [int(x) for x in re.findall(r"(?:width|height):\s*(\d+)px", body)]
        if not sizes or any(n < 32 or n > 36 for n in sizes):
            fail(f"brand-team size {sizes} not in 32–36px circle range")
        if "border-radius: 4px" in body:
            fail("brand-team still uses tiny rounded squares")

    # home link still present
    for page in ("index.html", "teams.html", "wrapped.html", "players.html", "history.html"):
        html = (SITE / page).read_text()
        if 'class="brand-home"' not in html or 'href="index.html"' not in html:
            fail(f"{page} lost the AFFL mark → home link")

    for page in ("index.html", "teams.html"):
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
