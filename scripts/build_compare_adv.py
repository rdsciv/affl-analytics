#!/usr/bin/env python3
"""Join 2025 advanced CSVs onto ESPN player ids. Writes site/compare_adv.json."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SRC = ROOT / "data" / "compare-2025"
OUT = SITE / "compare_adv.json"

SUFFIX = re.compile(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.I)
TEAM_ALIAS = {
    "JAC": "JAX", "JAX": "JAX",
    "WAS": "WAS", "WSH": "WAS",
    "LA": "LAR", "LAR": "LAR",
    "STL": "LAR",
}

def norm_name(s: str) -> str:
    n = (s or "").lower().replace("'", "").replace(".", "").replace("-", " ")
    n = SUFFIX.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

def norm_team(s: str) -> str:
    t = (s or "").strip().upper()
    return TEAM_ALIAS.get(t, t)

def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in ("", "-", "—", "NA", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def parse_player_blob(raw: str):
    """'Jahmyr Gibbs   DET' or 'Drake Maye   QB - NE' or 'Patrick Mahomes II   KC'."""
    s = (raw or "").strip()
    if not s:
        return None, None, None
    m = re.match(r"^(.+?)\s{2,}([A-Z]{1,3})\s*-\s*([A-Z]{2,3})$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip().upper(), norm_team(m.group(3))
    m = re.match(r"^(.+?)\s{2,}([A-Z]{2,3})$", s)
    if m:
        return m.group(1).strip(), None, norm_team(m.group(2))
    parts = s.rsplit(" ", 1)
    if len(parts) == 2 and re.fullmatch(r"[A-Z]{2,3}", parts[1]):
        return parts[0].strip(), None, norm_team(parts[1])
    return s, None, None

def last_nfl_team(nfl, pid, year="2025"):
    rec = (nfl.get(str(pid)) or {}).get(year) or {}
    if not isinstance(rec, dict):
        return ""
    wks = [k for k in rec if str(k).isdigit() and int(k) > 0]
    wks.sort(key=lambda x: int(x))
    for k in reversed(wks):
        row = rec[k]
        if isinstance(row, dict) and row.get("team"):
            return norm_team(row["team"])
    return ""

def build_lookup(index, nfl):
    by_name = {}
    by_name_pos = {}
    by_name_team = {}
    for pid, meta in index.items():
        name = norm_name(meta.get("name") or "")
        if not name:
            continue
        pos = str(meta.get("pos") or "").upper()
        team = last_nfl_team(nfl, pid)
        by_name.setdefault(name, []).append(str(pid))
        if pos:
            by_name_pos.setdefault((name, pos), []).append(str(pid))
        if team:
            by_name_team.setdefault((name, team), []).append(str(pid))
    return by_name, by_name_pos, by_name_team

def pick_pid(name, pos, team, by_name, by_name_pos, by_name_team):
    n = norm_name(name)
    pos = (pos or "").upper()
    team = norm_team(team) if team else ""
    if n and team and (n, team) in by_name_team:
        hits = by_name_team[(n, team)]
        if len(hits) == 1:
            return hits[0]
        if pos:
            pos_hits = [p for p in hits if p in set(by_name_pos.get((n, pos), []))]
            if len(pos_hits) == 1:
                return pos_hits[0]
    if n and pos and (n, pos) in by_name_pos:
        hits = by_name_pos[(n, pos)]
        if len(hits) == 1:
            return hits[0]
    hits = by_name.get(n) or []
    if len(hits) == 1:
        return hits[0]
    return None

def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def ensure(players, pid):
    rec = players.setdefault(str(pid), {"pid": int(pid)})
    return rec

def main():
    index = json.loads((SITE / "player_index.json").read_text())
    nfl = json.loads((SITE / "nfl_weeks.json").read_text())
    by_name, by_name_pos, by_name_team = build_lookup(index, nfl)
    players = {}
    unmatched = []

    def join(name, pos, team, source):
        pid = pick_pid(name, pos, team, by_name, by_name_pos, by_name_team)
        if not pid:
            unmatched.append({"source": source, "name": name, "pos": pos, "team": team})
            return None
        rec = ensure(players, pid)
        rec.setdefault("name", index[pid]["name"])
        rec.setdefault("pos", index[pid].get("pos") or pos or "")
        if team:
            rec.setdefault("nfl", team)
        return rec

    # snaps
    for row in read_csv(SRC / "snap-util.csv"):
        rec = join(row.get("PLAYER"), row.get("POS"), row.get("TEAM"), "snap")
        if not rec:
            continue
        rec["games"] = num(row.get("GAMES"))
        rec["snaps"] = num(row.get("SNAPS"))
        rec["snaps_gm"] = num(row.get("SNAPS/GM"))
        rec["snap_pct"] = num(row.get("SNAP %"))
        rec["rush_pct"] = num(row.get("RUSH %"))
        rec["tgt_pct"] = num(row.get("TGT %"))
        rec["touch_pct"] = num(row.get("TOUCH %"))
        rec["util_pct"] = num(row.get("UTIL %"))
        rec["pts_per_100"] = num(row.get("PTS/100 SNAPS"))

    # rb
    for row in read_csv(SRC / "rb-rushing.csv"):
        name, pos, team = parse_player_blob(row.get("Player") or "")
        rec = join(name, pos or "RB", team, "rb")
        if not rec:
            continue
        rec["games"] = rec.get("games") or num(row.get("G"))
        rec["rush_att"] = num(row.get("RUSHING ATT"))
        rec["rush_yds"] = num(row.get("RUSHING YDS"))
        rec["ypc"] = num(row.get("RUSHING Y/ATT"))
        rec["rush_yacon"] = num(row.get("RUSHING YACON"))
        rec["rush_yacon_att"] = num(row.get("RUSHING YACON/ATT"))
        rec["rush_brktkl"] = num(row.get("RUSHING BRKTKL"))
        rec["rush_10"] = num(row.get("BIG RUSH PLAYS 10+ YDS"))
        rec["rec"] = num(row.get("RECEIVING REC"))
        rec["tgt"] = num(row.get("RECEIVING TGT"))
        rec["rz_tgt"] = num(row.get("RECEIVING RZ TGT"))
        rec["rec_yacon"] = num(row.get("RECEIVING YACON"))

    # wr + te receiving
    for fname, default_pos in (("wr-receiving.csv", "WR"), ("te-receiving.csv", "TE")):
        for row in read_csv(SRC / fname):
            name, pos, team = parse_player_blob(row.get("Player") or "")
            rec = join(name, pos or default_pos, team, default_pos.lower())
            if not rec:
                continue
            rec["games"] = rec.get("games") or num(row.get("G"))
            rec["rec"] = num(row.get("RECEIVING REC"))
            rec["rec_yds"] = num(row.get("RECEIVING YDS"))
            rec["ypr"] = num(row.get("RECEIVING Y/R"))
            rec["ybc"] = num(row.get("RECEIVING YBC"))
            rec["air"] = num(row.get("RECEIVING AIR"))
            rec["yac"] = num(row.get("RECEIVING YAC"))
            rec["yac_r"] = num(row.get("RECEIVING YAC/R"))
            rec["rec_yacon"] = num(row.get("RECEIVING YACON"))
            rec["rec_brktkl"] = num(row.get("RECEIVING BRKTKL"))
            rec["tgt"] = num(row.get("TARGETS TGT"))
            rec["tgt_tm"] = num(row.get("TARGETS % TM"))
            rec["catchable"] = num(row.get("TARGETS CATCHABLE"))
            rec["drops"] = num(row.get("TARGETS DROP"))
            rec["rz_tgt"] = num(row.get("TARGETS RZ TGT"))
            rec["rec_10"] = num(row.get("BIG PLAYS 10+ YDS"))
            rec["rec_20"] = num(row.get("BIG PLAYS 20+ YDS"))

    # qb
    for row in read_csv(SRC / "qb-passing.csv"):
        name, pos, team = parse_player_blob(row.get("Player") or "")
        rec = join(name, pos or "QB", team, "qb")
        if not rec:
            continue
        rec["games"] = rec.get("games") or num(row.get("G"))
        rec["pass_cmp"] = num(row.get("PASSING COMP"))
        rec["pass_att"] = num(row.get("PASSING ATT"))
        rec["pass_pct"] = num(row.get("PASSING PCT"))
        rec["pass_yds"] = num(row.get("PASSING YDS"))
        rec["ypa"] = num(row.get("PASSING Y/A"))
        rec["pass_air"] = num(row.get("PASSING AIR"))
        rec["pkt_time"] = num(row.get("PRESSURE PKT TIME"))
        rec["sacks"] = num(row.get("PRESSURE SACK"))
        rec["rz_att"] = num(row.get("MISC RZ ATT"))
        rec["pass_rtg"] = num(row.get("MISC RTG"))
        rec["poor_throws"] = num(row.get("MISC POOR"))
        rec["qb_drops"] = num(row.get("MISC DROP"))

    # quality games
    for row in read_csv(SRC / "quality-games.csv"):
        name, pos, team = parse_player_blob(row.get("Player") or "")
        rec = join(name, pos, team, "quality")
        if not rec:
            continue
        rec["ecr"] = num(row.get("ECR"))
        rec["poor_n"] = num(row.get("POOR #"))
        rec["poor_pct"] = num(row.get("POOR %"))
        rec["quality_n"] = num(row.get("QUALITY #"))
        rec["quality_pct"] = num(row.get("QUALITY %"))
        rec["great_n"] = num(row.get("GREAT #"))
        rec["great_pct"] = num(row.get("GREAT %"))
        rec["qg_n"] = num(row.get("QUALITY + GREAT #"))
        rec["qg_pct"] = num(row.get("QUALITY + GREAT %"))

    payload = {
        "season": 2025,
        "source": "2025 advanced CSVs in data/compare-2025 (snaps, rush, rec, pass, quality games)",
        "scoring": "AFFL scoring for fantasy points; advanced box from the CSVs",
        "players": players,
        "unmatched_n": len(unmatched),
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print("players", len(players), "unmatched", len(unmatched))
    for pid in ("4429795", "4430807", "16800", "3139477"):
        rec = players.get(pid)
        print(pid, rec.get("name") if rec else None, {k: rec.get(k) for k in ("rush_att", "ypc", "tgt", "snap_pct", "qg_pct", "yac", "pass_yds")} if rec else None)
    if unmatched[:12]:
        print("unmatched sample:")
        for u in unmatched[:12]:
            print(" ", u)

if __name__ == "__main__":
    main()
