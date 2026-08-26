#!/usr/bin/env python3
"""CHI-55 / AFFL-036: Point Title + combined titles minus sackos."""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []
fail = lambda m: fails.append(m)
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
canon = lambda i: MERGE.get(i, i)
BANNED = ("Bob Loblaw", "FantasyGenius", "FG League", "other league")


def roll_combined(data):
    by = {}
    for y, season in (data.get("seasons") or {}).items():
        teams = season.get("teams") or []
        n = len(teams)
        top_pf = max((t.get("pf") or 0) for t in teams) if teams else -1
        for t in teams:
            oid = canon(t.get("owner"))
            if not oid:
                continue
            r = by.setdefault(oid, {
                "owner": oid, "name": t.get("name"),
                "titles": 0, "runnerUps": 0, "thirds": 0,
                "sackos": 0, "scoreTitles": 0,
            })
            r["name"] = t.get("name")
            if t.get("finalRank") == 1:
                r["titles"] += 1
            if t.get("finalRank") == 2:
                r["runnerUps"] += 1
            if t.get("finalRank") == 3:
                r["thirds"] += 1
            if t.get("finalRank") and t.get("finalRank") == n:
                r["sackos"] += 1
            if top_pf > 0 and t.get("pf") == top_pf:
                r["scoreTitles"] += 1
    for f in data.get("franchises") or []:
        r = by.get(canon(f.get("owner")))
        if r and f.get("currentName"):
            r["name"] = f["currentName"]
    for r in by.values():
        r["combined"] = (
            r["titles"] + r["runnerUps"] + r["thirds"] + r["scoreTitles"] - r["sackos"]
        )
    return by


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    data = json.loads((SITE / "data.json").read_text())

    for col in ("Titles", "2nd", "3rd", "Point Title", "Sacko", "Combined"):
        if col not in html:
            fail(f"history.html missing column: {col}")
    if 'id="titles-tbl"' not in html:
        fail("history.html missing titles-tbl")
    if 'data-k="combined"' not in html:
        fail("history.html missing sortable Combined")
    if 'data-k="scoreTitles">Point Title' not in html:
        fail("history.html missing Point Title data-k")

    formula = "(r.titles || 0) + (r.runnerUps || 0) + (r.thirds || 0) + (r.scoreTitles || 0) - (r.sackos || 0)"
    if formula not in js:
        fail("history.js missing combined formula from rollup fields")
    if "scoreTitles" not in js:
        fail("history.js missing scoreTitles")
    if "m01" not in js or "m07" not in js:
        fail("history.js missing m01→m07 merge")

    for needle in BANNED:
        if needle in html or needle in js:
            fail(f"other-league name leaked: {needle}")

    by = roll_combined(data)
    checks = [
        ("m06", "Fairview Fat Cats"),
        ("m18", "Grand Teeton Feelers"),
    ]
    for oid, name in checks:
        r = by.get(oid)
        if not r:
            fail(f"missing franchise {oid}")
            continue
        if r["name"] != name:
            fail(f"{oid} current name {r['name']!r} != {name!r}")
        expect = r["titles"] + r["runnerUps"] + r["thirds"] + r["scoreTitles"] - r["sackos"]
        if r["combined"] != expect:
            fail(f"{name} combined {r['combined']} != {expect}")
        print(
            f"{name}: titles={r['titles']} 2nd={r['runnerUps']} 3rd={r['thirds']} "
            f"PT={r['scoreTitles']} sacko={r['sackos']} combined={r['combined']}"
        )

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
