#!/usr/bin/env python3
"""Waiver Report overlay: 2018-2025 claims + History card."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def claims_in(bag, year, week=None):
    weeks = bag.get(str(year)) or {}
    if week is None:
        rows = []
        for rs in weeks.values():
            rows.extend(rs)
        return rows
    return list(weeks.get(str(week)) or [])


def add_pids(row):
    return [it.get("pid") for it in (row.get("items") or []) if it.get("act") == "ADD"]


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    script = (ROOT / "scripts" / "extract_waivers.py").read_text()

    if "Waiver Report" not in html:
        fail("history.html missing Waiver Report")
    if "waiver-block" not in html:
        fail("history.html missing waiver-block")
    if "waivers.json" not in js:
        fail("history.js does not load waivers.json")
    if "Waiver claims start in 2018" not in js:
        fail("history.js missing 2014 honest empty copy")
    if "Tittsburgh" in js:
        fail("history.js mentions Tittsburgh")
    if "url_for" not in script or "fetch.get" not in script:
        fail("extract_waivers.py does not use fetch.url_for / fetch.get")
    if "COOKIE" in script or "espn_s2" in script or "SWID" in script:
        fail("extract_waivers.py mentions cookies")

    path = SITE / "waivers.json"
    if not path.exists():
        fail("site/waivers.json missing")
        bag = {}
    else:
        bag = json.loads(path.read_text())
        if "2014" in bag:
            fail("waivers.json invented 2014 claims")
        years = [str(y) for y in range(2018, 2026)]
        for y in years:
            if y not in bag:
                fail(f"waivers.json missing {y}")
        w16 = claims_in(bag, 2019, 16)
        lock = [r for r in w16 if 3924327 in add_pids(r)]
        if not lock:
            fail("2019 week 16 missing Drew Lock (pid 3924327) claim")
        elif not any(r.get("tid") == 2 for r in lock):
            fail("2019 week 16 Lock claim tid %s not Fat Cats tid 2" % [r.get("tid") for r in lock])
        else:
            print("2019 w16 Lock tid 2", [r.get("status") for r in lock if r.get("tid") == 2])

        brown = [r for r in w16 if 4241372 in add_pids(r)]
        if not brown:
            fail("2019 week 16 missing Marquise Brown (pid 4241372)")
        else:
            ok = [r for r in brown if r.get("tid") == 3 and r.get("status") == "EXECUTED"]
            if not ok:
                fail("2019 week 16 Brown not EXECUTED to tid 3: %s" % [(r.get("tid"), r.get("status")) for r in brown])
            else:
                print("2019 w16 Brown EXECUTED tid 3")

        y19 = claims_in(bag, 2019)
        st = {r.get("status") for r in y19}
        if not (st & {"CANCELED", "FAILED_INVALIDPLAYERSOURCE", "FAILED_PLAYERALREADYDROPPED", "FAILED_ROSTERLOCK"}):
            fail(f"2019 waivers.json has no failed/canceled statuses: {sorted(st)}")
        else:
            print("2019 statuses include", sorted(st))

        if claims_in(bag, 2014):
            fail("2014 lookup returned invented claims")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/history.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"history.html HTTP {code}")
        else:
            print("history.html HTTP 200")
        wr = urllib.request.urlopen("http://127.0.0.1:8765/waivers.json", timeout=5)
        wcode = getattr(wr, "status", None) or wr.getcode()
        if wcode != 200:
            fail(f"waivers.json HTTP {wcode}")
        else:
            print("waivers.json HTTP 200")
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
