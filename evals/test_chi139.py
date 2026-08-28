#!/usr/bin/env python3
"""CHI-139: Savant hover must not hang career starts on one franchise.

Russell Wilson career AFFL starts are 92. pickHomeFranchise is Westeros
Warlords (most AFFL points, CHI-128). Those 92 are career, not Warlords.
The hover line "Started Nx by {franchise}" must use starts THAT franchise
actually started him (season-row starter weeks attributed to that canon
owner). Missing stint stays unavailable, never 0.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SAVANT = SITE / "savant"
fails: list[str] = []
TIMES = "\u00d7"


def fail(msg: str) -> None:
    fails.append(msg)


def pick_home_franchise(by_fr: dict) -> str | None:
    names = [fr for fr, bag in by_fr.items() if bag["fpts"] > 0]
    if not names:
        return None
    names.sort(key=lambda fr: (-by_fr[fr]["fpts"], -by_fr[fr]["starts"], fr))
    return names[0]


def hover_started_line(r: dict, fr: str | None, career: bool) -> str:
    if career:
        n = r.get("frStarts")
        if n is None or n == "":
            return ""
        if not (n > 0):
            return ""
        return "Started " + str(int(n)) + TIMES + ((" by " + fr) if fr else "")
    if r.get("starts"):
        return "Started " + str(r["starts"]) + TIMES + ((" by " + fr) if fr else "")
    return "Never started in the AFFL this season"


def wilson_from_payloads() -> dict:
    meta = json.loads((SAVANT / "meta.json").read_text())
    cols = meta["cols"]
    ix = {c: i for i, c in enumerate(cols)}
    by_fr: dict[str, dict] = defaultdict(lambda: {"fpts": 0.0, "starts": 0})
    career_starts = 0
    fpts = 0.0
    games = 0
    pid = None
    for y in meta["seasons"]:
        rows = json.loads((SAVANT / f"season_{y}.json").read_text())
        for r in rows:
            if r[ix["name"]] != "Russell Wilson":
                continue
            pid = r[ix["pid"]]
            career_starts += r[ix["starts"]] or 0
            fpts += r[ix["fpts"]] or 0
            games += r[ix["g"]] or 0
            fr = r[ix["fr"]]
            if fr:
                by_fr[fr]["fpts"] += r[ix["fpts"]] or 0
                by_fr[fr]["starts"] += r[ix["starts"]] or 0
    home = pick_home_franchise(by_fr)
    home_starts = by_fr[home]["starts"] if home else None
    return {
        "pid": pid,
        "starts": career_starts,
        "fpts": fpts,
        "g": games,
        "fr": home,
        "frStarts": home_starts,
        "byFr": {k: dict(v) for k, v in by_fr.items()},
    }


def test_wilson_data(w: dict) -> None:
    print("Wilson career starts", w["starts"])
    print("Wilson home franchise", w["fr"], "frStarts", w["frStarts"])
    print("Wilson fpts", round(w["fpts"], 1), "games", w["g"])
    for fr, bag in sorted(w["byFr"].items(), key=lambda kv: -kv[1]["fpts"]):
        print(f"  {fr}: fpts={round(bag['fpts'], 1)} starts={bag['starts']}")

    if w["starts"] != 92:
        fail(f"Wilson career starts {w['starts']} != 92 (published hover)")
    if w["fr"] != "Westeros Warlords":
        fail(f"Wilson home franchise {w['fr']!r} != Westeros Warlords (CHI-128)")
    if w["frStarts"] is None:
        fail("Wilson Warlords start count unavailable; must not invent 0")
    elif w["frStarts"] == 0:
        fail("Wilson Warlords starts is 0; missing stays unavailable, never 0")
    if w["frStarts"] == 92:
        fail("Wilson Warlords starts == 92; career starts hung on one franchise")
    if w["frStarts"] is not None and w["frStarts"] >= w["starts"]:
        fail(f"Wilson Warlords starts {w['frStarts']} is not a subset of career {w['starts']}")

    line = hover_started_line(w, w["fr"], career=True)
    print("Wilson career hover started line:", line)
    if "92" in line and "Warlords" in line:
        fail(f"Wilson hover attributes 92 starts to Warlords: {line!r}")
    if line == "Started 92" + TIMES + " by Westeros Warlords":
        fail("Wilson hover still paints Started 92x by Westeros Warlords")
    if w["frStarts"] and w["fr"]:
        want = "Started " + str(int(w["frStarts"])) + TIMES + " by " + w["fr"]
        if line != want:
            fail(f"Wilson hover started line {line!r} != {want!r}")


def test_source_gates(js: str, html: str) -> None:
    if "function hoverStartedLine" not in js:
        fail("savant.js missing hoverStartedLine")
    if "r.frStarts" not in js:
        fail("savant.js hover does not read r.frStarts")
    if "o.frStarts" not in js:
        fail("loadCareer does not keep o.frStarts")

    # The CHI-139 bug: career starts concatenated with "by {home franchise}".
    if "Started ${r.starts}" in js:
        fail("savant.js still interpolates Started ${r.starts} (career hung on franchise)")
    if re.search(r"Started \$\{r\.starts\}", js):
        fail("savant.js still hangs r.starts on the Started line")

    fn = re.search(r"function hoverStartedLine\(r, fr\) \{([\s\S]*?)\n  \}", js)
    if not fn:
        fail("cannot parse hoverStartedLine")
    else:
        body = fn.group(1)
        if "r.frStarts" not in body:
            fail("hoverStartedLine does not use r.frStarts on career")
        career = body
        if "if (isAll())" in body:
            career = body.split("if (isAll())", 1)[1]
            if "if (r.starts)" in career:
                career = career.split("if (r.starts)", 1)[0]
        if "r.starts" in career:
            fail("career branch of hoverStartedLine still reads r.starts")
        if "return 0" in body or 'return "Started 0' in body:
            fail("hoverStartedLine paints 0; missing stays unavailable")

    if "pickHomeFranchise" not in js:
        fail("savant.js lost pickHomeFranchise (CHI-128)")
    if "League Legacy" in js or "League Legacy" in html:
        fail("Savant mentions League Legacy")
    if re.search(r"Player \d+", js):
        fail("savant.js paints Player N")
    if "non-PPR" not in js:
        fail("savant.js dropped the non-PPR lock")

    bust = re.search(r"savant\.js\?v=(\d+)", html)
    if not bust:
        fail("savant.html savant.js not cache-busted")
    elif int(bust.group(1)) < 8:
        fail(f"savant.js cache still v={bust.group(1)}")
    if 'src="savant.js?v=8"' not in html:
        fail("savant.html pin is not savant.js?v=8")


def test_synthetic_mixup() -> None:
    by_fr = {
        "Westeros Warlords": {"fpts": 585.1, "starts": 11},
        "Muck City Mad Dawgs": {"fpts": 570.5, "starts": 20},
    }
    home = pick_home_franchise(by_fr)
    r = {"starts": 92, "fr": home, "frStarts": by_fr[home]["starts"]}
    line = hover_started_line(r, home, career=True)
    if "92" in line:
        fail(f"synthetic Wilson hover still contains 92: {line!r}")
    if home != "Westeros Warlords":
        fail(f"synthetic home {home!r}")
    if line != "Started 11" + TIMES + " by Westeros Warlords":
        fail(f"synthetic line {line!r}")

    missing = hover_started_line({"starts": 92, "fr": home, "frStarts": None}, home, True)
    if missing:
        fail(f"missing frStarts must be omitted, got {missing!r}")
    zero = hover_started_line({"starts": 92, "fr": home, "frStarts": 0}, home, True)
    if zero:
        fail(f"frStarts 0 must be omitted (never paint 0), got {zero!r}")


def main() -> int:
    js = (SITE / "savant.js").read_text()
    html = (SITE / "savant.html").read_text()
    w = wilson_from_payloads()
    test_wilson_data(w)
    test_source_gates(js, html)
    test_synthetic_mixup()

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS CHI-139 Wilson hover does not hang career starts on Warlords")
    print(f"Wilson Warlords starts (from season payloads) = {w['frStarts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
