#!/usr/bin/env python3
"""Build site/activity.json from raw ESPN mTransactions2 week dumps.

Grain (CHI-145)
---------------
Source: raw week dumps `{year}_mTransactions2_wXX.json` (transactions[]).
Never reads the warehouse transaction fact table or its CSV export.

tx_id (transactions[].id) ONLY dedupes the same event repeated across week
dumps. TRADE_PROPOSAL and TRADE_ACCEPT never share tx_id (0 overlap). Pair
proposal → accept / decline / veto on relatedTransactionId when present.

2018: relatedTransactionId is null on every row. Dedup by id; do not invent
links. Those PENDING sends stay open (out of the rate).

TRADE_UPHOLD is commissioner grain after a review window — NOT a second
accept. Skip it for accepted counts.

Commissioner-executed TRADE_ACCEPT still pairs to the sender's PENDING id.
Do not credit the commish's ESPN slot. TRADE_UPHOLD is never a second accept.

teamId <= 0 (including ESPN sentinel -2147483648) is dropped. Never mapped.

Owner key: ESPN teamId + year → site/data.json seasons[year].teams[].owner
then canon MERGE m01→m07, m03→m08, m20→m10. Franchise, not ESPN slot.

Counts per owner, per available year:

  waiverSubmitted  unique WAIVER rows (PENDING / EXECUTED / FAILED_* / CANCELED)
  waiverWon        WAIVER status == EXECUTED
  waiverFailed     WAIVER status startswith FAILED_
  waiverCanceled   WAIVER status == CANCELED
  faAdds           FREEAGENT status == EXECUTED with an ADD item (no fake claim split)
  tradesProposed   unique TRADE_PROPOSAL sends after id-dedupe with status != CANCELED
                   (PENDING is the send; CANCELED is a withdrawal, not a second proposal)
  tradesAccepted   unique sent threads whose related ACCEPT landed (sender of the PROPOSAL)
  tradesDeclined   unique sent threads whose related DECLINE landed (sender, not the decliner)
  tradesVetoed     unique sent threads whose related VETO landed (sender, not the vetoer)

Rates (UI, not stored as painted 0 for missing years):
  waiver win  = won / submitted
  acceptance  = accept / (accept + decline + veto) of THAT SENDER's closed outcomes.
                PENDING is not in the denominator. CANCELED is not veto.
                Pair ACCEPT/DECLINE/VETO back to the TRADE_PROPOSAL via relatedTransactionId.
                2018 related is null — do not invent; sender outcomes stay 0 (rate unavailable).

2014–17: raw files are stubs (no transactions[]). Years are available=false
with no manager counts — missing, never 0.

Cumulative: 2018–25 only. 2014–17 excluded.

Usage:
  AFFL_TX_RAW=/workspace/affl-viz/espn51418/raw \\
  AFFL_DATA_JSON=site/data.json \\
  AFFL_ACTIVITY_OUT=site/activity.json \\
    python3 scripts/build_activity.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "scripts" else HERE

RAW = Path(os.environ.get("AFFL_TX_RAW", "/workspace/affl-viz/espn51418/raw"))
DATA_JSON = Path(os.environ.get("AFFL_DATA_JSON", str(ROOT / "site" / "data.json")))
OUT = Path(os.environ.get("AFFL_ACTIVITY_OUT", str(ROOT / "site" / "activity.json")))

YEARS = list(range(2014, 2026))
AVAILABLE_YEARS = list(range(2018, 2026))
UNAVAILABLE_YEARS = list(range(2014, 2018))
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
SENTINEL = -2147483648

ZERO_KEYS = (
    "waiverSubmitted",
    "waiverWon",
    "waiverFailed",
    "waiverCanceled",
    "faAdds",
    "tradesProposed",
    "tradesAccepted",
    "tradesDeclined",
    "tradesVetoed",
)


def canon(oid):
    if oid is None or oid == "":
        return None
    s = str(oid)
    return MERGE.get(s, s)


def load_owner_map(path: Path) -> dict[int, dict[int, str]]:
    data = json.loads(path.read_text())
    out: dict[int, dict[int, str]] = {}
    for y, season in (data.get("seasons") or {}).items():
        year = int(y)
        slot = {}
        for t in season.get("teams") or []:
            tid = t.get("id")
            owner = canon(t.get("owner"))
            if tid is None or not owner:
                continue
            slot[int(tid)] = owner
        out[year] = slot
    return out


def valid_tid(tid) -> bool:
    try:
        n = int(tid)
    except (TypeError, ValueError):
        return False
    if n <= 0 or n == SENTINEL:
        return False
    return True


def owner_of(omap, year, tid):
    if not valid_tid(tid):
        return None
    return omap.get(year, {}).get(int(tid))


def extract_txs(blob):
    recs = blob if isinstance(blob, list) else [blob]
    out = []
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        txs = rec.get("transactions")
        if isinstance(txs, list):
            out.extend(txs)
    return out


def load_year_txs(raw: Path, year: int) -> tuple[list[dict], bool]:
    """Return (deduped txs, had_any_transactions_key_with_rows).

    Stubs (2014–17) have no transactions[]. That is unavailable, not zero.
    """
    files = sorted(raw.glob(f"{year}_mTransactions2_w*.json"))
    if not files:
        files = sorted(raw.glob(f"{year}_mTransactions2*.json"))
    by_id = {}
    saw_rows = False
    for fp in files:
        try:
            blob = json.loads(fp.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        txs = extract_txs(blob)
        if txs:
            saw_rows = True
        for t in txs:
            tid = t.get("id")
            if not tid:
                continue
            if tid not in by_id:
                by_id[tid] = t
    return list(by_id.values()), saw_rows


def item_teams(tx) -> list[int]:
    teams = []
    for it in tx.get("items") or []:
        if it.get("type") != "TRADE":
            continue
        for key in ("fromTeamId", "toTeamId"):
            v = it.get(key)
            if valid_tid(v):
                n = int(v)
                if n not in teams:
                    teams.append(n)
    return teams


def has_add(tx) -> bool:
    return any(it.get("type") == "ADD" for it in (tx.get("items") or []))


def movement_tid(tx):
    """Claimant / FA team. 2018 EXECUTED waivers use sentinel teamId; items.toTeamId is the roster move."""
    tid = tx.get("teamId")
    if valid_tid(tid):
        return tid
    for it in tx.get("items") or []:
        if it.get("type") == "ADD" and valid_tid(it.get("toTeamId")):
            return it.get("toTeamId")
    ta = tx.get("teamActions") or {}
    if isinstance(ta, dict):
        for k, v in ta.items():
            if str(v).upper() == "INVOLVED" and valid_tid(k):
                return k
    for it in tx.get("items") or []:
        for key in ("toTeamId", "fromTeamId"):
            if valid_tid(it.get(key)):
                return it.get(key)
    return None


def deal_key(tx) -> tuple:
    """Pair on relatedTransactionId when ESPN set it. Else this tx's own id.

    2018 relatedTransactionId is null — we do not invent a proposal link.
    """
    rel = tx.get("relatedTransactionId")
    if rel not in (None, "", 0, "0"):
        return ("relatedTransactionId", str(rel))
    return ("tx_id", str(tx.get("id") or ""))


def empty_row(owner: str) -> dict:
    row = {"ownerKey": owner}
    for k in ZERO_KEYS:
        row[k] = 0
    return row


def tally_year(year: int, txs: list[dict], omap: dict) -> dict[str, dict]:
    managers: dict[str, dict] = {}

    def row(oid: str) -> dict:
        if oid not in managers:
            managers[oid] = empty_row(oid)
        return managers[oid]

    def credit(tid, field, n=1):
        oid = owner_of(omap, year, tid)
        if not oid:
            return
        row(oid)[field] += n

    proposals = {}
    accepts = []
    declines = []
    vetoes = []

    for t in txs:
        typ = t.get("type")
        status = t.get("status")
        tid = t.get("teamId")

        if typ == "WAIVER":
            claimant = movement_tid(t)
            if not valid_tid(claimant):
                continue
            credit(claimant, "waiverSubmitted")
            if status == "EXECUTED":
                credit(claimant, "waiverWon")
            elif isinstance(status, str) and status.startswith("FAILED"):
                credit(claimant, "waiverFailed")
            elif status == "CANCELED":
                credit(claimant, "waiverCanceled")
            continue

        if typ == "FREEAGENT":
            if status != "EXECUTED":
                continue
            if not has_add(t):
                continue
            dest = movement_tid(t)
            if not valid_tid(dest):
                continue
            credit(dest, "faAdds")
            continue

        if typ == "TRADE_PROPOSAL":
            # PENDING is the send. CANCELED is a withdraw, not a second proposal
            # and not a pairing target (outcomes point at the PENDING id).
            if status == "PENDING" and valid_tid(tid):
                proposals[str(t.get("id"))] = t
            continue

        if typ == "TRADE_UPHOLD":
            # Commish grain. Not a second accept.
            continue

        if typ == "TRADE_ACCEPT":
            if status == "CANCELED":
                continue
            accepts.append(t)
            continue

        if typ == "TRADE_DECLINE":
            declines.append(t)
            continue

        if typ == "TRADE_VETO":
            vetoes.append(t)
            continue

    # Proposed = PENDING TRADE_PROPOSAL only. Open sends stay in proposed
    # and out of the rate. Do not collapse to closed threads.
    for t in proposals.values():
        credit(t.get("teamId"), "tradesProposed")

    def proposal_sender(tx):
        """Sender of the related TRADE_PROPOSAL. 2018 related is null — no invent."""
        rel = tx.get("relatedTransactionId")
        if rel in (None, "", 0, "0"):
            return None
        prop = proposals.get(str(rel))
        if not prop:
            return None
        tid = prop.get("teamId")
        return tid if valid_tid(tid) else None

    def credit_sender(rows, field):
        seen: set[tuple[str, str]] = set()
        for t in rows:
            sid = proposal_sender(t)
            if sid is None:
                continue
            oid = owner_of(omap, year, sid)
            if not oid:
                continue
            mark = (oid, str(t.get("relatedTransactionId")))
            if mark in seen:
                continue
            seen.add(mark)
            row(oid)[field] += 1

    # Outcomes hang off relatedTransactionId and credit the PROPOSER.
    # Responder teamId on ACCEPT/DECLINE/VETO is not the series grain.
    # TRADE_UPHOLD is commish grain — never a second accept (not in accepts).
    credit_sender(accepts, "tradesAccepted")
    credit_sender(declines, "tradesDeclined")
    credit_sender(vetoes, "tradesVetoed")

    return managers


def add_into(dst: dict, src: dict) -> None:
    for oid, rec in src.items():
        if oid not in dst:
            dst[oid] = empty_row(oid)
        for k in ZERO_KEYS:
            dst[oid][k] += rec.get(k, 0)


def main() -> int:
    if not RAW.is_dir():
        print(f"missing raw dumps: {RAW}", file=sys.stderr)
        return 2
    if not DATA_JSON.is_file():
        print(f"missing data.json: {DATA_JSON}", file=sys.stderr)
        return 2
    omap = load_owner_map(DATA_JSON)

    years_out = {}
    cumulative: dict[str, dict] = {}
    for year in YEARS:
        txs, saw_rows = load_year_txs(RAW, year)
        if year in UNAVAILABLE_YEARS or not saw_rows:
            years_out[str(year)] = {"available": False}
            continue
        managers = tally_year(year, txs, omap)
        years_out[str(year)] = {"available": True, "managers": managers}
        if year in AVAILABLE_YEARS:
            add_into(cumulative, managers)

    payload = {
        "grain": (
            "raw ESPN mTransactions2 week dumps; tx_id dedupes week repeats only; "
            "tradesProposed is the TRADE_PROPOSAL send (PENDING), not CANCELED; "
            "ACCEPT/DECLINE/VETO credit the proposal sender via relatedTransactionId; "
            "TRADE_UPHOLD is commish grain not a second accept; "
            "2014-17 stubs are unavailable (missing, never 0); "
            "owner via data.json seasons + canon MERGE; "
            "never the warehouse transaction fact table; never teamId<=0"
        ),
        "availableYears": AVAILABLE_YEARS,
        "unavailableYears": UNAVAILABLE_YEARS,
        "years": years_out,
        "cumulative": {"available": True, "from": 2018, "to": 2025, "managers": cumulative},
    }
    def grain_ok(cum: dict) -> bool:
        m18 = cum.get("m18") or {}
        m04 = cum.get("m04") or {}
        league_prop = sum(r.get("tradesProposed", 0) for r in cum.values())
        feelers_prop = m18.get("tradesProposed", 0)
        feelers_closed = (
            m18.get("tradesAccepted", 0)
            + m18.get("tradesDeclined", 0)
            + m18.get("tradesVetoed", 0)
        )
        chew_den = (
            m04.get("tradesAccepted", 0)
            + m04.get("tradesDeclined", 0)
            + m04.get("tradesVetoed", 0)
        )
        if 7200 <= league_prop <= 8000:
            print(f"FAIL grain: league proposed {league_prop} ~7600 (PENDING+CANCELED)", file=sys.stderr)
            return False
        if feelers_prop == 3964:
            print("FAIL grain: Feelers proposed is 3964 (CANCELED counted as send)", file=sys.stderr)
            return False
        if feelers_prop != 2079:
            print(f"FAIL grain: Feelers proposed {feelers_prop} != 2079 PENDING", file=sys.stderr)
            return False
        if chew_den and m04.get("tradesAccepted", 0) == chew_den:
            print("FAIL grain: Chewbacca rate is 100%", file=sys.stderr)
            return False
        if feelers_prop == feelers_closed:
            print("FAIL grain: proposed was set to closed threads", file=sys.stderr)
            return False
        return True

    if not grain_ok(cumulative):
        return 2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"wrote {OUT} years={list(years_out)} cum_managers={len(cumulative)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
