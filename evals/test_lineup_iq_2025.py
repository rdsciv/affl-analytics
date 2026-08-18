#!/usr/bin/env python3
"""CHI-33 / AFFL-013: optimal-lineup / management metrics. Pre-2018 stays unavailable."""
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
    for year in range(2014,2018):
        d=json.loads((SITE/f"years/{year}.json").read_text())
        if d.get("hasRosters"): fail(f"{year} hasRosters true")
        if d.get("lineupIQ"): fail(f"{year} published lineupIQ — pre-2018 solver not validated")
    print(f"2025 lineupIQ {len(iq)} teams; pre-2018 empty")
    PREVIEW.mkdir(exist_ok=True)
    names={}
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    for r in con.execute("SELECT team_id, name FROM dim_team WHERE season=2025"):
        names[r["team_id"]]=r["name"]
    rows=sorted(iq, key=lambda r: -r["eff"])
    lines=["# 2025 lineup IQ","", "CHI-33 / AFFL-013. actual ÷ optimal. Pre-2018 unavailable (not published).","",
           "| team | actual | optimal | wasted | eff |","| --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {names.get(r['teamId'], r['teamId'])} | {r['actual']} | {r['optimal']} | {r['wasted']} | {r['eff']} |")
    lines += ["","```","python3 evals/test_lineup_iq_2025.py","```",""]
    (PREVIEW/"LINEUP.md").write_text("\n".join(lines))
    print(PREVIEW/"LINEUP.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-33: 2025 lineup IQ present; pre-2018 unpublished"); return 0
if __name__=="__main__":
    sys.exit(main())
