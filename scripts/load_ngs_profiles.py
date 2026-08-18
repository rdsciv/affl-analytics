#!/usr/bin/env python3
"""Build site/ngs_profiles.json from the public NGS CSV feed.

Read-only against affl.db. Never UPDATE/INSERT/DELETE warehouse facts.
Caches CSVs under data/ngs-profiles/. GitHub raw is primary; Vercel fallback.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "affl.db")
CACHE = os.path.join(ROOT, "data", "ngs-profiles")
SITE = os.path.join(ROOT, "site")
OUT_JSON = os.path.join(SITE, "ngs_profiles.json")

GH_CSV = "https://raw.githubusercontent.com/rdsciv/affl-ngs-profiles/main/csv/{name}.csv"
GH_META = "https://raw.githubusercontent.com/rdsciv/affl-ngs-profiles/main/meta.json"
VERCEL_CSV = "https://affl-ngs-profiles.vercel.app/csv/{name}.csv"
VERCEL_ROOT = "https://affl-ngs-profiles.vercel.app/{name}.csv"
VERCEL_META = "https://affl-ngs-profiles.vercel.app/meta.json"

TABLES = (
    "dim_ngs_player",
    "fact_ngs_passing",
    "fact_ngs_rushing",
    "fact_ngs_receiving",
    "fact_ngs_defense",
    "fact_ngs_weekly_passing",
    "fact_ngs_weekly_rushing",
    "fact_ngs_weekly_receiving",
    "fact_ngs_post_passing",
    "fact_ngs_post_rushing",
    "fact_ngs_post_receiving",
    "fact_ngs_routes",
    "fact_ngs_holes",
    "dim_ngs_team",
    "player_profile_ngs",
)

MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}
ROUTE_POS = {"WR", "TE", "RB"}
HOLE_POS = {"RB"}
SEASON = 2025
UA = "AFFL-ngs-profiles-loader/1.0 (+local warehouse ingest)"


def canon(mid):
    if mid is None:
        return None
    s = str(mid)
    return MERGE.get(s, s)


def fetch_url(url, dest, retries=3):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last = None
    for i in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not data:
                raise RuntimeError("empty body")
            with open(dest, "wb") as f:
                f.write(data)
            return dest, url
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def download(name):
    dest = os.path.join(CACHE, name + ".csv")
    if os.path.exists(dest) and os.path.getsize(dest) > 80:
        return dest, "cache"
    urls = [GH_CSV.format(name=name), VERCEL_CSV.format(name=name), VERCEL_ROOT.format(name=name)]
    errors = []
    for url in urls:
        try:
            path, used = fetch_url(url, dest)
            return path, used
        except Exception as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError(f"failed to fetch {name}.csv\n  " + "\n  ".join(errors))


def download_meta():
    dest = os.path.join(CACHE, "meta.json")
    if os.path.exists(dest) and os.path.getsize(dest) > 20:
        try:
            return json.load(open(dest))
        except Exception:
            pass
    for url in (GH_META, VERCEL_META):
        try:
            fetch_url(url, dest)
            return json.load(open(dest))
        except Exception:
            continue
    return {}


def read_csv(name):
    path = os.path.join(CACHE, name + ".csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    if v is None or v == "":
        return None
    s = str(v).strip()
    if s == "" or s.upper() in ("NA", "NAN", "NULL", "NONE"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_json_list(raw):
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def open_ro():
    uri = "file:" + DB + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def primary_roster(con):
    rows = con.execute("""
        SELECT r.player_id, r.team_id, t.member_id, t.name AS team_name,
               p.name, p.position, p.gsis_id, COUNT(*) AS wks
          FROM fact_roster_week r
          JOIN dim_player p ON p.player_id = r.player_id
          JOIN dim_team t ON t.season = r.season AND t.team_id = r.team_id
         WHERE r.season = ?
         GROUP BY r.player_id, r.team_id
         ORDER BY r.player_id, wks DESC, r.team_id
    """, (SEASON,)).fetchall()
    best = {}
    for rec in rows:
        pid = rec["player_id"]
        if pid not in best:
            best[pid] = rec
    return list(best.values())


def build(con, meta):
    profiles = read_csv("player_profile_ngs")
    routes = read_csv("fact_ngs_routes")
    holes = read_csv("fact_ngs_holes")
    dim_players = con.execute("""
        SELECT player_id, name, position, gsis_id
          FROM dim_player
         WHERE gsis_id IS NOT NULL AND gsis_id <> ''
    """).fetchall()
    by_gsis_espn = {}
    for r in dim_players:
        by_gsis_espn[str(r["gsis_id"])] = r

    players = {}
    for rec in profiles:
        gid = str(rec.get("gsis_id") or "")
        espn = by_gsis_espn.get(gid)
        if not espn:
            continue
        pid = espn["player_id"]
        players[str(pid)] = {
            "pid": pid,
            "name": espn["name"],
            "pos": espn["position"],
            "gsis_id": gid,
            "nfl_team": rec.get("nfl_team") or "",
            "pass_2025_cpoe": num(rec.get("pass_2025_cpoe")),
            "pass_2025_ttt": num(rec.get("pass_2025_ttt")),
            "pass_2025_agr": num(rec.get("pass_2025_agr")),
            "rush_2025_ryoe_att": num(rec.get("rush_2025_ryoe_att")),
            "rec_2025_sep": num(rec.get("rec_2025_sep")),
            "rec_2025_yacoe": num(rec.get("rec_2025_yacoe")),
            "top_routes_json": rec.get("top_routes_json") or "[]",
            "top_holes_json": rec.get("top_holes_json") or "[]",
        }

    roster = primary_roster(con)
    teams = {}
    gsis_owner_pos = {}
    for r in roster:
        oid = canon(r["member_id"])
        if not oid:
            continue
        t = teams.setdefault(oid, {
            "owner": oid, "tid": r["team_id"], "name": r["team_name"],
            "nReceivers": 0, "nRushers": 0, "routeYards": 0, "holeYards": 0,
            "routes": {}, "holes": {},
        })
        t["name"] = r["team_name"]
        t["tid"] = r["team_id"]
        pos = (r["position"] or "").upper()
        if pos in ROUTE_POS:
            t["nReceivers"] += 1
        if pos in HOLE_POS:
            t["nRushers"] += 1
        if r["gsis_id"]:
            gsis_owner_pos[str(r["gsis_id"])] = (oid, pos)

    for rec in routes:
        if str(rec.get("season") or "") not in ("2025", "2025.0"):
            continue
        gid = str(rec.get("gsis_id") or "")
        info = gsis_owner_pos.get(gid)
        if not info:
            continue
        oid, pos = info
        if pos not in ROUTE_POS or oid not in teams:
            continue
        route = rec.get("route") or ""
        yds = num(rec.get("yards")) or 0
        tgt = num(rec.get("targets")) or 0
        td = num(rec.get("td")) or 0
        bag = teams[oid]["routes"].setdefault(route, {"route": route, "yds": 0, "tgt": 0, "td": 0})
        bag["yds"] += yds
        bag["tgt"] += tgt
        bag["td"] += td
        teams[oid]["routeYards"] += yds

    for rec in holes:
        if str(rec.get("season") or "") not in ("2025", "2025.0"):
            continue
        gid = str(rec.get("gsis_id") or "")
        info = gsis_owner_pos.get(gid)
        if not info:
            continue
        oid, pos = info
        if pos not in HOLE_POS or oid not in teams:
            continue
        hole = rec.get("hole") or ""
        yds = num(rec.get("yards")) or 0
        att = num(rec.get("attempts") if rec.get("attempts") not in (None, "") else rec.get("att")) or 0
        td = num(rec.get("td")) or 0
        bag = teams[oid]["holes"].setdefault(hole, {"hole": hole, "yds": 0, "att": 0, "td": 0})
        bag["yds"] += yds
        bag["att"] += att
        bag["td"] += td
        teams[oid]["holeYards"] += yds

    franchises = []
    for oid, t in teams.items():
        route_list = sorted(t["routes"].values(), key=lambda x: (-x["yds"], x["route"]))
        hole_list = sorted(t["holes"].values(), key=lambda x: (-x["yds"], x["hole"]))
        tot_r = t["routeYards"] or 0
        tot_h = t["holeYards"] or 0
        for bag in route_list:
            bag["yds"] = round(bag["yds"], 1)
            bag["tgt"] = int(bag["tgt"])
            bag["td"] = int(bag["td"])
            bag["share"] = round(bag["yds"] / tot_r, 4) if tot_r else 0
        for bag in hole_list:
            bag["yds"] = round(bag["yds"], 1)
            bag["att"] = int(bag["att"])
            bag["td"] = int(bag["td"])
            bag["share"] = round(bag["yds"] / tot_h, 4) if tot_h else 0
        franchises.append({
            "owner": oid,
            "tid": t["tid"],
            "name": t["name"],
            "nReceivers": t["nReceivers"],
            "nRushers": t["nRushers"],
            "routeYards": round(tot_r, 1),
            "holeYards": round(tot_h, 1),
            "topRoute": route_list[0] if route_list else None,
            "topHole": hole_list[0] if hole_list else None,
            "routes": route_list,
            "holes": hole_list,
        })
    franchises.sort(key=lambda x: (-x["routeYards"], x["name"]))
    return {
        "season": SEASON,
        "updated": (meta or {}).get("updated") or "2026-08",
        "source": "NFL Next Gen Stats via nflverse · affl-ngs-profiles",
        "join_key": "gsis_id",
        "csv_counts": {n: len(read_csv(n)) for n in TABLES},
        "franchises": franchises,
        "players": players,
    }, profiles, dim_players


def report(payload, profiles, dim_players, before_draft):
    print("=== NGS profiles export (read-only affl.db) ===")
    print(f"source updated: {payload.get('updated')}")
    for name, n in payload["csv_counts"].items():
        print(f"  {name:28s} {n:6d}  (csv)")
    espn_g = len(dim_players)
    matched = len(payload["players"])
    pct = (100.0 * matched / espn_g) if espn_g else 0
    print(f"dim_player with gsis_id: {espn_g}")
    print(f"match: {matched} / {espn_g} ESPN-with-gsis hit player_profile_ngs  ({pct:.1f}%)")
    print("5 example profiles (name, pos, cpoe, ryoe/att, yacoe):")
    shown = 0
    for rec in profiles:
        if shown >= 5:
            break
        if not (rec.get("pass_2025_cpoe") or rec.get("rush_2025_ryoe_att") or rec.get("rec_2025_yacoe")):
            continue
        print(f"  {rec.get('name','')[:22]:22s} {str(rec.get('position') or ''):3s}  "
              f"cpoe={rec.get('pass_2025_cpoe')}  ryoe/att={rec.get('rush_2025_ryoe_att')}  "
              f"yacoe={rec.get('rec_2025_yacoe')}")
        shown += 1
    print(f"fact_draft_pick (read-only): {before_draft}  unchanged")
    feel = next((f for f in payload["franchises"] if f["owner"] == "m18"), None)
    if feel:
        tr = feel.get("topRoute") or {}
        th = feel.get("topHole") or {}
        print(f"Feelers 2025: {feel['name']} tid={feel['tid']}")
        print(f"  top route: {tr.get('route')} {tr.get('yds')} yds ({(tr.get('share') or 0)*100:.1f}%)")
        print(f"  top hole:  {th.get('hole')} {th.get('yds')} yds ({(th.get('share') or 0)*100:.1f}%)")
        print(f"  routeYards={feel['routeYards']}  holeYards={feel['holeYards']}")
    print(f"exported {len(payload['franchises'])} franchises · {len(payload['players'])} player profiles → site/ngs_profiles.json")
    return pct


def main():
    os.makedirs(CACHE, exist_ok=True)
    meta = download_meta()
    for name in TABLES:
        path, src = download(name)
        print(f"fetched {name}.csv via {src}")
    con = open_ro()
    before_draft = con.execute("SELECT COUNT(*) FROM fact_draft_pick").fetchone()[0]
    payload, profiles, dim_players = build(con, meta)
    after_draft = con.execute("SELECT COUNT(*) FROM fact_draft_pick").fetchone()[0]
    con.close()
    if before_draft != after_draft:
        raise RuntimeError("fact_draft_pick changed — aborting write")
    os.makedirs(SITE, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    report(payload, profiles, dim_players, before_draft)
    return 0


if __name__ == "__main__":
    sys.exit(main())
