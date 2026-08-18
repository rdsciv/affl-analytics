#!/usr/bin/env python3
"""History: current franchise name only, Feelers linked, leeger all-time."""
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []


def fail(msg):
    fails.append(msg)


def nav_labels(html):
    m = re.search(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    if not m:
        return []
    return re.findall(r"<a[^>]*>([^<]+)</a>", m.group(1))


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    data = json.loads((SITE / "data.json").read_text())

    if "History" not in nav_labels(html):
        fail("nav missing History")
    if 'data-k="ownerName"' in html or ">Owner<" in html:
        fail("Owner / first-name column is still on History")
    if 'data-k="name">Team<' not in html:
        fail("Team column missing")
    if "rank-pill" not in js:
        fail("History rows missing rank pills")
    if "logoHTML" not in js:
        fail("History rows missing logos")
    if "was " in js or "inactive" in js:
        fail("History still renders was/inactive labels")
    for col in ("Sacko", "3rd", "PO%", "Med", "SD", "Pts/$", "PAR/$"):
        if col not in html:
            fail(f"leeger/PPD column missing: {col}")
    if 'id="ppd-tbl"' not in html:
        fail("PPD table missing")
    if "ppdQB" not in js:
        fail("positional PPD missing")
    for col in ("All-Play", "AP%", "Exp W", "Luck", "Avg", "Max", "Min", "+/-"):
        if col not in html:
            fail(f"leeger column missing: {col}")

    banned = ("ownerName", "shortOwner", "f.ownerName")
    for b in banned:
        if b in js:
            fail(f"history.js still uses {b}")
    if "currentName" not in js and "f.name" not in js:
        fail("history.js does not display current franchise name")
    if "allplayW" not in js and "allW" not in js:
        fail("history.js missing all-play")
    if "expWins" not in js:
        fail("history.js missing expected wins")
    if "maxScore" not in js:
        fail("history.js missing max score")
    if "teams.html" not in js or "squad" not in js:
        fail("no teams.html?squad= link")

    # Feelers: one owner, current name Grand Teeton, Tittsburgh is an alias
    feel = [f for f in data["franchises"] if f.get("owner") == "m18"]
    if len(feel) != 1:
        fail(f"Feelers should be 1 franchise row, got {len(feel)}")
    if feel and feel[0].get("currentName") != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel[0].get('currentName')}")
    tits = [f for f in data["franchises"] if "Tittsburgh" in (f.get("currentName") or "")]
    if tits:
        fail("Tittsburgh Feelers is a separate franchise row")
    names_2014_2024 = []
    for y, s in data["seasons"].items():
        for t in s.get("teams", []):
            if t.get("owner") == "m18":
                names_2014_2024.append((y, t.get("name")))
    if not any(n == "Tittsburgh Feelers" for _, n in names_2014_2024):
        fail("Tittsburgh Feelers alias missing from season history")
    if not any(n == "Grand Teeton Feelers" for _, n in names_2014_2024):
        fail("Grand Teeton Feelers missing from season history")
    print("Feelers aliases:", sorted(set(n for _, n in names_2014_2024)))

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
