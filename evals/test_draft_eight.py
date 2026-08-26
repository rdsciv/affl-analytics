#!/usr/bin/env python3
"""Draft eight: Auction DNA + W1 + miles. Current names, hide 2014, no crash if keys missing."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(m):
    fails.append(m)


def main():
    html = (SITE / "draft.html").read_text()
    js = (SITE / "draft.js").read_text()
    data = json.loads((SITE / "data.json").read_text())
    members = data.get("members") or {}
    owner_names = {v for v in members.values() if v}

    if 'id="auction-dna-block"' not in html:
        fail("auction DNA card missing")
    if 'id="w1-block"' not in html:
        fail("week 1 vs acquired card missing")
    if 'id="miles-th"' not in html:
        fail("board miles column missing")
    if "hidden" not in html.split('id="auction-dna-block"', 1)[1][:80]:
        fail("auction DNA should start hidden")
    if "hidden" not in html.split('id="w1-block"', 1)[1][:80]:
        fail("w1 block should start hidden")
    if "draft.js?v=11" in html:
        fail("draft.js cache-bust still v=11")
    if "draft.js?v=" not in html:
        fail("draft.js query string missing")

    if "function teamCell" not in js:
        fail("teamCell name renderer missing")
    if "function renderAuctionDNA" not in js:
        fail("renderAuctionDNA missing")
    if "function renderW1" not in js:
        fail("renderW1 missing")
    if "function milesCell" not in js:
        fail("milesCell missing")
    if "function touchesAsOf" not in js:
        fail("touchesAsOf missing")
    if "A.franchiseTeam" not in js or "A.franchiseName" not in js:
        fail("draft not using franchise helpers")
    if "const CATES = [58, 40, 24, 13, 12, 9]" not in js:
        fail("Cates curve $58/$40/$24/$13/$12/$9 missing")
    if "function top6List" not in js or "function normalizeDna" not in js:
        fail("top6Spend array normalizer missing")
    # sibling contract: top6Spend is the 6-bid vector; catesCurve is the reference, not a team row
    if "Array.isArray(r.catesCurve) ? r.catesCurve" in js:
        fail("catesCurve used as a team's top-6 slots")

    # New tables go through teamCell -> teamOf -> franchiseTeam. Never owner first names.
    dna_fn = js.split("function renderAuctionDNA", 1)[1].split("function emptyW1", 1)[0]
    w1_fn = js.split("function renderW1", 1)[1].split("function milesRisk", 1)[0]
    cell_fn = js.split("function teamCell", 1)[1].split("function", 1)[0]
    for label, chunk in (("teamCell", cell_fn), ("renderAuctionDNA", dna_fn), ("renderW1", w1_fn)):
        if "memberName" in chunk or "ownerName" in chunk:
            fail(f"{label} uses owner name helper")
        if "was " in chunk or "inactive" in chunk:
            fail(f"{label} renders was/inactive")
        if "t.owner" in chunk and "t.name" not in chunk:
            fail(f"{label} displays owner id instead of franchise name")
    if "t.name" not in cell_fn:
        fail("teamCell does not render t.name")
    if "teamCell(r.tid)" not in dna_fn:
        fail("auction DNA table not using teamCell")
    if "teamCell(r.tid)" not in w1_fn:
        fail("w1 table not using teamCell")

    # 2014 / snake hides auction DNA; pre-2018 hides w1
    if "year < 2016" not in js and "year <= 2015" not in js:
        fail("2014–15 snake hide for auction DNA missing")
    if "year < 2018" not in js:
        fail("2014/pre-2018 hide for w1 missing")
    if "el.hidden = true" not in dna_fn and "el.hidden = true" not in js:
        fail("auction DNA never hides")
    if "year < 2018" not in w1_fn:
        fail("renderW1 missing 2018 gate")

    # Poll-safe: missing keys do not throw
    if "YD.auctionDna || []" not in js and "(YD && YD.auctionDna)" not in js:
        fail("auctionDna missing-key guard missing")
    if "YD.w1Acquired || []" not in js and "(YD && YD.w1Acquired)" not in js:
        fail("w1Acquired missing-key guard missing")
    if "return null" not in js.split("function touchesAsOf", 1)[1][:800]:
        fail("touchesAsOf does not return null when miles are missing")
    if "miles.json" not in js:
        fail("miles.json loader missing")

    MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
    canon = lambda i: MERGE.get(str(i), str(i))
    franch = {canon(f["owner"]): f for f in data["franchises"]}

    # 16 current names = every franchise that appears in an auction season.
    auction_owners = set()
    for yp in sorted((SITE / "years").glob("*.json")):
        y = json.loads(yp.read_text())
        year = y.get("year") or int(yp.stem)
        draft = y.get("draft") or {}
        if not draft.get("auction"):
            continue
        for t in (data.get("seasons") or {}).get(str(year), {}).get("teams", []):
            if t.get("owner"):
                auction_owners.add(canon(t["owner"]))
        # missing keys must be safe to read
        if y.get("auctionDna") not in (None, []):
            pass
        _ = (y.get("auctionDna") or [])
        _ = (y.get("w1Acquired") or [])

    names = []
    for oid in sorted(auction_owners):
        f = franch.get(oid) or {}
        name = f.get("currentName") or ""
        if not name:
            fail(f"no currentName for {oid}")
        if name in owner_names:
            fail(f"currentName is an owner name: {name}")
        names.append(name)

    if len(names) != 16:
        fail(f"expected 16 auction-era current names, got {len(names)}: {names}")
    if len(names) != len(set(names)):
        fail(f"duplicate franchise rows: {names}")

    kafka = [n for n in names if "Chupacabra" in n or "Kafka" in n]
    if len(kafka) != 1:
        fail(f"Kafka/Chupacabras rows: {kafka}")
    if "Jason Kafka" in names:
        fail("Jason Kafka still a team label")
    for banned in ("Tanner Dunn", "Patrick O'Neill", "Alex Renney", "Ryan Childress", "Jason Kafka"):
        if banned in names:
            fail(f"owner name used as team: {banned}")
        if banned in dna_fn or banned in w1_fn or banned in cell_fn:
            fail(f"owner name hardcoded in new renderer: {banned}")

    feel = franch.get("m18", {}).get("currentName")
    if feel != "Grand Teeton Feelers":
        fail(f"Feelers name {feel}")
    if "Grand Teeton Feelers" not in names:
        fail("Feelers missing from auction-era rollup")

    # Feelers 2025 is team_id 7 / m18
    t2025 = {t["id"]: t for t in (data.get("seasons") or {}).get("2025", {}).get("teams", [])}
    feel_t = t2025.get(7) or {}
    if feel_t.get("owner") != "m18":
        fail(f"2025 team_id 7 owner is {feel_t.get('owner')}, expected m18")
    if feel_t.get("name") != "Grand Teeton Feelers":
        fail(f"2025 team_id 7 name is {feel_t.get('name')}")

    # 2014 year file: snake, no auctionDna / w1 — page must hide, not crash
    y2014 = json.loads((SITE / "years" / "2014.json").read_text())
    if y2014.get("draft", {}).get("auction"):
        fail("2014 is unexpectedly auction")
    if y2014.get("auctionDna"):
        fail("2014 already has auctionDna; hide rule still required")
    if y2014.get("w1Acquired"):
        fail("2014 already has w1Acquired; hide rule still required")

    y2025 = json.loads((SITE / "years" / "2025.json").read_text())
    missing = []
    if not y2025.get("auctionDna"):
        missing.append("auctionDna")
    if not y2025.get("w1Acquired"):
        missing.append("w1Acquired")
    bio = json.loads((SITE / "player_bio.json").read_text())
    sample = next(iter(bio.values())) if bio else {}
    has_miles = (SITE / "miles.json").exists() or (
        isinstance(sample, dict) and ("careerNflTouchesAsOf" in sample or "nflTouchesBySeason" in sample)
    )
    if not has_miles:
        missing.append("miles (player_bio/miles.json)")

    print(f"teams={len(names)}")
    print(f"names={names}")
    print(f"kafka={kafka}")
    print(f"feelers={feel}")
    print(f"missing_json={missing}")
    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
