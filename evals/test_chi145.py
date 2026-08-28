#!/usr/bin/env python3
"""CHI-145: Activity By Manager split series from raw mTransactions2.

Fails on: fact_transaction in builder/trades activity path; 2014–17 numeric
zeros; UPHOLD counted as accept; stacked five-series; missing
relatedTransactionId; dash/unavailable axis labels.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def fn_chunk(src: str, start: str, stop: str) -> str:
    if start not in src:
        fail(f"missing {start}")
        return ""
    rest = src.split(start, 1)[1]
    return rest.split(stop, 1)[0] if stop in rest else rest


def grab_fn(src: str, name: str) -> str:
    m = re.search(rf"function {re.escape(name)}\s*\(", src)
    if not m:
        return ""
    brace = src.find("{", m.start())
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start() : i + 1]
    return ""


def main() -> int:
    builder = ROOT / "scripts/build_activity.py"
    js_path = ROOT / "site/trades.js"
    html_path = ROOT / "site/trades.html"
    act_path = ROOT / "site/activity.json"

    if not builder.is_file():
        fail("missing scripts/build_activity.py")
        builder_src = ""
    else:
        builder_src = builder.read_text()

    js = js_path.read_text() if js_path.is_file() else ""
    html = html_path.read_text() if html_path.is_file() else ""
    if not js:
        fail("missing site/trades.js")
    if not html:
        fail("missing site/trades.html")

    act = None
    if not act_path.is_file():
        fail("missing site/activity.json — builder must write real files")
    else:
        act = json.loads(act_path.read_text())

    act_fn = fn_chunk(js, "function renderActivity", "function renderTrades")
    tname = fn_chunk(js, "function tName", "const short") or grab_fn(js, "tName")

    # --- fact_transaction is executed-only; rates cannot come from it ---
    if re.search(r"fact_transaction", builder_src):
        fail("builder still reads fact_transaction")
    if re.search(r"fact_transaction", act_fn):
        fail("trades.js activity path still mentions fact_transaction")
    if "txByTeam" in act_fn:
        fail("renderActivity still paints warehouse txByTeam (executed-only lump)")

    # --- pairing grain ---
    # Old collapse: one thread from PENDING+CANCELED pair via proposal_ids = set(proposals).
    # Proposed is the TRADE_PROPOSAL row; CANCELED is an outcome; PENDING stays out of the rate.
    if "proposal_ids = set(proposals)" in builder_src:
        fail("builder still collapses PENDING+CANCELED via proposal_ids = set(proposals)")
    if "relatedTransactionId" not in builder_src:
        fail("builder missing relatedTransactionId pairing")
    if re.search(r"relatedTransactionId", builder_src) is None:
        fail("builder does not read relatedTransactionId")

    # CHI-145: do not invent a PENDING+CANCELED thread collapse
    if re.search(r"if rel\b.*in proposal_ids", builder_src):
        fail("builder collapses PENDING+CANCELED via 'if rel ... in proposal_ids'")

    # --- UPHOLD is commish grain, not a second accept ---
    if "TRADE_UPHOLD" not in builder_src:
        fail("builder never mentions TRADE_UPHOLD — cannot prove it is excluded")
    uphold_chunk = ""
    if "TRADE_UPHOLD" in builder_src:
        # the UPHOLD branch must not increment tradesAccepted
        idx = builder_src.find("TRADE_UPHOLD")
        uphold_chunk = builder_src[max(0, idx - 80) : idx + 240]
    if "tradesAccepted" in uphold_chunk and "TRADE_UPHOLD" in uphold_chunk:
        # allow a comment that says it is excluded
        if not re.search(r"not a second accept|Not a second accept|excluded|continue", uphold_chunk):
            fail("TRADE_UPHOLD branch looks like it credits tradesAccepted")
    if re.search(r"typ == ['\"]TRADE_UPHOLD['\"].*tradesAccepted", builder_src, re.S):
        # crude: an increment on the same line / nearby without continue
        for m in re.finditer(r"if typ == ['\"]TRADE_UPHOLD['\"]:(.*?)(?=\n        if typ ==|\n    return managers)", builder_src, re.S):
            body = m.group(1)
            if "tradesAccepted" in body and "continue" not in body:
                fail("TRADE_UPHOLD counted as accept")

    if "TRADE_DECLINE" not in builder_src:
        fail("builder missing TRADE_DECLINE=decline")

    # --- 2014–17 never numeric zeros ---
    if act is not None:
        years = act.get("years") or act.get("seasons") or {}
        for y in (2014, 2015, 2016, 2017):
            rec = years.get(str(y)) or {}
            if rec.get("available") is True:
                fail(f"{y} marked available — ESPN log is a stub")
            managers = rec.get("managers") or rec.get("byOwner") or {}
            if managers:
                fail(f"{y} has manager counts (must be unavailable, never 0)")
            blob = json.dumps(rec)
            if re.search(r":\s*0\b", blob):
                fail(f"{y} payload contains numeric zeros")
        cum = act.get("cumulative") or act.get("career") or {}
        if int(cum.get("from") or 2018) < 2018:
            fail("cumulative includes pre-2018")
        if "2014" in json.dumps(cum.get("managers") or {}) and '"2014"' in json.dumps(cum):
            fail("cumulative payload still names 2014")

    if re.search(r"year\s*<\s*2018[^;\n]*\b0\b", act_fn):
        fail("renderActivity fills 2014–17 with numeric zeros")
    if re.search(r"unavailableYears.*0|2014.*waiverSubmitted.: 0", js):
        fail("trades.js hard-codes 2014–17 zeros")

    # season view must notice + empty chart, not paint zeros
    if "transaction log unavailable" not in act_fn and "does not retain transaction" not in act_fn:
        fail("2014–17 season view missing unavailable notice")
    if "year <= 2017" not in act_fn and "year < 2018" not in act_fn:
        fail("renderActivity does not gate 2014–17 as unavailable")

    # --- grouped, not stacked soup ---
    if "stack: 'a'" in act_fn or 'stack: "a"' in act_fn or "stack:'a'" in act_fn:
        fail("five-series still stacked (stack:'a')")
    if "stacked: true" in act_fn:
        fail("activity scales still stacked: true")
    for label in (
        "Waiver submitted",
        "Waiver won",
        "FA adds",
        "Trades proposed",
        "Trades accepted",
    ):
        if label not in act_fn:
            fail(f"missing grouped series {label!r}")
    if act_fn.count("label:") < 5:
        fail("renderActivity does not define five series")
    if "xProposed" not in act_fn and "logarithmic" not in act_fn:
        fail("Feelers proposed still shares a linear x-axis with the other series")
    if "xAxisID: \"xProposed\"" not in act_fn and "xAxisID: 'xProposed'" not in act_fn and "logarithmic" not in act_fn:
        fail("Trades proposed series is not on its own scale")

    # rates
    if "waiverSubmitted" not in act_fn or "waiverWon" not in act_fn:
        fail("hover/table missing won/submitted")
    if "tradesDeclined" not in act_fn or "tradesVetoed" not in act_fn:
        fail("acceptance rate missing decline/veto (accept/(accept+decline+veto))")
    if "fmtRate" not in js and "won / submitted" not in js:
        fail("missing waiver win rate helper")

    # --- fetch activity.json, not year txByTeam ---
    if "activity.json" not in js:
        fail("trades.js does not fetch activity.json")
    if "function loadActivity" not in js:
        fail("loadActivity missing")

    # --- CHI-112 axis: current names, never dash / never paint unavailable ---
    if "labels: names" not in act_fn:
        fail("renderActivity missing labels: names")
    if "tName(r.tid)" not in act_fn:
        fail("renderActivity labels path missing tName(r.tid)")
    if "autoSkip: false" not in act_fn:
        fail("autoSkip must be false")
    if "afterFit(scale)" not in act_fn:
        fail("afterFit padding missing")
    if "short(r.tid)" in act_fn:
        fail("chart labels must be full franchise names, not short()")
    if 'n !== "unavailable"' not in act_fn and "n !== 'unavailable'" not in act_fn:
        fail("renderActivity must drop unnamed / unavailable rows from the axis")
    for bad in ('|| "—"', "|| '—'", '|| "-"', "|| '-'", 'return "—"', "return '—'", 'return "-"', "return '-'"):
        if bad in tname:
            fail(f"tName still falls back to a dash: {bad}")
    if "—" in tname or re.search(r"return\s+[\"']-[\"']", tname):
        fail("tName body still contains a dash fallback")
    # axis labels must not be the string unavailable
    if re.search(r"labels:\s*\[.*unavailable", act_fn):
        fail("unavailable hard-coded as an axis label")
    if "function ownerKey" not in js:
        fail("ownerKey missing — ESPN sentinel must stay dropped")
    if "function tName" not in js:
        fail("tName missing — CHI-112 axis required")

    bust = re.search(r"trades\.js\?v=(\d+)", html)
    if not bust:
        fail("trades.html missing trades.js cache bust")
    elif int(bust.group(1)) < 9:
        fail(f"trades.js cache still v={bust.group(1)} (need v=9)")

    if 'id="activity-rates"' not in html:
        fail("trades.html missing the rates table")
    if "white-space: nowrap" not in html and "white-space:nowrap" not in html:
        fail("rates table missing nowrap — SUBMITTED will clip to SUB")
    if "overflow-x: auto" not in html and "overflow-x:auto" not in html:
        fail("rates wrap missing overflow-x:auto — SUB column clips instead of scrolling")
    if 'id="activity-note"' not in html:
        fail("trades.html missing the 2014–17 notice slot")

    # builder must use raw mTransactions2 week dumps + data.json seasons
    if "mTransactions2" not in builder_src:
        fail("builder does not read mTransactions2")
    if "data.json" not in builder_src:
        fail("builder does not map teamId+year via data.json")
    if "teamId" not in builder_src and "tid" not in builder_src:
        fail("builder does not read teamId")
    if "-2147483648" not in builder_src and "<= 0" not in builder_src and "<=0" not in builder_src:
        fail("builder does not drop teamId <= 0 / sentinel")

    # Feelers (m18) must have real split counts, not a lump
    if act is not None:
        m18 = (act.get("cumulative") or {}).get("managers", {}).get("m18")
        if not m18:
            fail("cumulative missing Feelers m18")
        else:
            if m18.get("waiverSubmitted", 0) <= 0:
                fail("Feelers waiverSubmitted is 0/missing — look like a stub")
            if m18.get("waiverWon", 0) > m18.get("waiverSubmitted", 0):
                fail("Feelers won > submitted")
            if m18.get("tradesAccepted", 0) > m18.get("tradesProposed", 0):
                fail("Feelers accepted > proposed")
            if m18.get("waiverSubmitted") == m18.get("waiverWon") and m18.get("waiverSubmitted", 0) > 0:
                fail("Feelers submitted == won — looks like fact_transaction executed-only")

        # BIND: m01 (Glory Holes alias) + m07 = one Chupacabras bar
        for scope, bag in [("cumulative", act.get("cumulative") or {})]:
            managers = bag.get("managers") or {}
            if "m01" in managers:
                fail("m01 is its own key in cumulative — must MERGE into m07 Chupacabras")
        for y, rec in (act.get("years") or {}).items():
            managers = rec.get("managers") or {}
            if "m01" in managers:
                fail(f"m01 is its own key in {y} — must MERGE into m07 Chupacabras")
        m07 = (act.get("cumulative") or {}).get("managers", {}).get("m07")
        if not m07:
            fail("cumulative missing Chupacabras m07")
        y2018 = ((act.get("years") or {}).get("2018") or {}).get("managers") or {}
        if (y2018.get("m07") or {}).get("waiverWon", 0) <= 0:
            fail("2018 Chupacabras waiverWon is 0 — 2018 EXECUTED waivers have sentinel teamId; recover from items")

        # Measured sender grain (Analyst 2026-08-28): proposed = PENDING send
        m18 = (act.get("cumulative") or {}).get("managers", {}).get("m18") or {}
        m07 = (act.get("cumulative") or {}).get("managers", {}).get("m07") or {}
        m04 = (act.get("cumulative") or {}).get("managers", {}).get("m04") or {}
        managers = (act.get("cumulative") or {}).get("managers") or {}
        league_prop = sum(v.get("tradesProposed", 0) for v in managers.values())
        league_acc = sum(v.get("tradesAccepted", 0) for v in managers.values())
        if m18.get("tradesProposed") != 2079:
            fail(f"Feelers proposed {m18.get('tradesProposed')} — expected 2079 PENDING sends")
        if m18.get("tradesAccepted") != 37:
            fail(f"Feelers accepted {m18.get('tradesAccepted')} — expected 37 sender-side")
        if m18.get("tradesDeclined") != 1238:
            fail(f"Feelers declined {m18.get('tradesDeclined')} — expected 1238 sender-side")
        if m18.get("tradesVetoed") != 7:
            fail(f"Feelers vetoed {m18.get('tradesVetoed')} — expected 7 sender-side")
        if m07.get("tradesProposed") != 311:
            fail(f"Chupacabras proposed {m07.get('tradesProposed')} — expected 311 PENDING sends")
        if m04.get("tradesProposed") != 20:
            fail(f"Chewbacca proposed {m04.get('tradesProposed')} — expected 20")
        if m04.get("tradesAccepted", 0) != 0:
            fail(f"Chewbacca accepted {m04.get('tradesAccepted')} — responder 3-accept / 100% bug")
        if m04.get("tradesDeclined", 0) != 0 or m04.get("tradesVetoed", 0) != 0:
            fail("Chewbacca rate denom must be 0 (unavailable), not responder outcomes")
        if league_prop > 5000:
            fail(f"league proposed {league_prop} still counts CANCELED/PENDING leak (~7545)")
        if league_prop < 3000:
            fail(f"league proposed {league_prop} dropped PENDING sends (closed-thread grain)")
        if league_acc > 80:
            fail(f"league accepted {league_acc} still looks responder-side (was 276)")

    # pairing grain: relatedTransactionId, UPHOLD is not accept
    spec = None
    builder_path = ROOT / "scripts/build_activity.py"
    if builder_path.is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_activity", builder_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        key = mod.deal_key({"id": "acc-1", "relatedTransactionId": "prop-9"})
        if key != ("relatedTransactionId", "prop-9"):
            fail(f"deal_key did not pair on relatedTransactionId: {key}")
        key18 = mod.deal_key({"id": "acc-1", "relatedTransactionId": None})
        if key18 != ("tx_id", "acc-1"):
            fail(f"2018 null related invented a link: {key18}")
        omap = {2025: {7: "m18", 3: "m08", 6: "m02", 2: "m06"}}
        txs = [
            {"id": "p1", "type": "TRADE_PROPOSAL", "teamId": 7, "status": "PENDING"},
            {
                "id": "a1",
                "type": "TRADE_ACCEPT",
                "teamId": 3,
                "status": None,
                "relatedTransactionId": "p1",
                "isLeagueManager": False,
            },
            {
                "id": "u1",
                "type": "TRADE_UPHOLD",
                "teamId": 7,
                "status": "EXECUTED",
                "relatedTransactionId": "p1",
                "isLeagueManager": True,
            },
        ]
        m = mod.tally_year(2025, txs, omap)
        if (m.get("m18") or {}).get("tradesProposed") != 1:
            fail(f"proposer not credited: {m.get('m18')}")
        if (m.get("m18") or {}).get("tradesAccepted") != 1:
            fail(f"sender accept not credited: {m.get('m18')}")
        if (m.get("m08") or {}).get("tradesAccepted", 0) != 0:
            fail("acceptance credited to responder, not the proposal sender")
        if (m.get("m18") or {}).get("tradesAccepted", 0) > 1:
            fail("TRADE_UPHOLD counted as a second Feelers accept")
        sent = [
            {"id": "w1", "type": "WAIVER", "status": "EXECUTED", "teamId": -2147483648,
             "items": [{"type": "ADD", "toTeamId": 7}]},
            {"id": "w2", "type": "WAIVER", "status": "EXECUTED", "teamId": 7},
        ]
        m3 = mod.tally_year(2025, sent, omap)
        if (m3.get("m18") or {}).get("waiverWon") != 2:
            fail(f"sentinel waiver not recovered from items: {m3.get('m18')}")
        if any(k.startswith("-") or k == "m01" for k in m3):
            fail("sentinel or m01 leaked into managers")
        canceled_as_proposal = [
            {"id": "pend1", "type": "TRADE_PROPOSAL", "teamId": 7, "status": "PENDING"},
            {
                "id": "canc1",
                "type": "TRADE_PROPOSAL",
                "teamId": 7,
                "status": "CANCELED",
                "relatedTransactionId": "pend1",
            },
            {"id": "canc2", "type": "TRADE_PROPOSAL", "teamId": 7, "status": "CANCELED"},
        ]
        m_c = mod.tally_year(2025, canceled_as_proposal, omap)
        if (m_c.get("m18") or {}).get("tradesProposed") != 1:
            fail("tradesProposed counts status==CANCELED as a proposal")
        if (m_c.get("m18") or {}).get("tradesAccepted", 0) != 0:
            fail("CANCELED-only fixture should not invent an accept")
        # Decline of a sent proposal credits the SENDER, not the decliner
        sent_declined = [
            {"id": "p-sent", "type": "TRADE_PROPOSAL", "teamId": 7, "status": "PENDING"},
            {
                "id": "d-resp",
                "type": "TRADE_DECLINE",
                "teamId": 3,
                "status": "EXECUTED",
                "relatedTransactionId": "p-sent",
            },
        ]
        m_d = mod.tally_year(2025, sent_declined, omap)
        if (m_d.get("m18") or {}).get("tradesDeclined") != 1:
            fail(f"decline of a sent proposal must credit the sender: {m_d}")
        if (m_d.get("m08") or {}).get("tradesDeclined", 0) != 0:
            fail("decline credited to the responder")
        # 2018 null related — do not invent a sender accept
        y2018 = [
            {"id": "p18", "type": "TRADE_PROPOSAL", "teamId": 2, "status": "PENDING"},
            {"id": "a18", "type": "TRADE_ACCEPT", "teamId": 2, "status": "PENDING", "relatedTransactionId": None},
        ]
        o18 = {2018: {2: "m04", 7: "m18"}}
        m18y = mod.tally_year(2018, y2018, o18)
        if (m18y.get("m04") or {}).get("tradesProposed") != 1:
            fail(f"2018 Chewbacca proposed missing: {m18y}")
        if (m18y.get("m04") or {}).get("tradesAccepted", 0) != 0:
            fail("2018 null related invented a sender accept (Chewbacca 100% bug)")

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("CHI-145: split series from raw mTransactions2; grouped; 2014-17 unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
