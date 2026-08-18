#!/usr/bin/env python3
"""History Waiver Value: pts after claim week, FAAB gated, no 2014 fiction."""
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def pts_after(con, season, tid, pid, claim_wk):
    rows = con.execute(
        "SELECT week, points FROM fact_roster_week "
        "WHERE season=? AND team_id=? AND player_id=?",
        (season, tid, pid),
    ).fetchall()
    return sum((pts or 0) for week, pts in rows if week > claim_wk)


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()

    if "Waiver Value" not in html:
        fail("history.html missing Waiver Value")
    if 'id="waiver-value-block"' not in html:
        fail("history.html missing waiver-value-block")
    if "renderWaiverValue" not in js:
        fail("history.js missing renderWaiverValue")
    if "ptsAfter" not in js:
        fail("history.js missing ptsAfter")
    if "r.w > claimWk" not in js and "week > claim" not in js:
        fail("history.js does not score week > claim week")
    if "VALUE_PRE2018" not in js and "Waiver value starts in 2018" not in js:
        fail("history.js missing 2014 honest empty copy")
    if "seasonYear < 2018" not in js:
        fail("history.js does not gate pre-2018 value")

    # Static markup must not advertise FAAB totals. JS may render them only if maxBid > 0.
    if "FAAB Spent" in html or "Avg FAAB" in html:
        fail("history.html has ungated FAAB Spent / Avg FAAB copy")
    if "if (faabOn)" not in js:
        fail("history.js does not gate FAAB chips behind faabOn")
    if "maxBid > 0" not in js:
        fail("history.js does not require a real bid > 0 for FAAB")

    bag_path = SITE / "waivers.json"
    if not bag_path.exists():
        fail("site/waivers.json missing")
        bag = {}
    else:
        bag = json.loads(bag_path.read_text())
        if "2014" in bag:
            fail("waivers.json invented 2014 claims")

    db = ROOT / "affl.db"
    if not db.exists():
        fail("affl.db missing")
    else:
        con = sqlite3.connect(db)
        # 2019 Drew Brees added week 5 by tid 5 (Mad Dawgs)
        brees = pts_after(con, 2019, 5, 2580, 5)
        print("2019 Brees ptsAfter (tid 5, after wk 5)", brees)
        if brees is None or brees < 0:
            fail(f"2019 Brees ptsAfter not numeric >= 0: {brees}")
        if brees < 100:
            fail(f"2019 Brees ptsAfter {brees} looks like full-season leak or miss")
        # 2022 Geno Smith added week 5 by tid 9 (Sanchitos)
        geno = pts_after(con, 2022, 9, 15864, 5)
        print("2022 Geno ptsAfter (tid 9, after wk 5)", geno)
        if geno is None or geno < 0:
            fail(f"2022 Geno ptsAfter not numeric >= 0: {geno}")
        if geno < 100:
            fail(f"2022 Geno ptsAfter {geno} looks like full-season leak or miss")
        con.close()

    # 2014 must not invent values
    y14 = SITE / "years" / "2014.json"
    if y14.exists():
        d14 = json.loads(y14.read_text())
        if d14.get("hasTx"):
            fail("2014 year file claims hasTx")
        if d14.get("trades"):
            fail("2014 year file invented trades")

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
