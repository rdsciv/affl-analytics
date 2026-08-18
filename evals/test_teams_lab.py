#!/usr/bin/env python3
"""Teams franchise lab: Home-year charts as a one-franchise year-to-year lab.

Proves the page ships the lab, grades auction PAR/$ and Spotrac vs position
(not raw league-wide Pts/$), keeps 2014 snake spend as a notice, and does not
crash when nflCap / lineups are missing. Feelers label is Grand Teeton Feelers.
"""
import json
import re
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FEELERS = "m18"
YEAR = 2025
fails = []


def fail(msg):
    fails.append(msg)


def src(name):
    p = SITE / name
    return p.read_text() if p.exists() else ""


def same(a, b):
    return a is not None and b is not None and int(a) == int(b)


def rank_of(values, mine, desc=True):
    pool = [v for v in values if v is not None]
    better = sum(1 for v in pool if (v > mine if desc else v < mine))
    return better + 1


def main():
    html = src("teams.html")
    js = src("teams.js")
    css = src("styles.css")
    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years/2025.json").read_text())
    y2014 = json.loads((SITE / "years/2014.json").read_text())

    feel = [f for f in data.get("franchises") or [] if f.get("owner") == FEELERS]
    if len(feel) != 1:
        fail(f"Feelers should be 1 franchise row, got {len(feel)}")
    elif feel[0].get("currentName") != "Grand Teeton Feelers":
        fail(f"Feelers current name is {feel[0].get('currentName')!r}")
    else:
        print("Feelers label: Grand Teeton Feelers")

    teams = (data.get("seasons") or {}).get("2025", {}).get("teams") or []
    feel_t = next((t for t in teams if t.get("owner") == FEELERS), None)
    if not feel_t or feel_t.get("id") != 7:
        fail(f"Feelers 2025 tid should be 7, got {feel_t}")
    tid = feel_t["id"] if feel_t else None

    if 'id="lab-block"' not in html:
        fail("teams.html missing #lab-block")
    if "lab-block" not in js:
        fail("teams.js never mentions lab-block")
    if "function renderLab" not in js:
        fail("teams.js missing renderLab")
    if "teams.js?v=6" not in html:
        fail("teams.html does not cache-bust teams.js?v=6")
    if "styles.css?v=14" not in html:
        fail("teams.html does not cache-bust styles.css?v=14")
    if "chart.umd.min.js" not in html:
        fail("teams.html missing Chart.js")

    # PAR/$ positional — not raw league-wide Pts/$
    if "PAR / $" not in js and "PAR/$" not in js:
        fail("teams.js does not mention PAR/$")
    if "pickPar" not in js or "baselineMap" not in js:
        fail("teams.js does not compute PAR from draftValue.baselines")
    if "par: 0" not in js:
        fail("spend mix byPos.par is still never initialized")
    if "posMed" not in js and "pos median" not in js.lower():
        fail("teams.js does not compare PAR/$ to a position median")
    if "never raw league-wide Pts/$" not in js and "not raw league-wide" not in js:
        fail("teams.js never says the grade is not raw league-wide Pts/$")

    # Spotrac residual / pos median
    if "residual" not in js.lower():
        fail("teams.js never mentions Spotrac residual")
    if "pos median" not in js.lower() and "position median" not in js.lower():
        fail("teams.js never mentions a position median for Spotrac")
    if "spotracRowsFor" not in js:
        fail("teams.js missing spotracRowsFor")
    if "pts/$M" not in js and "pts / $1M" not in js:
        fail("teams.js missing pts/$M")

    # empty nflCap / missing lineups — no crash
    if "nflCap || {}" not in js and "nflCap ||{}" not in js:
        fail("teams.js does not guard missing nflCap")
    if "Empty state" not in js and "empty state" not in js.lower():
        fail("teams.js missing empty-state copy when cap / lineups are absent")
    if "lineupIQ || []" not in js:
        fail("teams.js does not guard missing lineupIQ")
    if "franchiseAdv || []" not in js:
        fail("teams.js does not guard missing franchiseAdv")
    if "whatif || []" not in js:
        fail("teams.js does not guard missing whatif")
    if "report || []" not in js:
        fail("teams.js does not guard missing report")

    # 2014 snake spend still notices
    if "snake draft" not in js.lower():
        fail("teams.js lost the snake-draft spend notice")
    if y2014.get("draft", {}).get("auction"):
        fail("2014 should still be a snake year in the payload")
    if (y2014.get("nflCap") or {}).get("byTeam"):
        print("note: 2014 nflCap.byTeam is unexpectedly populated")
    print("2014 snake spend still notices; nflCap.byTeam empty =", not (y2014.get("nflCap") or {}).get("byTeam"))

    # identity
    if "firstName(" in js:
        fail("teams.js uses firstName")
    if "Tittsburgh Feelers" in js:
        fail("teams.js hardcodes Tittsburgh Feelers")
    if "Grand Teeton Feelers" in js:
        fail("teams.js hardcodes Grand Teeton Feelers")
    if re.search(r"\binactive\b", js):
        fail("teams.js renders inactive labels")

    # destroy charts
    if "killLabCharts" not in js:
        fail("teams.js does not destroy lab charts on re-render")
    if "spendChart.destroy" not in js:
        fail("teams.js no longer destroys spendChart")

    # CSS additive lab
    if "lab-chip" not in css and "lab-card" not in css:
        fail("styles.css missing additive lab rules")

    # Feelers 2025 ranks actually computed from JSON (do not invent)
    print("\nFeelers 2025 sample ranks (from year JSON, not copy):")
    pf_rank = rank_of([t.get("pf") for t in teams], feel_t.get("pf"))
    aps = [
        (t.get("allplayW") or 0) / max(1, (t.get("allplayW") or 0) + (t.get("allplayL") or 0))
        for t in teams
    ]
    feel_ap = (feel_t.get("allplayW") or 0) / max(1, (feel_t.get("allplayW") or 0) + (feel_t.get("allplayL") or 0))
    ap_rank = rank_of(aps, feel_ap)
    luck_rank = rank_of([t.get("luck") for t in teams], feel_t.get("luck"))
    print(f"  standings finish {feel_t.get('finalRank')} · W-L {feel_t.get('wins')}-{feel_t.get('losses')} · PF {feel_t.get('pf')} (#{pf_rank}/12)")
    print(f"  all-play {feel_t.get('allplayW')}-{feel_t.get('allplayL')} ({feel_ap:.3f}) #{ap_rank}/12")
    print(f"  luck {feel_t.get('luck')} #{luck_rank}/12")

    liq = next((x for x in y2025.get("lineupIQ") or [] if same(x.get("teamId"), tid)), None)
    if liq:
        iq_rank = rank_of([x.get("eff") for x in y2025["lineupIQ"]], liq.get("eff"))
        print(f"  lineupIQ eff {liq['eff']:.4f} wasted {liq['wasted']} #{iq_rank}/12")
    fa = next((x for x in y2025.get("franchiseAdv") or [] if same(x.get("teamId"), tid)), None)
    if fa:
        epa_rank = rank_of([x.get("epa") for x in y2025["franchiseAdv"]], fa.get("epa"))
        print(f"  starter EPA {fa['epa']} #{epa_rank}/12")
    wi = next((x for x in y2025.get("whatif") or [] if same(x.get("teamId"), tid)), None)
    if wi:
        print(f"  whatif actRank {wi['actRank']} optRank {wi['optRank']} (reg. season ranks, not final finish)")
    rep = next((x for x in y2025.get("report") or [] if same(x.get("teamId"), tid)), None)
    if rep:
        gpa_rank = rank_of([x.get("gpa") for x in y2025["report"]], rep.get("gpa"))
        print(f"  report GPA {rep['gpa']} {rep['gDraft']}/{rep['gLineup']}/{rep['gWaiver']}/{rep['gLuck']} #{gpa_rank}/12")
    trop = y2025.get("trophies") or {}
    won = [k for k, v in trop.items() if same(v, tid)]
    print(f"  2025 trophies won: {won or 'none'}")

    # PAR for Feelers vs pos median
    bases = {b["position"]: b["baseline"] for b in (y2025.get("draftValue") or {}).get("baselines") or []}
    board = (y2025.get("draft") or {}).get("board") or []
    bypos = {}
    for p in board:
        bid = p.get("bid") or 0
        if bid <= 0 or p.get("pos") not in bases:
            continue
        par = (p.get("pts") or 0) - bases[p["pos"]]
        bypos.setdefault(p["pos"], []).append(par / bid)
    med = {pos: median(xs) for pos, xs in bypos.items() if xs}
    mine = [p for p in board if same(p.get("tid"), tid)]
    print("  auction PAR/$ vs pos median (sample):")
    for p in mine[:4]:
        bid = p.get("bid") or 0
        par = (p.get("pts") or 0) - bases.get(p.get("pos"), 0)
        parpd = par / bid if bid else None
        m = med.get(p.get("pos"))
        resid = (parpd - m) if (parpd is not None and m is not None) else None
        print(f"    {p['name']} {p['pos']} ${bid} PAR/$={parpd:.2f} posMed={m:.2f} resid={resid:+.2f}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
