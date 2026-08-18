#!/usr/bin/env python3
"""History/Draft expose positional PPD; Feelers auction math is real."""
import json, sys
from pathlib import Path
SITE = Path(__file__).resolve().parents[1] / "site"
fails=[]
def fail(m): fails.append(m)
html=(SITE/"history.html").read_text(); js=(SITE/"history.js").read_text()
dhtml=(SITE/"draft.html").read_text(); djs=(SITE/"draft.js").read_text()
if "was " in js or "inactive" in js: fail("was/inactive labels")
if "id=\"ppd-tbl\"" not in html: fail("ppd-tbl")
if "ppdQB" not in js: fail("positional PPD")
if "id=\"pos-ppd-tbl\"" not in dhtml: fail("draft pos-ppd-tbl")
if "renderPosPPD" not in djs: fail("draft renderPosPPD")
data=json.loads((SITE/"data.json").read_text())
MERGE={"m01":"m07","m03":"m08","m20":"m10"}
canon=lambda i: MERGE.get(i,i)
spend=pts=scored=0
for yp in (SITE/"years").glob("*.json"):
    y=json.loads(yp.read_text()); year=y.get("year") or int(yp.stem)
    owners={t["id"]:canon(t["owner"]) for t in data["seasons"].get(str(year),{}).get("teams",[]) if t.get("owner")}
    for p in (y.get("draft") or {}).get("board") or []:
        if owners.get(p.get("tid"))!="m18": continue
        bid=p.get("bid") or 0; spend+=bid
        if p.get("pts") is not None: pts+=p["pts"]; scored+=bid
if spend<=0: fail("Feelers no auction spend")
if scored<=0 or pts/scored<=0: fail("Feelers PPD missing")
print(f"Feelers pts/$ = {pts/scored:.2f} on ${spend}")
print("FAIL" if fails else "PASS")
[print(" -",f) for f in fails]
sys.exit(1 if fails else 0)
