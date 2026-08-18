#!/usr/bin/env python3
"""Custody ledger is exported and Draft renders it with franchise names."""
import json, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
fails = []
def fail(m): fails.append(m)

html = (SITE / "draft.html").read_text()
js = (SITE / "draft.js").read_text()
if 'id="custody-block"' not in html: fail("custody block")
if "function renderCustody" not in js: fail("renderCustody")
if "A.franchiseTeam" not in js: fail("franchise names")
if "ptsUnknown" in html or "ptsUnknown" in js: fail("Unknown column still in UI")
if "how each manager" in js: fail("manager wording")
for k in ("ptsDrafted", "ptsTradedIn", "ptsWaiver", "ptsFa"):
    if k not in html: fail(f"missing {k} column")

y = json.loads((SITE / "years/2025.json").read_text())
data = json.loads((SITE / "data.json").read_text())
c = y.get("custody")
if not c or c.get("grain") != "weekly": fail("2025 custody grain")
tid = next(t["id"] for t in data["seasons"]["2025"]["teams"] if t.get("owner") == "m18")
if tid != 7: fail(f"Feelers tid {tid} != 7")
row = next((t for t in c["teams"] if t["tid"] == tid), None)
if not row: fail("Feelers row missing")
else:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    wh = {a: pts for a, pts in con.execute(
        "SELECT acquisition, ROUND(SUM(points),1) FROM fact_player_week_par "
        "WHERE season=2025 AND team_id=? GROUP BY 1", (tid,))}
    drafted = wh.get("Drafted") or 0
    traded = wh.get("Traded in") or 0
    waiver = wh.get("Waiver") or 0
    fa = wh.get("FA") or 0
    if abs(row["ptsDrafted"] - drafted) > 0.2: fail(f"drafted site {row['ptsDrafted']} != warehouse {drafted}")
    if abs(row["ptsTradedIn"] - traded) > 0.2: fail(f"traded site {row['ptsTradedIn']} != warehouse {traded}")
    if abs(row["ptsWaiver"] - waiver) > 0.2: fail(f"waiver site {row['ptsWaiver']} != warehouse {waiver}")
    if abs(row["ptsFa"] - fa) > 0.2: fail(f"fa site {row['ptsFa']} != warehouse {fa}")
    if abs((row["ptsWaiver"] + row["ptsFa"]) - row["ptsWaived"]) > 0.2:
        fail("waiver+FA != waived")
    if (row.get("ptsUnknown") or 0) != 0: fail(f"unknown {row.get('ptsUnknown')}")
    if abs(drafted - 718.9) > 0.2: fail(f"Feelers drafted {drafted}")
    if abs(traded - 1104.8) > 0.2: fail(f"Feelers traded in {traded}")
    if abs((waiver + fa) - 617.9) > 0.2: fail(f"Feelers waived {waiver+fa}")
    if row["ptsTradedAway"] <= 0: fail("no pts given in trades")
    if row["ptsDroppedAway"] <= 0: fail("no pts given in drops")
    adams = con.execute(
        "SELECT DISTINCT acquisition FROM fact_player_week_par "
        "WHERE season=2025 AND player_id=16800 AND team_id=?", (tid,)).fetchall()
    dowdle = con.execute(
        "SELECT DISTINCT acquisition FROM fact_player_week_par "
        "WHERE season=2025 AND player_id=4038815 AND team_id=?", (tid,)).fetchall()
    if adams != [("Traded in",)]: fail(f"Adams {adams}")
    if dowdle != [("Traded in",)]: fail(f"Dowdle {dowdle}")
    unk = con.execute(
        "SELECT COUNT(*) FROM fact_player_week_par "
        "WHERE season BETWEEN 2018 AND 2025 "
        "AND acquisition NOT IN ('Drafted','Traded in','Waiver','FA')").fetchone()[0]
    if unk: fail(f"{unk} residual unknown player-weeks")

pre = json.loads((SITE / "years/2014.json").read_text()).get("custody")
if pre is not None: fail("2014 should have no weekly custody")

print("FAIL" if fails else "PASS")
for f in fails: print(" -", f)
sys.exit(1 if fails else 0)
