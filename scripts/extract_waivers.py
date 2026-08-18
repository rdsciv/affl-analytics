#!/usr/bin/env python3
"""Pull ESPN waiver / free-agent claims with status for 2018–2025.

Uses fetch.url_for / fetch.get and cookies from .env. Never prints cookies.

Writes site/waivers.json keyed year → week → list of claims:
  {id, type, tid, wk, bid, date, processDate, status, executionType,
   items: [{pid, act, from, to, name}]}

Dedup by id. Does not rewrite data/tx_*.json.
Player names come from warehouse dim_player, then site year pmeta.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(ROOT, "data")
YEARS = list(range(2018, 2026))
# 0 = preseason / offseason bucket; 18 covers 2021+ regular season.
PERIODS = list(range(0, 19))
KEEP = {"WAIVER", "FREEAGENT"}

sys.path.insert(0, ROOT)
import fetch  # noqa: E402


def load_player_names():
    names = {}
    db = os.path.join(ROOT, "affl.db")
    if os.path.exists(db):
        con = sqlite3.connect(db)
        for pid, name in con.execute(
            "SELECT player_id, name FROM dim_player WHERE name IS NOT NULL"
        ):
            if pid is None or not name:
                continue
            names[int(pid)] = name
        con.close()
    years_dir = os.path.join(SITE, "years")
    if os.path.isdir(years_dir):
        for fn in os.listdir(years_dir):
            if not fn.endswith(".json"):
                continue
            try:
                bag = json.load(open(os.path.join(years_dir, fn)))
            except Exception:
                continue
            pmeta = bag.get("pmeta") or {}
            for k, v in pmeta.items():
                try:
                    pid = int(k)
                except (TypeError, ValueError):
                    continue
                if pid in names:
                    continue
                label = v[0] if isinstance(v, (list, tuple)) and v else None
                if label:
                    names[pid] = label
    return names


def compact_tx(t, names):
    typ = t.get("type")
    if typ not in KEEP:
        return None
    items = []
    for it in t.get("items") or []:
        pid = it.get("playerId")
        rec = {
            "pid": pid,
            "act": it.get("type"),
            "from": it.get("fromTeamId"),
            "to": it.get("toTeamId"),
        }
        if pid is not None:
            try:
                nm = names.get(int(pid))
            except (TypeError, ValueError):
                nm = None
            if nm:
                rec["name"] = nm
        items.append(rec)
    return {
        "id": t.get("id"),
        "type": typ,
        "tid": t.get("teamId"),
        "wk": t.get("scoringPeriodId"),
        "bid": t.get("bidAmount") or 0,
        "date": t.get("proposedDate"),
        "processDate": t.get("processDate"),
        "status": t.get("status"),
        "executionType": t.get("executionType"),
        "items": items,
    }


def fetch_week(year, wk, names):
    d = fetch.get(fetch.url_for(year, ["mTransactions2"], f"&scoringPeriodId={wk}"))
    out = []
    for t in (d or {}).get("transactions") or []:
        rec = compact_tx(t, names)
        if rec and rec.get("id"):
            out.append(rec)
    return year, wk, out


def extract():
    names = load_player_names()
    jobs = [(y, w) for y in YEARS for w in PERIODS]
    bag = {str(y): {} for y in YEARS}
    seen = {str(y): set() for y in YEARS}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(fetch_week, y, w, names) for y, w in jobs]
        for fut in futs:
            year, _wk, rows = fut.result()
            yk = str(year)
            for rec in rows:
                tid = rec["id"]
                if tid in seen[yk]:
                    continue
                seen[yk].add(tid)
                week = rec.get("wk")
                if week is None:
                    week = 0
                wk = str(int(week))
                bag[yk].setdefault(wk, []).append(rec)
    for yk, weeks in bag.items():
        for wk, rows in weeks.items():
            rows.sort(key=lambda t: (
                t.get("processDate") or t.get("date") or 0,
                t.get("date") or 0,
                t.get("id") or "",
            ))
    dest = os.path.join(SITE, "waivers.json")
    with open(dest, "w") as f:
        json.dump(bag, f, separators=(",", ":"))
        f.write("\n")
    return bag, dest, names


def summarize(bag):
    print("year  weeks  claims  WAIVER  FA  EXECUTED  failed  canceled")
    for y in YEARS:
        weeks = bag.get(str(y)) or {}
        rows = [r for rs in weeks.values() for r in rs]
        st = Counter(r.get("status") or "" for r in rows)
        typ = Counter(r.get("type") or "" for r in rows)
        failed = sum(n for k, n in st.items() if str(k).startswith("FAILED"))
        print(
            f"{y}  {len(weeks):4d}  {len(rows):6d}  {typ.get('WAIVER', 0):6d}  "
            f"{typ.get('FREEAGENT', 0):4d}  {st.get('EXECUTED', 0):8d}  "
            f"{failed:6d}  {st.get('CANCELED', 0):8d}"
        )


def main():
    bag, dest, names = extract()
    n = sum(len(rs) for weeks in bag.values() for rs in weeks.values())
    print(f"wrote {dest} claims={n} named={len(names)}")
    summarize(bag)


if __name__ == "__main__":
    main()
