#!/usr/bin/env python3
"""CHI-84: Franchise NGS is a route tree + O-line gap bars. No disclaimer, no fan."""
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []


def fail(msg):
    fails.append(msg)


def renderer_body(js, name, nxt):
    start = js.find("function " + name)
    end = js.find(nxt, start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        return ""
    return js[start:end]


def main():
    tjs = (SITE / "teams.js").read_text()
    pjs = (SITE / "players.js").read_text()
    thtml = (SITE / "teams.html").read_text()
    phtml = (SITE / "players.html").read_text()

    caption = "yard share vs AFFL NGS average, not Reception Perception success rate."
    for name, body in (("teams.js", tjs), ("players.js", pjs)):
        if caption in body:
            fail(f"{name} still has the RP disclaimer")
        if "RP_CAPTION" in body:
            fail(f"{name} still defines RP_CAPTION")
        if "function renderNgsHoleFan" in body:
            fail(f"{name} still has renderNgsHoleFan")
        if 'class="rp-fan"' in body:
            fail(f"{name} still emits rp-fan")
        if "function renderNgsHoleScheme" not in body:
            fail(f"{name} missing renderNgsHoleScheme")
        if 'class="rp-scheme"' not in body:
            fail(f"{name} missing rp-scheme")
        if "rp-gap-bar" not in body:
            fail(f"{name} missing rp-gap-bar")
        if '["LE", "LT", "LG", "MID", "RG", "RT", "RE"]' not in body:
            fail(f"{name} missing 7-gap ORDER")
        if "function renderNgsRouteTree" not in body:
            fail(f"{name} missing renderNgsRouteTree")
        if 'class="rp-tree"' not in body:
            fail(f"{name} missing rp-tree")

    for label, js, tree_next, scheme_next in (
        ("teams.js", tjs, "function renderNgsHoleScheme", "function ngsShare"),
        ("players.js", pjs, "function renderNgsHoleScheme", "function renderNgsProfile"),
    ):
        tree_fn = renderer_body(js, "renderNgsRouteTree", tree_next)
        scheme_fn = renderer_body(js, "renderNgsHoleScheme", scheme_next)
        if "<figcaption>" in tree_fn or "<figcaption>" in scheme_fn:
            fail(f"{label} new renderers still emit figcaption")

    if "renderNgsHoleScheme(f.holes" not in tjs:
        fail("teams renderNgs does not call renderNgsHoleScheme")
    if "renderNgsHoleScheme(holes" not in pjs:
        fail("players renderNgsProfile does not call renderNgsHoleScheme")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/teams.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"teams.html HTTP {code}")
        else:
            print("teams.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code2 = getattr(r2, "status", None) or r2.getcode()
        if code2 != 200:
            fail(f"players.html HTTP {code2}")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
