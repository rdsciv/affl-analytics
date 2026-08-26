#!/usr/bin/env python3
"""Trades page: all-time current-franchise trade grid."""
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def canon(oid):
    if not oid:
        return None
    s = str(oid)
    return MERGE.get(s, s)


def main():
    html = (SITE / "trades.html").read_text()
    js = (SITE / "trades.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())

    if 'id="trade-grid"' not in html:
        fail("trades.html missing #trade-grid")
    if 'id="trade-grid-block"' not in html:
        fail("trades.html missing trade-grid-block")
    if html.find('id="trade-grid"') > html.find('id="trade-list"'):
        fail("grid sits after the blotter, not on the landing")
    if "function buildTradeGrid" not in js:
        fail("trades.js missing buildTradeGrid")
    if "function tradeOwners" not in js:
        fail("trades.js missing tradeOwners (one-sided from=)")
    if "g.from" not in js:
        fail("one-sided trades do not read got.from")
    if "f.active" not in js:
        fail("grid is not limited to current franchises")
    if "currentName" not in js:
        fail("grid does not use currentName")
    if "Tittsburgh" in js or "Tittsburgh" in html:
        fail("Tittsburgh in trade grid UI")
    if "2018" not in js:
        fail("grid does not mention 2018 floor")
    if "table.tg" not in css:
        fail("styles.css missing trade grid")

    franch = {f["owner"]: f for f in data["franchises"]}
    active = [f for f in data["franchises"] if f.get("active")]
    if len(active) != 12:
        fail("expected 12 active franchises, got %s" % len(active))
    owner_of = {}
    for y, season in (data.get("seasons") or {}).items():
        for t in season.get("teams") or []:
            owner_of[(int(y), t["id"])] = canon(t.get("owner"))

    seen = set()
    pairs = Counter()
    for y in range(2014, 2026):
        d = json.loads((SITE / f"years/{y}.json").read_text())
        for tr in d.get("trades") or []:
            sides = tr.get("sides") or []
            owners = []
            if len(sides) >= 2:
                for s in sides:
                    oid = owner_of.get((y, s.get("tid")))
                    if oid:
                        owners.append(oid)
            elif len(sides) == 1:
                oid = owner_of.get((y, sides[0].get("tid")))
                if oid:
                    owners.append(oid)
                for g in sides[0].get("got") or []:
                    oid2 = owner_of.get((y, g.get("from")))
                    if oid2:
                        owners.append(oid2)
            owners = list(dict.fromkeys(owners))
            owners = [o for o in owners if franch.get(o, {}).get("active")]
            if len(owners) < 2:
                continue
            a, b = sorted(owners[:2])
            key = (y, tr.get("date"), tr.get("wk"), a, b)
            if key in seen:
                continue
            seen.add(key)
            pairs[(a, b)] += 1

    feel_ski = pairs.get(tuple(sorted(["m18", "m11"])), 0)
    # CHI-45: proposal join recovered empty 2025 ACCEPTs (was 17 before the join).
    if feel_ski != 20:
        fail("Feelers–Skinners all-time current deals %s != 20" % feel_ski)
    if sum(pairs.values()) < 200:
        fail("too few current-franchise deals: %s" % sum(pairs.values()))

    try:
        body = urllib.request.urlopen("http://127.0.0.1:8765/trades.html", timeout=3).read().decode()
        if 'id="trade-grid"' not in body:
            fail("served trades.html missing trade grid")
        if "Tittsburgh" in body:
            fail("Tittsburgh on served trades.html")
    except Exception as e:
        fail("trades.html not reachable on 8765: %s" % e)

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("current_deals", sum(pairs.values()), "feelers_skinners", feel_ski)
    return 0


if __name__ == "__main__":
    sys.exit(main())
