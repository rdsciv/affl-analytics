#!/usr/bin/env python3
"""CHI-45: TRADE_ACCEPT.rel join is consumed; one-sided 2018 rows attach."""
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_seasons import (
    build_season_trades,
    collect_accept_trades,
    resolve_accept_items,
)

fails = []
fail = lambda m: fails.append(m)

# Real 2018 week-3 ACCEPT: Fitzgerald 10→3, Bernard 3→10.
# Old builder dropped Bernard (accept_confirmed / truthy filter) and left
# Fitzgerald as a one-sided site trade.
FITZ, BERNARD = 5528, 15826
ACCEPT_2018 = {
    "id": "f426179e-cb24-347e-b234-992e20965bd7",
    "type": "TRADE_ACCEPT",
    "tid": 10,
    "wk": 3,
    "date": 1537412481984,
    "rel": None,
    "items": [
        {"pid": FITZ, "act": "TRADE", "from": 10, "to": 3},
        {"pid": BERNARD, "act": "TRADE", "from": 3, "to": 10},
    ],
}


class SpyDict(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gets = []

    def get(self, key, default=None):
        self.gets.append(key)
        return super().get(key, default)


def sides_of(trades):
    out = []
    for tr in trades:
        for s in tr.get("sides") or []:
            for g in s.get("got") or []:
                out.append((g.get("pid"), g.get("from"), s.get("tid"), tr.get("wk")))
    return out


def main():
    src = inspect.getsource(resolve_accept_items)
    if "by_id.get" not in src and "by_id[" not in src:
        fail("resolve_accept_items does not read by_id")
    ps = (ROOT / "process_seasons.py").read_text()
    if "by_id = {t['id']: t for t in tx_list" not in ps and \
       'by_id = {t["id"]: t for t in tx_list' not in ps:
        fail("collect_accept_trades no longer builds by_id")
    if "i.get('from') and i.get('to')" in ps and "accept_confirmed" in ps:
        fail("old truthy from/to + accept_confirmed filter still in process_seasons")

    # 1) Empty ACCEPT + rel → proposal. by_id must be consulted.
    prop_id = "prop-2019-sample"
    proposal = {
        "id": prop_id,
        "type": "TRADE_PROPOSAL",
        "tid": 7,
        "wk": 3,
        "items": [
            {"pid": 111, "act": "TRADE", "from": 4, "to": 7},
            {"pid": 222, "act": "TRADE", "from": 7, "to": 4},
        ],
    }
    accept = {
        "id": "acc-empty",
        "type": "TRADE_ACCEPT",
        "tid": 4,
        "wk": 3,
        "rel": prop_id,
        "items": [],
    }
    spy = SpyDict({prop_id: proposal})
    joined = resolve_accept_items(accept, spy)
    if prop_id not in spy.gets:
        fail("by_id.get was not called for ACCEPT.rel")
    pids = {i["pid"] for i in joined}
    if pids != {111, 222}:
        fail(f"empty ACCEPT did not inherit proposal items: {joined}")
    if not any(i["pid"] == 111 and i["from"] == 4 and i["to"] == 7 for i in joined):
        fail("proposal from/to not copied onto ACCEPT")

    empty_spy = SpyDict()
    if resolve_accept_items(accept, empty_spy):
        fail("empty ACCEPT with missing proposal invented items")
    if prop_id not in empty_spy.gets:
        fail("by_id.get not called when proposal is absent")

    # 2) One-sided 2018 sample: Bernard missing `to`; pair + proposal fill it.
    onesided = {
        "id": "acc-2018-onesided",
        "type": "TRADE_ACCEPT",
        "tid": 10,
        "wk": 3,
        "rel": "prop-2018-fitz",
        "items": [
            {"pid": FITZ, "act": "TRADE", "from": 10, "to": 3},
            {"pid": BERNARD, "act": "TRADE", "from": 3, "to": None},
        ],
    }
    prop_2018 = {
        "id": "prop-2018-fitz",
        "type": "TRADE_PROPOSAL",
        "items": [
            {"pid": FITZ, "act": "TRADE", "from": 10, "to": 3},
            {"pid": BERNARD, "act": "TRADE", "from": 3, "to": 10},
        ],
    }
    spy2 = SpyDict({"prop-2018-fitz": prop_2018})
    filled = resolve_accept_items(onesided, spy2)
    if "prop-2018-fitz" not in spy2.gets:
        fail("2018 one-sided sample did not consult by_id")
    bern = next((i for i in filled if i["pid"] == BERNARD), None)
    if not bern:
        fail("one-sided 2018 Bernard row was dropped")
    elif bern.get("from") != 3 or bern.get("to") != 10:
        fail(f"Bernard did not attach 3→10, got {bern}")
    fitz = next((i for i in filled if i["pid"] == FITZ), None)
    if not fitz or fitz.get("from") != 10 or fitz.get("to") != 3:
        fail(f"Fitzgerald 10→3 lost: {fitz}")

    # Pair-only fill (no proposal items needed beyond parties).
    pair_only = {
        "id": "acc-pair",
        "type": "TRADE_ACCEPT",
        "rel": None,
        "items": [
            {"pid": FITZ, "act": "TRADE", "from": 10, "to": 3},
            {"pid": BERNARD, "act": "TRADE", "from": 3},  # missing to
        ],
    }
    paired = resolve_accept_items(pair_only, {})
    bern = next((i for i in paired if i["pid"] == BERNARD), None)
    if not bern or bern.get("to") != 10:
        fail(f"paired-item fill failed for Bernard: {bern}")

    # DROP-to-FA stays dropped.
    drop = resolve_accept_items({
        "id": "acc-drop", "type": "TRADE_ACCEPT", "rel": None,
        "items": [{"pid": 99, "act": "DROP", "from": 8, "to": 0}],
    }, {})
    if drop:
        fail(f"DROP-to-FA became a trade: {drop}")

    # 3) Real 2018 ACCEPT through collect — both legs on one two-sided trade.
    trades, moves, by_id = collect_accept_trades([ACCEPT_2018])
    if ACCEPT_2018["id"] not in by_id:
        fail("collect_accept_trades by_id missing the 2018 ACCEPT id")
    legs = sides_of(trades)
    if (FITZ, 10, 3, 3) not in legs:
        fail(f"2018 Fitzgerald 10→3 not attached: {legs}")
    if (BERNARD, 3, 10, 3) not in legs:
        fail(f"2018 Bernard 3→10 not attached: {legs}")
    two_sided = [tr for tr in trades if len(tr.get("sides") or []) >= 2]
    if not two_sided:
        fail("2018 Fitzgerald/Bernard ACCEPT stayed one-sided")

    # 4) Live 2018 feed: same deal survives the real file.
    tx_path = ROOT / "data" / "tx_2018.json"
    if tx_path.exists():
        raw = json.loads(tx_path.read_text())
        tx = (raw[0] if isinstance(raw, list) else raw).get("tx") or []
        live, _, live_by = collect_accept_trades(tx)
        if not live_by:
            fail("2018 collect_accept_trades built an empty by_id")
        live_legs = sides_of(live)
        if (FITZ, 10, 3, 3) not in live_legs or (BERNARD, 3, 10, 3) not in live_legs:
            fail(f"live 2018 feed missing Fitz/Bernard attach: {live_legs[:8]}")
        hit = False
        for tr in live:
            pids = {g["pid"] for s in tr["sides"] for g in s["got"]}
            tids = {s["tid"] for s in tr["sides"]}
            if FITZ in pids and BERNARD in pids and tids == {3, 10}:
                hit = True
        if not hit:
            fail("live 2018 Fitz/Bernard not on the same two-sided trade")
    else:
        fail("data/tx_2018.json missing")

    # 5) Do not invent 2014–17 trades (no tx log).
    invented, _ = build_season_trades(
        2016,
        [],
        {},
        [{"pid": 1, "tid": 7}],
        [(1, 4, 1, "RB", 10, True)],  # would look like a mid-season hop
        [],
    )
    if invented:
        fail(f"2016 invented {len(invented)} trades from draft/roster hop")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    if not fails:
        print("by_id consumed; 2018 Fitz/Bernard two-sided; no 2014-17 invent")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
