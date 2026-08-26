#!/usr/bin/env python3
"""AFFL playoff player metrics + franchise all-time scorers.

Playoffs = year JSON weeks[*].tier == WINNERS_BRACKET only (2018+).
WINNERS_CONSOLATION_LADDER and LOSERS_CONSOLATION_LADDER do not count.
2014-2017 have trophies but every game is NONE — do not invent player
playoff weeks or rings for those years.

Writes site/yoff.json and site/franchise_leaders.json.
Re-run this script; do not hand-edit the JSON.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
YEARS = list(range(2018, 2026))
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
BENCH = {"BN", "IR"}
POS_KEYS = ("QB", "RB", "WR", "TE", "K", "DST")


def canon(oid):
    if oid is None or oid == "":
        return oid
    s = str(oid)
    return MERGE.get(s, s)


def r3(v):
    if v is None:
        return None
    return round(float(v) + 0.0, 3)


def r1(v):
    if v is None:
        return None
    return round(float(v) + 0.0, 1)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def norm_pos(pos):
    p = str(pos or "").upper().replace(" ", "")
    if p in ("D/ST", "DST", "DEF", "D"):
        return "DST"
    if p in POS_KEYS:
        return p
    return p or ""


def is_start(slot, started=None):
    sl = str(slot or "").upper()
    if sl in BENCH:
        return False
    if started:
        return True
    if sl and sl not in {"", "—", "-", "NFL"}:
        return True
    return False


def tid_owner_map(data, year):
    out = {}
    for t in ((data.get("seasons") or {}).get(str(year), {}) or {}).get("teams") or []:
        out[int(t["id"])] = canon(t.get("owner"))
    return out


def playoff_tids(yd):
    tids = set()
    for gs in (yd.get("weeks") or {}).values():
        for g in gs or []:
            if g.get("tier") != "WINNERS_BRACKET":
                continue
            for side in ("home", "away"):
                tid = (g.get(side) or {}).get("tid")
                if tid is not None:
                    tids.add(int(tid))
    return tids


def wb_games(yd):
    out = []
    for wk, gs in (yd.get("weeks") or {}).items():
        for g in gs or []:
            if g.get("tier") == "WINNERS_BRACKET":
                out.append((int(wk), g))
    out.sort(key=lambda x: x[0])
    return out


def championship_game(yd):
    champ = (yd.get("trophies") or {}).get("h2hChampionTid")
    if champ is None:
        return None, None
    champ = int(champ)
    games = [(wk, g) for wk, g in wb_games(yd)
             if int((g.get("home") or {}).get("tid") or -1) == champ
             or int((g.get("away") or {}).get("tid") or -1) == champ]
    if not games:
        return None, None
    return games[-1]


def extract():
    data = load_json(os.path.join(SITE, "data.json"))
    # pid -> accumulators
    yoff_pts = defaultdict(list)   # playoff start points
    reg_pts = defaultdict(list)
    drafts = defaultdict(lambda: {"n": 0, "po": 0})
    rings = defaultdict(list)
    names = {}
    seen = set()

    # franchise -> pos -> pid -> {name, pts, years}
    leaders = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "name": "", "pts": 0.0, "years": set()
    })))

    for year in YEARS:
        yd = load_json(os.path.join(SITE, "years", f"{year}.json"))
        reg_weeks = int(yd.get("regWeeks") or (13 if year <= 2020 else 14))
        owners = tid_owner_map(data, year)
        po_tids = playoff_tids(yd)
        champ_wk, champ_g = championship_game(yd)
        champ_tid = (yd.get("trophies") or {}).get("h2hChampionTid")
        champ_tid = int(champ_tid) if champ_tid is not None else None

        # playoff starts from WINNERS_BRACKET rosters
        yoff_this = defaultdict(list)  # pid -> pts list this year
        for wk, g in wb_games(yd):
            for side in ("home", "away"):
                for row in (g.get(side) or {}).get("roster") or []:
                    if not row:
                        continue
                    pid, slot, pts = row[0], row[1], row[2] if len(row) > 2 else None
                    if not is_start(slot, None):
                        continue
                    if pts is None:
                        continue
                    yoff_this[int(pid)].append(float(pts))

        # rings: anyone on the cup winner's championship roster
        if champ_g is not None and champ_tid is not None:
            side = "home" if int(champ_g["home"]["tid"]) == champ_tid else "away"
            for row in (champ_g.get(side) or {}).get("roster") or []:
                if not row:
                    continue
                pid = int(row[0])
                if year not in rings[pid]:
                    rings[pid].append(year)

        for p in yd.get("players") or []:
            pid = int(p["pid"])
            seen.add(pid)
            names[pid] = p.get("name") or names.get(pid) or ("#" + str(pid))
            pos = norm_pos(p.get("pos"))
            draft = p.get("draft") or {}
            tid_d = draft.get("teamId")
            if tid_d is not None:
                drafts[pid]["n"] += 1
                if int(tid_d) in po_tids:
                    drafts[pid]["po"] += 1

            for w in p.get("wk") or []:
                wk = int(w[0])
                pts = w[1]
                started = bool(w[2])
                tid = w[3]
                slot = w[4] if len(w) > 4 else ""
                if pts is None:
                    continue
                if wk <= reg_weeks and is_start(slot, started):
                    reg_pts[pid].append(float(pts))
                # franchise leaders: AFFL starts only, tid maps to owner
                if started and tid is not None and is_start(slot, started):
                    owner = owners.get(int(tid))
                    if owner and pos in POS_KEYS:
                        rec = leaders[owner][pos][pid]
                        rec["name"] = p.get("name") or rec["name"]
                        rec["pts"] += float(pts)
                        rec["years"].add(year)

        for pid, pts_list in yoff_this.items():
            seen.add(pid)
            yoff_pts[pid].extend(pts_list)

    out_yoff = {}
    for pid in sorted(seen):
        yp = yoff_pts.get(pid) or []
        rp = reg_pts.get(pid) or []
        n_yoff = len(yp)
        n_reg = len(rp)
        yoff_ppg = (sum(yp) / n_yoff) if n_yoff else None
        reg_ppg = (sum(rp) / n_reg) if n_reg else None
        stud = dud = delta = None
        if n_yoff >= 3 and n_reg >= 1 and yoff_ppg is not None and reg_ppg is not None:
            delta = yoff_ppg - reg_ppg
            stud = max(0.0, delta)
            dud = max(0.0, -delta)
        d = drafts.get(pid) or {"n": 0, "po": 0}
        ry = sorted(rings.get(pid) or [])
        out_yoff[str(pid)] = {
            "yoffstud": r3(stud),
            "yoffdud": r3(dud),
            "delta": r3(delta),
            "yoffPpg": r3(yoff_ppg),
            "regPpg": r3(reg_ppg),
            "nYoff": n_yoff,
            "nReg": n_reg,
            "draftPlayoffs": d["po"],
            "draftsN": d["n"],
            "rings": len(ry),
            "ringYears": ry,
        }

    out_leaders = {}
    owners = set(canon(f.get("owner")) for f in (data.get("franchises") or []))
    owners.update(leaders.keys())
    for owner in sorted(o for o in owners if o):
        block = {}
        for pos in POS_KEYS:
            rows = []
            for pid, rec in (leaders.get(owner) or {}).get(pos, {}).items():
                ys = sorted(rec["years"])
                rows.append({
                    "pid": pid,
                    "name": rec["name"] or names.get(pid) or ("#" + str(pid)),
                    "pts": r1(rec["pts"]),
                    "years": [ys[0], ys[-1]] if ys else [],
                })
            rows.sort(key=lambda r: (-(r["pts"] or 0), r["name"] or ""))
            block[pos] = rows[:5]
        out_leaders[owner] = block

    yoff_path = os.path.join(SITE, "yoff.json")
    lead_path = os.path.join(SITE, "franchise_leaders.json")
    with open(yoff_path, "w") as f:
        json.dump(out_yoff, f, indent=2)
        f.write("\n")
    with open(lead_path, "w") as f:
        json.dump(out_leaders, f, indent=2)
        f.write("\n")
    return out_yoff, out_leaders


def main():
    yoff, leaders = extract()
    graded = sum(1 for v in yoff.values() if v["nYoff"] >= 3 and v["yoffstud"] is not None)
    print(f"yoff.json players={len(yoff)} graded(nYoff>=3)={graded}")
    print(f"franchise_leaders.json owners={len(leaders)}")
    for pid in (4242335, 4430807, 4697815):
        rec = yoff.get(str(pid))
        print(f"  pid {pid}: {rec}")
    feel = leaders.get("m18") or {}
    for pos in ("RB", "WR", "QB"):
        print(f"  Feelers {pos}: {feel.get(pos)}")


if __name__ == "__main__":
    main()
