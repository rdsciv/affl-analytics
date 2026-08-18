#!/usr/bin/env python3
"""History Transaction Log: dense claim+trade ledger, no FAAB column."""
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


def log_markup(html):
    m = re.search(r'id="tx-log-tbl"(.*?)</table>', html, re.S)
    return m.group(1) if m else ""


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()

    if "Transaction Log" not in html:
        fail("history.html missing Transaction Log")
    if 'id="tx-log-block"' not in html:
        fail("history.html missing tx-log-block")
    if 'id="tx-log-tbl"' not in html:
        fail("history.html missing tx-log-tbl")
    if "Waiver Report" not in html or "Transaction Counter" not in html:
        fail("history.html lost Waiver Report or Transaction Counter")
    if "waivers.json" not in js:
        fail("history.js does not load waivers.json")
    if "renderTxLog" not in js:
        fail("history.js missing renderTxLog")
    if "TX_PRE2018" not in js and "Transaction log starts in 2018" not in js:
        fail("history.js missing 2014 honest empty copy")
    if "seasonYear < 2018" not in js:
        fail("history.js does not gate pre-2018 log")
    if "Tittsburgh" in js:
        fail("history.js mentions Tittsburgh")
    if "buildTradeRows" not in js:
        fail("history.js missing trade rows")
    if "TRADE_PROPOSAL" in js:
        fail("history.js lists trade proposals")

    thead = log_markup(html)
    if not thead:
        fail("tx-log-tbl markup missing")
    else:
        if re.search(r"FAAB|Budget", thead, re.I):
            fail("Transaction Log table markup has FAAB/Budget column")
        if "Week" not in thead or "Team" not in thead or "Detail" not in thead:
            fail("Transaction Log missing Week/Team/Detail columns")

    path = SITE / "waivers.json"
    if not path.exists():
        fail("site/waivers.json missing")
        bag = {}
    else:
        bag = json.loads(path.read_text())
        if "2014" in bag:
            fail("waivers.json invented 2014 claims")
        w16 = claims_in(bag, 2019, 16)
        perr = [r for r in w16 if 2972460 in add_pids(r)]
        if not perr:
            fail("2019 week 16 missing Breshad Perriman (pid 2972460)")
        else:
            ok = [r for r in perr if r.get("tid") == 5 and r.get("status") == "EXECUTED"]
            fail_g = [r for r in perr if r.get("tid") == 3 and str(r.get("status") or "").startswith("FAILED")]
            if not ok:
                fail("2019 week 16 Perriman not EXECUTED to tid 5 Mad Dawgs: %s" %
                     [(r.get("tid"), r.get("status")) for r in perr])
            else:
                print("2019 w16 Perriman EXECUTED tid 5")
            if not fail_g:
                fail("2019 week 16 missing failed Gringos Perriman tid 3: %s" %
                     [(r.get("tid"), r.get("status")) for r in perr])
            else:
                print("2019 w16 Perriman FAILED tid 3")
        y19 = claims_in(bag, 2019)
        print("2019 claim rows", len(y19), "w16", len(w16))
        if claims_in(bag, 2014):
            fail("2014 lookup returned invented claims")

    data = json.loads((SITE / "data.json").read_text())
    MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
    franch = {f["owner"]: f.get("currentName") for f in data["franchises"]}
    by_tid = {}
    for t in (data["seasons"].get("2019") or {}).get("teams") or []:
        oid = MERGE.get(t.get("owner"), t.get("owner"))
        by_tid[t["id"]] = franch.get(oid) or t.get("name")
    if "Mad Dawgs" not in (by_tid.get(5) or ""):
        fail("tid 5 is not Mad Dawgs: %s" % by_tid.get(5))
    if "Gringos" not in (by_tid.get(3) or ""):
        fail("tid 3 is not Gringos: %s" % by_tid.get(3))

    y2019 = json.loads((SITE / "years" / "2019.json").read_text())
    trades = y2019.get("trades") or []
    print("2019 trade rows", len(trades), "log total", len(y19) + len(trades) if bag else "?")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/history.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"history.html HTTP {code}")
        else:
            print("history.html HTTP 200")
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
