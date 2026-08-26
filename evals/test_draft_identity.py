#!/usr/bin/env python3
"""Draft cumulative PPD + spend chart use current franchise names, not owners."""
import json, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
def fail(m): fails.append(m)

common = (SITE / "common.js").read_text()
djs = (SITE / "draft.js").read_text()
dhtml = (SITE / "draft.html").read_text()

if "memberName(t.owner)" in common:
    fail("ownerTeams still uses owner name")
if "function franchiseName" not in common:
    fail("franchiseName missing")
if "tid: +tid" in djs:
    fail("spend chart still coerces tid to number")
if "how each manager" in djs:
    fail("spend subtitle still says manager")
if "average $200 allocation" not in djs:
    fail("cumulative spend subtitle missing")
if "function ownerKey" not in djs:
    fail("ownerKey missing")
if "A.franchiseTeam" not in djs:
    fail("draft not using franchiseTeam")

data = json.loads((SITE / "data.json").read_text())
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
canon = lambda i: MERGE.get(str(i), str(i))
franch = {canon(f["owner"]): f for f in data["franchises"]}
members = data.get("members") or {}
owner_names = {v for v in members.values() if v}

# Simulate cumulative auction rollup the way draft.js now does.
per = {}
par_any = 0
for yp in sorted((SITE / "years").glob("*.json")):
    y = json.loads(yp.read_text())
    year = y.get("year") or int(yp.stem)
    draft = y.get("draft") or {}
    if not draft.get("auction"):
        continue
    owners = {t["id"]: canon(t["owner"]) for t in data["seasons"].get(str(year), {}).get("teams", []) if t.get("owner")}
    bases = {}
    for b in (y.get("draftValue") or {}).get("baselines") or []:
        bases[b["position"]] = b["baseline"]
    for p in draft.get("board") or []:
        tid = owners.get(p.get("tid"))
        if not tid:
            continue
        r = per.setdefault(tid, {"spend": 0, "pts": 0, "par": 0, "scored": 0, "years": set(), "byPos": defaultdict(float)})
        bid = p.get("bid") or 0
        r["spend"] += bid
        r["years"].add(year)
        pos = "DST" if p.get("pos") == "D/ST" else p.get("pos")
        r["byPos"][pos] += bid
        if p.get("pts") is not None:
            r["pts"] += p["pts"]
            r["scored"] += bid
            base = bases.get(pos)
            if base is not None:
                r["par"] += p["pts"] - base
                par_any += 1

if not per:
    fail("no auction rows")

labels = []
names = []
for tid, r in per.items():
    f = franch.get(tid)
    name = (f or {}).get("currentName") or ""
    if not name:
        fail(f"no currentName for {tid}")
    if name in owner_names:
        fail(f"currentName is an owner name: {name}")
    # last word = chart label
    short = name.split()[-1] if name.split() else "?"
    if short == "?":
        fail(f"chart label ? for {tid}")
    labels.append(short)
    names.append(name)
    ny = max(1, len(r["years"]))
    avg_spend = r["spend"] / ny
    if avg_spend > 260:
        fail(f"{name} avg spend ${avg_spend:.0f} still looks like career stack")

# Kafka / Feelers
kafka = [n for n in names if "Chupacabra" in n or "Kafka" in n]
if len(kafka) != 1:
    fail(f"Kafka/Chupacabras rows: {kafka}")
if "Jason Kafka" in names:
    fail("Jason Kafka still a team label")
if "Tanner Dunn" in names or "Patrick O'Neill" in names or "Alex Renney" in names:
    fail("owner first+last still used as team")
feel = franch.get("m18", {}).get("currentName")
if feel != "Grand Teeton Feelers":
    fail(f"Feelers name {feel}")
if "Grand Teeton Feelers" not in names:
    fail("Feelers missing from PPD rollup")
if "?" in labels:
    fail("question-mark chart labels")
if par_any == 0:
    fail("no PAR terms — cumulative PAR/$ will stay 0")

# uniqueness after merge
if len(names) != len(set(names)):
    fail(f"duplicate franchise rows: {names}")

print(f"teams={len(names)} labels={labels}")
print(f"names={names}")
print(f"par_terms={par_any}")
print("FAIL" if fails else "PASS")
for f in fails:
    print(" -", f)
sys.exit(1 if fails else 0)
