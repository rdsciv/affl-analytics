#!/usr/bin/env python3
"""CHI-39: Custody PAR is on History, from weekly PAR, not starter points."""
import csv
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
CSV = ROOT / "preview" / "custody_par_2025.csv"
fails = []
fail = lambda m: fails.append(m)


def close(a, b, tol=0.2):
    return abs(float(a) - float(b)) <= tol


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    draft_html = (SITE / "draft.html").read_text()
    draft_js = (SITE / "draft.js").read_text()

    if 'id="custody-par-block"' not in html:
        fail("history.html missing custody-par-block")
    if "Custody PAR" not in html:
        fail("history.html missing Custody PAR heading")
    if "renderCustodyPar" not in js:
        fail("history.js missing renderCustodyPar")
    if "custodyParRows" not in js:
        fail("history.js missing custodyParRows")
    if "parDrafted" not in js or "parTotal" not in js:
        fail("history.js does not read exported PAR")
    if "ptsDrafted" in js or "ptsKept" in js:
        fail("history.js reads starter/custody points instead of PAR")
    if "PAR_PRE2018" not in js:
        fail("history.js missing 2014–2017 unavailable copy")
    if "seasonYear < 2018" not in js:
        fail("history.js does not gate pre-2018 Custody PAR")
    if "started + benched" not in html and "started + benched" not in js:
        fail("subcopy missing rostered-week (started+benched)")
    if "GM grade" not in html and "GM grade" not in js:
        fail("subcopy missing GM grade")
    if "Trade Alpha is not in the total" not in html and "Trade Alpha is not in" not in js:
        fail("subcopy missing Trade Alpha exclusion")
    if "A.franchiseName" not in js and "A.franchiseTeam" not in js:
        fail("history.js missing franchise name helper")
    if "firstName(" in js or "firstName(" in html:
        fail("firstName() on History")
    if "Tittsburgh" in js or "Tittsburgh" in html:
        fail("Tittsburgh on History page")
    if "tradeAlpha" in js and ("parTotal + " in js or "+ row.tradeAlpha" in js or "+ r.tradeAlpha" in js):
        fail("Trade Alpha is being added into Custody PAR")
    # Draft points ledger must still exist — this card does not replace it
    if 'id="custody-block"' not in draft_html:
        fail("Draft points custody ledger was removed")
    if "ptsDrafted" not in draft_html:
        fail("Draft points ledger columns missing")

    gold = {}
    if CSV.exists():
        for row in csv.DictReader(CSV.open()):
            gold[row["owner_name"]] = row
    else:
        fail("preview/custody_par_2025.csv missing")

    y25 = json.loads((SITE / "years" / "2025.json").read_text())
    data = json.loads((SITE / "data.json").read_text())
    c = y25.get("custody")
    if not c or c.get("grain") != "weekly":
        fail("2025 custody grain missing/not weekly")
    if c.get("tradeAlpha") not in (None,):
        fail(f"2025 tradeAlpha should be unavailable/null, got {c.get('tradeAlpha')}")

    tid = next(t["id"] for t in data["seasons"]["2025"]["teams"] if t.get("owner") == "m18")
    if tid != 7:
        fail(f"Feelers tid {tid} != 7")
    row = next((t for t in (c.get("teams") or []) if t["tid"] == tid), None)
    if not row:
        fail("Feelers custody PAR row missing from 2025.json")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    wh = {a: par for a, par in con.execute(
        "SELECT acquisition, ROUND(SUM(par),1) FROM fact_player_week_par "
        "WHERE season=2025 AND team_id=? GROUP BY 1", (tid,))}
    drafted = wh.get("Drafted") or 0
    traded = wh.get("Traded in") or 0
    waiver = wh.get("Waiver") or 0
    fa = wh.get("FA") or 0
    unk = sum(v for a, v in wh.items() if a not in ("Drafted", "Traded in", "Waiver", "FA"))
    total = round(drafted + traded + waiver + fa + unk, 1)

    if not close(row.get("parTotal"), total):
        fail(f"Feelers parTotal site {row.get('parTotal')} != warehouse {total}")
    if not close(row.get("parDrafted"), drafted):
        fail(f"Feelers parDrafted site {row.get('parDrafted')} != warehouse {drafted}")
    if not close(row.get("parTradedIn"), traded):
        fail(f"Feelers parTradedIn site {row.get('parTradedIn')} != warehouse {traded}")
    if not close(row.get("parWaiver"), waiver):
        fail(f"Feelers parWaiver site {row.get('parWaiver')} != warehouse {waiver}")
    if not close(row.get("parFa"), fa):
        fail(f"Feelers parFa site {row.get('parFa')} != warehouse {fa}")
    if not close(row.get("parUnknown") or 0, unk):
        fail(f"Feelers parUnknown site {row.get('parUnknown')} != warehouse {unk}")
    if abs(unk) > 0.05 and "Unknown" not in html:
        fail("unknown PAR is non-zero but History has no Unknown column")

    # Gold CSV: total + drafted bind. waived = waiver+FA. traded_in/unknown are stale.
    g = gold.get("Ryan Childress") or {}
    if g:
        if not close(total, g["par_total"]):
            fail(f"Feelers warehouse total {total} != CSV {g['par_total']}")
        if not close(drafted, g["par_drafted"]):
            fail(f"Feelers warehouse drafted {drafted} != CSV {g['par_drafted']}")
        csv_waived = float(g["par_waived"])
        if not close(waiver + fa, csv_waived):
            fail(f"Feelers waiver+FA {waiver+fa} != CSV waived {csv_waived}")
        if not close(total, 607.6):
            fail(f"Feelers total {total} != 607.6")
        csv_traded = float(g["par_traded_in"])
        csv_unk = float(g["par_unknown"])
        if abs(csv_unk) > 0.05 and not close(traded, csv_traded + csv_unk):
            fail(f"CSV unknown {csv_unk} + traded {csv_traded} != warehouse traded {traded}")

    view = con.execute(
        "SELECT par_total, par_drafted, par_traded_in, par_waiver, par_fa "
        "FROM v_custody_par WHERE season=2025 AND team_id=?", (tid,)
    ).fetchone()
    if not view:
        fail("v_custody_par missing Feelers 2025")
    else:
        if not close(row["parTotal"], view[0]):
            fail(f"parTotal {row['parTotal']} != v_custody_par {view[0]}")
        if not close(row["parDrafted"], view[1]):
            fail(f"parDrafted != view {view[1]}")
        if not close(row["parTradedIn"], view[2]):
            fail(f"parTradedIn != view {view[2]}")

    # Trade Alpha must not be folded into the total
    if close(row["parTotal"], total + 1) and not close(row["parTotal"], total):
        fail("parTotal looks like it includes an invented Trade Alpha")
    for t in c["teams"]:
        if t.get("tradeAlpha"):
            fail(f"tid {t['tid']} has invented tradeAlpha {t.get('tradeAlpha')}")
        summed = round(
            (t.get("parDrafted") or 0) + (t.get("parTradedIn") or 0)
            + (t.get("parWaiver") or 0) + (t.get("parFa") or 0)
            + (t.get("parUnknown") or 0), 1)
        if not close(t.get("parTotal"), summed):
            fail(f"tid {t['tid']} parTotal {t.get('parTotal')} != sum of splits {summed}")

    y14 = json.loads((SITE / "years" / "2014.json").read_text())
    pre = y14.get("custody")
    if pre is not None:
        fail("2014 published weekly custody PAR (should be unavailable, not zeros)")
    else:
        print("2014 custody is null (unavailable)")

    feel = [f for f in data["franchises"] if f.get("owner") == "m18"]
    if feel and feel[0].get("currentName") != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel[0].get('currentName')}")

    print(
        f"2025 Feelers tid={tid} parTotal={row.get('parTotal')} "
        f"drafted={row.get('parDrafted')} traded={row.get('parTradedIn')} "
        f"waiver={row.get('parWaiver')} fa={row.get('parFa')} "
        f"unknown={row.get('parUnknown')}"
    )

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/history.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"history.html HTTP {code}")
        else:
            print("history.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"history.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
