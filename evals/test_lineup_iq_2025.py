#!/usr/bin/env python3
"""CHI-33 / AFFL-013: optimal-lineup / management metrics.

The season-aggregate `lineupIQ` stays 2018+ only: it needs a full roster every week
and pre-2018 has starters only. `lineupIQPre2018` is a different, narrower thing -
one record per 2014-2017 team-week whose roster snapshot could be dated, so the
bench for that one week is actually known. The two must never be pooled.
"""
import json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SITE=ROOT/"site"; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    y=json.loads((SITE/"years/2025.json").read_text())
    iq=y.get("lineupIQ") or []
    if len(iq)!=12: fail(f"2025 lineupIQ {len(iq)} != 12")
    for r in iq:
        if r.get("actual") is None or r.get("optimal") is None: fail(f"missing actual/optimal {r}")
        if r["optimal"]+1e-6 < r["actual"]: fail(f"optimal < actual team {r.get('teamId')}")
        if r.get("eff") is None: fail("missing eff")
        expect=round(r["actual"]/r["optimal"],3) if r["optimal"] else None
        if expect is not None and abs(r["eff"]-expect)>0.002:
            fail(f"eff {r['eff']} != actual/optimal {expect}")
    # Dated snapshots, straight from the warehouse - the eval decides what may be
    # published rather than trusting the exporter to have chosen correctly.
    con0=sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    dated={y:{(t,w) for t,w in con0.execute(
        "SELECT DISTINCT team_id, dated_week FROM fact_roster_snapshot_pre2018 "
        "WHERE season=? AND dated_week IS NOT NULL", (y,))} for y in range(2014,2018)}
    con0.close()

    n_pre=0
    for year in range(2014,2018):
        d=json.loads((SITE/f"years/{year}.json").read_text())
        if d.get("hasRosters"): fail(f"{year} hasRosters true")
        if d.get("lineupIQ"): fail(f"{year} published lineupIQ — pre-2018 has no full rosters")
        pre=d.get("lineupIQPre2018") or []
        n_pre+=len(pre)
        if year==2016 and pre:
            fail("2016 published lineupIQPre2018 — none of its snapshots are datable")
        for r in pre:
            key=(r.get("teamId"), r.get("week"))
            if key not in dated[year]:
                fail(f"{year} published lineupIQPre2018 for {key} — snapshot is not dated")
            if r.get("actual") is None or r.get("optimal") is None:
                fail(f"{year} missing actual/optimal {r}")
            elif r["optimal"]+1e-6 < r["actual"]:
                fail(f"{year} team {key} optimal {r['optimal']} < actual {r['actual']}")
            exp=round(r["actual"]/r["optimal"],3) if r.get("optimal") else None
            if exp is not None and abs(r.get("eff", 0)-exp)>0.002:
                fail(f"{year} team {key} eff {r.get('eff')} != {exp}")
            if r.get("phase") not in ("regular","playoff"):
                fail(f"{year} team {key} phase {r.get('phase')!r} not labelled")
    if not n_pre:
        fail("no lineupIQPre2018 published at all — the dated snapshots were lost")
    print(f"2025 lineupIQ {len(iq)} teams; pre-2018 season aggregate empty; "
          f"{n_pre} dated team-weeks in lineupIQPre2018")
    PREVIEW.mkdir(exist_ok=True)
    names={}
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    for r in con.execute("SELECT team_id, name FROM dim_team WHERE season=2025"):
        names[r["team_id"]]=r["name"]
    rows=sorted(iq, key=lambda r: -r["eff"])
    lines=["# 2025 lineup IQ","", "CHI-33 / AFFL-013. actual ÷ optimal.","",
           "Season aggregate is 2018+ only. 2014-2017 publish `lineupIQPre2018`: one record per",
           "team-week whose roster snapshot is dated, so the bench is known. Verified roster,",
           "computed optimal — see CONTRACTS.md. Never pooled with the season number.","",
           "| team | actual | optimal | wasted | eff |","| --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {names.get(r['teamId'], r['teamId'])} | {r['actual']} | {r['optimal']} | {r['wasted']} | {r['eff']} |")
    lines += ["","```","python3 evals/test_lineup_iq_2025.py","```",""]
    (PREVIEW/"LINEUP.md").write_text("\n".join(lines))
    print(PREVIEW/"LINEUP.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-33: 2025 lineup IQ present; pre-2018 only where dated"); return 0
if __name__=="__main__":
    sys.exit(main())
