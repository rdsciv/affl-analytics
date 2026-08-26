#!/usr/bin/env python3
"""Build site/pre2018_season_rosters.json for 2014–2017.

Season-long AFFL roster = union of:
  1. draft picks that year (draft_YYYY.json, fact_draft_pick, year JSON board)
  2. weekly starts in site/pre2018_starts.json
  3. final snapshot in site/pre2018_rosters.json / league_YYYY.json roster

NFL points are nflverse standard fantasy_points joined via dim_player.gsis_id.
No gsis → nflPts is null (never invented). Weekly benches are not in ESPN's API.
Re-run this script; do not hand-edit the JSON.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
DB = os.path.join(ROOT, "affl.db")
YEARS = (2014, 2015, 2016, 2017)
BENCH_SLOTS = {20, 21}
SLOT = {
    0: "QB",
    2: "RB",
    3: "RB/WR",
    4: "WR",
    5: "WR/TE",
    6: "TE",
    7: "OP",
    16: "D/ST",
    17: "K",
    20: "BN",
    21: "IR",
    23: "FLEX",
}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def unwrap(d):
    return d[0] if isinstance(d, list) and d else d


def player_id(entry):
    ppe = entry.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    pid = p.get("id")
    if pid is None:
        pid = entry.get("playerId")
    return pid


def player_name(entry):
    ppe = entry.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    return p.get("fullName") or ""


def player_pos(entry):
    ppe = entry.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    return p.get("defaultPosition") or p.get("eligibleSlots") or None


def norm_pos(pos, slot=None):
    if pos:
        p = str(pos).upper().replace("D/ST", "DST").replace("DEF", "DST")
        if p in ("DST", "D/ST"):
            return "DST"
        if p in ("QB", "RB", "WR", "TE", "K", "FLEX", "OP"):
            return p
        if "/" not in p:
            return p
    if slot in SLOT:
        s = SLOT[slot]
        return "DST" if s == "D/ST" else s
    return ""


def load_dim_players():
    out = {}
    if not os.path.exists(DB):
        return out
    con = sqlite3.connect(DB)
    try:
        for pid, name, pos, gsis in con.execute(
            "SELECT player_id, name, position, gsis_id FROM dim_player"
        ):
            if pid is None:
                continue
            out[int(pid)] = {
                "name": name or "",
                "pos": pos or "",
                "gsis": gsis or None,
            }
    finally:
        con.close()
    return out


def load_draft_pids(year):
    """pid -> {tid, overall, name, pos} from draft file / warehouse / year board."""
    out = {}
    path = os.path.join(DATA, f"draft_{year}.json")
    if os.path.exists(path):
        draft = load_json(path)
        for p in draft.get("picks") or []:
            pid = p.get("pid")
            tid = p.get("tid")
            if pid is None or tid is None:
                continue
            out[int(pid)] = {
                "tid": int(tid),
                "overall": p.get("overall"),
                "name": p.get("name") or "",
                "pos": p.get("pos") or "",
            }
    if os.path.exists(DB):
        con = sqlite3.connect(DB)
        try:
            for pid, tid, overall in con.execute(
                "SELECT player_id, team_id, overall FROM fact_draft_pick WHERE season=?",
                (year,),
            ):
                if pid is None or tid is None:
                    continue
                rec = out.setdefault(int(pid), {"tid": int(tid), "overall": overall, "name": "", "pos": ""})
                rec["tid"] = int(tid)
                if overall is not None:
                    rec["overall"] = overall
        finally:
            con.close()
    ypath = os.path.join(SITE, "years", f"{year}.json")
    if os.path.exists(ypath):
        yd = load_json(ypath)
        for p in ((yd.get("draft") or {}).get("board") or []):
            pid = p.get("pid")
            tid = p.get("tid")
            if pid is None or tid is None:
                continue
            rec = out.setdefault(int(pid), {"tid": int(tid), "overall": p.get("overall"), "name": "", "pos": ""})
            rec["tid"] = int(tid)
            if p.get("overall") is not None:
                rec["overall"] = p.get("overall")
            if p.get("name"):
                rec["name"] = p["name"]
            if p.get("pos"):
                rec["pos"] = p["pos"]
    return out


def load_league_snapshot(year):
    """pid -> {tid, slot, name} from league JSON roster (same snapshot as pre2018_rosters)."""
    path = os.path.join(DATA, f"league_{year}.json")
    if not os.path.exists(path):
        return {}
    league = unwrap(load_json(path))
    out = {}
    for team in league.get("teams") or []:
        tid = team.get("id")
        if tid is None:
            continue
        tid = int(tid)
        for e in ((team.get("roster") or {}).get("entries") or []):
            pid = player_id(e)
            if pid is None:
                continue
            out[int(pid)] = {
                "tid": tid,
                "slot": e.get("lineupSlotId"),
                "name": player_name(e) or "",
            }
    return out


def load_pmeta(year):
    path = os.path.join(SITE, "years", f"{year}.json")
    if not os.path.exists(path):
        return {}
    return (load_json(path).get("pmeta") or {})


def load_nfl_points(year, gsis_by_pid):
    """gsis_id -> {pts, games} for REG season. Standard fantasy_points only."""
    path = os.path.join(DATA, f"stats_player_week_{year}.csv")
    if not os.path.exists(path):
        return {}
    wanted = {g for g in gsis_by_pid.values() if g}
    bag = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            if rec.get("season_type") != "REG":
                continue
            gid = rec.get("player_id") or ""
            if gid not in wanted:
                continue
            raw = rec.get("fantasy_points")
            try:
                pts = float(raw) if raw not in (None, "") else 0.0
            except (TypeError, ValueError):
                pts = 0.0
            slot = bag.setdefault(gid, {"pts": 0.0, "games": 0})
            slot["pts"] += pts
            slot["games"] += 1
    return bag


def load_proj(year):
    path = os.path.join(SITE, "proj.json")
    if not os.path.exists(path):
        return {}
    all_proj = load_json(path)
    return all_proj.get(str(year)) or {}


def resolve_name(pid, *sources):
    for src in sources:
        if not src:
            continue
        if isinstance(src, str) and src.strip():
            return src.strip()
    return f"pid {pid}"


def resolve_pos(pid, slot, *sources):
    for src in sources:
        p = norm_pos(src, slot)
        if p and p not in ("BN", "IR", "FLEX", "OP", "RB/WR", "WR/TE"):
            return p
    return norm_pos(None, slot) or ""


def sort_key(row):
    slot = row.get("slot")
    snap = row.get("snapshot")
    drafted = row.get("drafted")
    name = row.get("name") or ""
    if snap and slot not in BENCH_SLOTS and slot is not None:
        return (0, int(slot), name)
    if snap:
        return (1, 99 if slot is None else int(slot), name)
    if drafted:
        overall = row.get("draftOverall")
        return (2, 999 if overall is None else int(overall), name)
    return (3, -(row.get("starts") or 0), name)


def source_labels(drafted, starts, snapshot):
    labels = []
    if drafted:
        labels.append("drafted")
    if starts:
        labels.append("started")
    if snapshot:
        labels.append("finished")
    return labels


def main():
    index = {}
    idx_path = os.path.join(SITE, "player_index.json")
    if os.path.exists(idx_path):
        index = load_json(idx_path)
    dim = load_dim_players()
    rosters = load_json(os.path.join(SITE, "pre2018_rosters.json"))
    starts_all = load_json(os.path.join(SITE, "pre2018_starts.json"))

    out = {}
    for year in YEARS:
        draft = load_draft_pids(year)
        snap_file = rosters.get(str(year)) or {}
        snap_league = load_league_snapshot(year)
        pmeta = load_pmeta(year)
        starts_year = starts_all.get(str(year)) or {}
        proj_year = load_proj(year)

        # tids that appear in any source
        tids = set()
        for rec in draft.values():
            tids.add(rec["tid"])
        for rec in snap_file.values():
            if rec.get("tid") is not None:
                tids.add(int(rec["tid"]))
        for rec in snap_league.values():
            tids.add(rec["tid"])
        for rec in starts_year.values():
            if not isinstance(rec, dict):
                continue
            for wk, row in rec.items():
                if isinstance(row, dict) and row.get("tid") is not None:
                    tids.add(int(row["tid"]))

        # collect pids per tid
        by_tid = {tid: {} for tid in tids}

        def bag(tid, pid):
            return by_tid[tid].setdefault(int(pid), {
                "pid": int(pid),
                "drafted": False,
                "snapshot": False,
                "starts": 0,
                "slot": None,
                "draftOverall": None,
                "name": "",
                "pos": "",
            })

        for pid, rec in draft.items():
            row = bag(rec["tid"], pid)
            row["drafted"] = True
            if rec.get("overall") is not None:
                row["draftOverall"] = rec["overall"]
            if rec.get("name"):
                row["name"] = rec["name"]
            if rec.get("pos"):
                row["pos"] = rec["pos"]

        for pid_s, rec in snap_file.items():
            if rec.get("tid") is None:
                continue
            pid = int(pid_s)
            row = bag(int(rec["tid"]), pid)
            row["snapshot"] = True
            if rec.get("slot") is not None:
                row["slot"] = rec["slot"]
            if rec.get("name"):
                row["name"] = rec["name"]
        for pid, rec in snap_league.items():
            row = bag(rec["tid"], pid)
            row["snapshot"] = True
            if rec.get("slot") is not None and row["slot"] is None:
                row["slot"] = rec["slot"]
            if rec.get("name") and not row["name"]:
                row["name"] = rec["name"]

        for pid_s, rec in starts_year.items():
            if not isinstance(rec, dict):
                continue
            pid = int(pid_s)
            counts = {}
            for wk, row in rec.items():
                if not isinstance(row, dict) or row.get("tid") is None:
                    continue
                tid = int(row["tid"])
                counts[tid] = counts.get(tid, 0) + 1
            for tid, n in counts.items():
                if tid not in by_tid:
                    by_tid[tid] = {}
                row = bag(tid, pid)
                row["starts"] = n

        # NFL points via gsis
        gsis_map = {}
        all_pids = set()
        for tid_map in by_tid.values():
            all_pids.update(tid_map.keys())
        for pid in all_pids:
            g = (dim.get(pid) or {}).get("gsis")
            if g:
                gsis_map[pid] = g
        nfl = load_nfl_points(year, gsis_map)

        year_out = {}
        for tid in sorted(by_tid):
            rows = []
            for pid, rec in by_tid[tid].items():
                idx = index.get(str(pid)) or {}
                dim_rec = dim.get(pid) or {}
                meta = pmeta.get(str(pid))
                meta_name = meta[0] if isinstance(meta, list) and meta else ""
                meta_pos = meta[1] if isinstance(meta, list) and len(meta) > 1 else ""
                name = resolve_name(
                    pid,
                    rec.get("name"),
                    idx.get("name"),
                    dim_rec.get("name"),
                    meta_name,
                )
                pos = resolve_pos(
                    pid,
                    rec.get("slot"),
                    rec.get("pos"),
                    idx.get("pos"),
                    dim_rec.get("pos"),
                    meta_pos,
                )
                gsis = dim_rec.get("gsis")
                nfl_rec = nfl.get(gsis) if gsis else None
                if nfl_rec:
                    nfl_pts = round(float(nfl_rec["pts"]), 1)
                    nfl_g = int(nfl_rec["games"])
                else:
                    nfl_pts = None
                    nfl_g = None
                proj_map = proj_year.get(str(pid)) or proj_year.get(pid)
                if isinstance(proj_map, dict) and proj_map:
                    proj_pts = round(sum(float(v) for v in proj_map.values() if isinstance(v, (int, float))), 1)
                else:
                    proj_pts = None
                slot = rec.get("slot")
                item = {
                    "pid": pid,
                    "name": name,
                    "pos": pos,
                    "drafted": bool(rec.get("drafted")),
                    "snapshot": bool(rec.get("snapshot")),
                    "starts": int(rec.get("starts") or 0),
                    "nflPts": nfl_pts,
                    "projPts": proj_pts,
                    "nflG": nfl_g,
                    "slot": slot,
                    "slotName": SLOT.get(slot, "—") if slot is not None else "—",
                    "source": source_labels(rec.get("drafted"), rec.get("starts"), rec.get("snapshot")),
                }
                if rec.get("draftOverall") is not None:
                    item["draftOverall"] = rec["draftOverall"]
                rows.append(item)
            rows.sort(key=sort_key)
            # drop helper-only fields from published rows? keep slot/source — UI needs them
            year_out[str(tid)] = rows
        out[str(year)] = year_out

        n = sum(len(v) for v in year_out.values())
        print(f"  {year}: {len(year_out)} teams, {n} season-roster rows")

    dest = os.path.join(SITE, "pre2018_season_rosters.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"wrote {dest}")

    # Feelers 2014 sanity
    feel = out.get("2014", {}).get("7") or []
    print(f"Feelers 2014 (tid 7) n={len(feel)}")
    want = {11278, 13934, 14881, 5536, 13983}
    for row in feel:
        if row["pid"] in want or (row["drafted"] and not row["snapshot"]):
            print(
                f"  {row['name']:22} pid={row['pid']} slot={row['slotName']:4} "
                f"starts={row['starts']:2} nflPts={row['nflPts']} "
                f"drafted={row['drafted']} snap={row['snapshot']} src={row['source']}"
            )


if __name__ == "__main__":
    main()
