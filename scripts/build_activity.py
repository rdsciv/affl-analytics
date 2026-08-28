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
links. Each TRADE_ACCEPT is its own accepted event.

TRADE_UPHOLD is commissioner grain after a review window — NOT a second
accept. Skip it for accepted counts.

Commissioner-executed TRADE_ACCEPT (isLeagueManager=True) is attributed to
the roster-movement teams in items (the counterparty), never to the
commish's ESPN slot. If a non-commish ACCEPT exists on the same related
id, that team is the acceptor.

teamId <= 0 (including ESPN sentinel -2147483648) is dropped. Never mapped.

Owner key: ESPN teamId + year → site/data.json seasons[year].teams[].owner
then canon MERGE m01→m07, m03→m08, m20→m10. Franchise, not ESPN slot.

Counts per owner, per available year:

  waiverSubmitted  unique WAIVER rows (PENDING / EXECUTED / FAILED_* / CANCELED)
  waiverWon        WAIVER status == EXECUTED
  waiverFailed     WAIVER status startswith FAILED_
  waiverCanceled   WAIVER status == CANCELED
  faAdds           FREEAGENT status == EXECUTED with an ADD item (no fake claim split)
  tradesProposed   unique TRADE_PROPOSAL (proposer teamId)
  tradesAccepted   unique accepted deals (see pairing). TRADE_UPHOLD excluded.
  tradesDeclined   unique TRADE_DECLINE (declining team)
  tradesVetoed     unique TRADE_VETO if present; never invented

Rates (UI, not stored as painted 0 for missing years):
  waiver win  = won / submitted
  acceptance  = accept / (accept + decline + veto)

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
            if not valid_tid(tid):
                continue
            credit(tid, "waiverSubmitted")
            if status == "EXECUTED":
                credit(tid, "waiverWon")
            elif isinstance(status, str) and status.startswith("FAILED"):
                credit(tid, "waiverFailed")
            elif status == "CANCELED":
                credit(tid, "waiverCanceled")
            continue

        if typ == "FREEAGENT":
            if status != "EXECUTED":
                continue
            if not has_add(t):
                continue
            if not valid_tid(tid):
                continue
            credit(tid, "faAdds")
            continue

        if typ == "TRADE_PROPOSAL":
            if valid_tid(tid):
                credit(tid, "tradesProposed")
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

    # Pair ACCEPT to PROPOSAL on relatedTransactionId (0 overlap on tx_id).
    deals: dict[tuple, list] = defaultdict(list)
    for t in accepts:
        deals[deal_key(t)].append(t)

    credited_accepts: set[tuple[str, tuple]] = set()
    for key, group in deals.items():
        non_lm = [t for t in group if not t.get("isLeagueManager")]
        lm = [t for t in group if t.get("isLeagueManager")]
        owners = []
        if non_lm:
            for t in non_lm:
                oid = owner_of(omap, year, t.get("teamId"))
                if oid and oid not in owners:
                    owners.append(oid)
        elif lm:
            # Roster-movement grain, not the commish's team.
            sample = lm[0]
            rel = sample.get("relatedTransactionId")
            prop = proposals.get(str(rel)) if rel not in (None, "", 0, "0") else None
            teams = item_teams(sample) or (item_teams(prop) if prop else [])
            proposer = None
            if prop and valid_tid(prop.get("teamId")):
                proposer = int(prop.get("teamId"))
            for espn_tid in teams:
                if proposer is not None and int(espn_tid) == proposer:
                    continue
                oid = owner_of(omap, year, espn_tid)
                if oid and oid not in owners:
                    owners.append(oid)
        for oid in owners:
            mark = (oid, key)
            if mark in credited_accepts:
                continue
            credited_accepts.add(mark)
            row(oid)["tradesAccepted"] += 1

    seen_decline: set[tuple[str, tuple]] = set()
    for t in declines:
        oid = owner_of(omap, year, t.get("teamId"))
        if not oid:
            continue
        mark = (oid, deal_key(t))
        if mark in seen_decline:
            continue
        seen_decline.add(mark)
        row(oid)["tradesDeclined"] += 1

    seen_veto: set[tuple[str, tuple]] = set()
    for t in vetoes:
        oid = owner_of(omap, year, t.get("teamId"))
        if not oid:
            continue
        mark = (oid, deal_key(t))
        if mark in seen_veto:
            continue
        seen_veto.add(mark)
        row(oid)["tradesVetoed"] += 1

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
            "TRADE_PROPOSAL pairs to TRADE_ACCEPT on relatedTransactionId; "
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"wrote {OUT} years={list(years_out)} cum_managers={len(cumulative)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
