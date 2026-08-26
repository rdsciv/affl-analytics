#!/usr/bin/env python3
"""Extract 2014–2017 ESPN snapshot rosters into site/pre2018_rosters.json.

These are last-known / final rosters + lineupSlotId, NOT weekly lineups.
ESPN compacted weekly boxes before 2018. Do not invent start weeks.
Re-run this script; do not hand-edit the JSON.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
YEARS = (2014, 2015, 2016, 2017)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def unwrap(d):
    return d[0] if isinstance(d, list) and d else d


def tid_owner_map(data, year):
    out = {}
    for t in ((data.get("seasons") or {}).get(str(year), {}) or {}).get("teams") or []:
        if t.get("id") is None:
            continue
        out[int(t["id"])] = t.get("owner")
    return out


def player_name(entry):
    ppe = entry.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    return p.get("fullName") or ""


def player_id(entry):
    ppe = entry.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    pid = p.get("id")
    if pid is None:
        pid = entry.get("playerId")
    return pid


def main():
    data = load_json(os.path.join(SITE, "data.json"))
    index = {}
    idx_path = os.path.join(SITE, "player_index.json")
    if os.path.exists(idx_path):
        index = load_json(idx_path)

    out = {}
    for year in YEARS:
        owners = tid_owner_map(data, year)
        league = unwrap(load_json(os.path.join(DATA, f"league_{year}.json")))
        year_map = {}
        for team in league.get("teams") or []:
            tid = team.get("id")
            if tid is None:
                continue
            tid = int(tid)
            owner = owners.get(tid)
            for e in ((team.get("roster") or {}).get("entries") or []):
                pid = player_id(e)
                if pid is None:
                    continue
                rec = {
                    "tid": tid,
                    "owner": owner,
                    "slot": e.get("lineupSlotId"),
                    "name": player_name(e) or ((index.get(str(pid)) or {}).get("name") or ""),
                }
                year_map[str(int(pid))] = rec

        draft_path = os.path.join(DATA, f"draft_{year}.json")
        if os.path.exists(draft_path):
            draft = load_json(draft_path)
            for p in draft.get("picks") or []:
                pid = p.get("pid")
                if pid is None:
                    continue
                key = str(int(pid))
                dtid = p.get("tid")
                rec = year_map.get(key)
                if rec is None:
                    name = ((index.get(key) or {}).get("name") or "")
                    rec = {"name": name}
                    year_map[key] = rec
                if dtid is not None:
                    rec["draftTid"] = int(dtid)

        out[str(year)] = year_map
        n_snap = sum(1 for v in year_map.values() if v.get("tid") is not None)
        n_draft = sum(1 for v in year_map.values() if v.get("draftTid") is not None)
        print(f"  {year}: {n_snap} snapshot players, {n_draft} with draftTid, {len(year_map)} keys")

    dest = os.path.join(SITE, "pre2018_rosters.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
