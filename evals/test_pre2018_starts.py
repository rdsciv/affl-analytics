#!/usr/bin/env python3
"""2014–2017 recovered starter overlays: file exists, weeks real, no invented Ben starts."""
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
BANNED = ("not rostered", "not on an AFFL roster")


def brace_block(src, start):
    i = src.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


def main():
    path = SITE / "pre2018_starts.json"
    if not path.exists():
        fail("site/pre2018_starts.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    data = json.loads(path.read_text())
    y2014 = data.get("2014") or {}
    weeks = set()
    for pid, rec in y2014.items():
        if not isinstance(rec, dict):
            continue
        weeks.update(int(w) for w in rec if str(w).isdigit())
    print(f"2014 weeks with starter rows: {sorted(weeks)} n={len(weeks)}")
    if len(weeks) < 8:
        fail(f"2014 has {len(weeks)} weeks with starter rows, need >= 8")

    teams_2014 = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    ben = y2014.get("5536") or {}
    if ben:
        print("2014 pid 5536 starts (from file, not invented):")
        for wk in sorted(ben, key=lambda x: int(x)):
            rec = ben[wk]
            print(f"  W{wk} tid={rec.get('tid')} slot={rec.get('slot')} pts={rec.get('pts')}")
            try:
                wkn = int(wk)
            except (TypeError, ValueError):
                fail(f"2014 pid 5536 week {wk!r} is not an int")
                continue
            if wkn < 1 or wkn > 17:
                fail(f"2014 pid 5536 week {wkn} not in 1-17")
            tid = rec.get("tid")
            if tid not in teams_2014:
                fail(f"2014 pid 5536 W{wkn} tid {tid} is not a 2014 team id")
    else:
        print("2014 pid 5536: absent from starts (backup all year is allowed)")

    snap_path = SITE / "pre2018_rosters.json"
    if not snap_path.exists():
        fail("site/pre2018_rosters.json missing")
    else:
        snap = json.loads(snap_path.read_text())
        sben = ((snap.get("2014") or {}).get("5536") or {})
        print(f"2014 snapshot 5536 tid={sben.get('tid')} owner={sben.get('owner')}")
        if sben.get("tid") != 7:
            fail(f"snapshot 2014 pid 5536 tid {sben.get('tid')} != 7 (Feelers)")
        if sben.get("owner") != "m18":
            fail(f"snapshot 2014 pid 5536 owner {sben.get('owner')} != m18 (Feelers)")

    site = json.loads((SITE / "data.json").read_text())
    feelers = next((f for f in site.get("franchises") or [] if f.get("owner") == "m18"), None)
    if not feelers or "Feelers" not in (feelers.get("currentName") or ""):
        fail("franchiseName m18 is not Feelers")
    else:
        print(f"m18 currentName={feelers.get('currentName')}")

    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()
    if "pre2018_starts.json" not in js:
        fail("players.js does not fetch pre2018_starts.json")
    if "function preStartsFor" not in js and "PRE2018_STARTS" not in js:
        fail("players.js missing pre2018 starts overlay")
    if "/* <th>Proj</th> */" in js:
        fail("players.js reintroduced leftover Proj comment inside template")

    for m in re.finditer(r"isPre2018\s*\(", js):
        block = brace_block(js, m.start())
        for phrase in BANNED:
            if phrase in block:
                fail(f"players.js uses '{phrase}' inside an isPre2018 branch")
    for i, line in enumerate(js.splitlines(), 1):
        if "< 2018" in line or "isPre2018(" in line:
            for phrase in BANNED:
                if phrase in line:
                    fail(f"players.js line {i} uses '{phrase}' with a pre-2018 test")

    if "players.js?v=" not in html:
        fail("players.html did not cache-bust players.js")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/pre2018_starts.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail(f"pre2018_starts.json HTTP {c2}")
        else:
            print("pre2018_starts.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
