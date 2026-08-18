#!/usr/bin/env python3
"""Build site/nfl_weeks.json + site/ngs.json for AFFL players.

If a player ever appeared on an AFFL roster (player_index.json or any
year JSON players[]), they get their full nflverse REG game log — not
just the weeks they were AFFL-rostered.

AFFL scoring is ESPN standard. We store nflverse `fantasy_points`
(verified: Jalen Nailor 2025 sums to 71.7, matching warehouse AFFL FP).

NGS is downloaded from nflverse nextgen_stats (2016–2025). Week 0 is
the season total — stored, not a game. Missing NGS (below attempt
minimums) is omitted so the UI can render an em dash, never a fake 0.

Official NGS chart CDN filenames include a timestamp and the NGS player
code (e.g. MAH401939). nflverse files only have player_gsis_id, so
stable official chart image/page URLs cannot be constructed without
scraping. This script does not emit chart links.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sqlite3
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
DB = os.path.join(ROOT, "affl.db")
NGS_DIR = os.path.join(DATA, "ngs")
OUT_NFL = os.path.join(SITE, "nfl_weeks.json")
OUT_NGS = os.path.join(SITE, "ngs.json")

NAILOR_ESPN = 4382466
NAILOR_GSIS = "00-0037291"

NGS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "nextgen_stats/ngs_{kind}.csv.gz"
)
NGS_KINDS = ("receiving", "passing", "rushing")

NGS_KEEP = {
    "receiving": {
        "avg_separation": "sep",
        "avg_cushion": "cushion",
        "avg_yac_above_expectation": "yacoe",
        "avg_yac": "yac",
        "avg_expected_yac": "xyac",
        "targets": "ngs_tgt",
        "receptions": "ngs_rec",
    },
    "passing": {
        "completion_percentage_above_expectation": "cpoe",
        "avg_time_to_throw": "ttt",
        "aggressiveness": "agg",
        "expected_completion_percentage": "xcomp",
        "completion_percentage": "comp",
    },
    "rushing": {
        "rush_yards_over_expected": "ryoe",
        "efficiency": "eff",
        "percent_attempts_gte_eight_defenders": "box8",
        "rush_yards_over_expected_per_att": "ryoe_att",
        "expected_rush_yards": "xryd",
    },
}


def fnum(v):
    if v is None or v == "":
        return None
    if isinstance(v, str) and v.upper() in ("NA", "NAN", "NULL", "NONE"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def r1(v):
    n = fnum(v)
    return None if n is None else round(n, 1)


def r2(v):
    n = fnum(v)
    return None if n is None else round(n, 2)


def r3(v):
    n = fnum(v)
    return None if n is None else round(n, 3)


def put(obj, *keys, value=None):
    if value is None:
        return
    cur = obj
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def affl_espn_pids():
    """ESPN pids that appear in player_index or any year JSON players[]."""
    pids = set()
    idx_path = os.path.join(SITE, "player_index.json")
    idx = json.load(open(idx_path))
    for k in idx:
        try:
            pids.add(int(k))
        except (TypeError, ValueError):
            continue
    years_dir = os.path.join(SITE, "years")
    for name in os.listdir(years_dir):
        if not name.endswith(".json"):
            continue
        d = json.load(open(os.path.join(years_dir, name)))
        for p in d.get("players") or []:
            pid = p.get("pid")
            if pid is None:
                continue
            try:
                pids.add(int(pid))
            except (TypeError, ValueError):
                continue
    return pids, idx


def load_maps(pids):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    gsis_to_espn = {}
    espn_meta = {}
    q = (
        "SELECT player_id, gsis_id, name, position, headshot_url "
        "FROM dim_player WHERE player_id IN ({})".format(
            ",".join(str(p) for p in pids)
        )
    )
    for row in con.execute(q):
        pid = int(row["player_id"])
        gsis = row["gsis_id"] or ""
        espn_meta[pid] = {
            "name": row["name"],
            "pos": row["position"] or "",
            "gsis": gsis,
            "hs": row["headshot_url"] or "",
        }
        if gsis:
            gsis_to_espn.setdefault(gsis, pid)
    xtd = {}
    for row in con.execute(
        "SELECT season, week, gsis_id, xtd, residual, actual_td "
        "FROM fact_xtd_player_week"
    ):
        gsis = row["gsis_id"]
        if gsis not in gsis_to_espn:
            continue
        xtd[(gsis, int(row["season"]), int(row["week"]))] = (
            r2(row["xtd"]),
            r2(row["residual"]),
        )
    roster = {}
    for row in con.execute(
        "SELECT season, week, team_id, player_id, slot, points, started "
        "FROM fact_roster_week"
    ):
        pid = int(row["player_id"])
        if pid not in pids:
            continue
        roster[(pid, int(row["season"]), int(row["week"]))] = {
            "tid": int(row["team_id"]) if row["team_id"] is not None else None,
            "slot": row["slot"] or "",
            "started": 1 if row["started"] else 0,
            "espn_pts": r1(row["points"]),
        }
    con.close()
    return gsis_to_espn, espn_meta, xtd, roster


def yds_td_for(pos, row):
    pyds = fnum(row.get("passing_yards")) or 0
    ryds = fnum(row.get("rushing_yards")) or 0
    recy = fnum(row.get("receiving_yards")) or 0
    ptd = fnum(row.get("passing_tds")) or 0
    rtd = fnum(row.get("rushing_tds")) or 0
    retd = fnum(row.get("receiving_tds")) or 0
    pos = (pos or row.get("position") or "").upper()
    if pos == "QB":
        return round(pyds + ryds), int(ptd + rtd)
    return round(ryds + recy), int(rtd + retd)


def epa_for(row):
    parts = [
        fnum(row.get("passing_epa")),
        fnum(row.get("rushing_epa")),
        fnum(row.get("receiving_epa")),
    ]
    vals = [v for v in parts if v is not None]
    if not vals:
        return None
    return r2(sum(vals))


def extract_weekly(gsis_to_espn, espn_meta, xtd, roster):
    out = {}
    csv_years = []
    for name in sorted(os.listdir(DATA)):
        if not name.startswith("stats_player_week_") or not name.endswith(".csv"):
            continue
        year = name[len("stats_player_week_") : -4]
        if not year.isdigit():
            continue
        csv_years.append(int(year))
        path = os.path.join(DATA, name)
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                gsis = row.get("player_id") or ""
                pid = gsis_to_espn.get(gsis)
                if pid is None:
                    continue
                if (row.get("season_type") or "REG").upper() != "REG":
                    continue
                week = int(float(row["week"]))
                if week <= 0:
                    continue
                season = int(float(row.get("season") or year))
                pos = (espn_meta.get(pid) or {}).get("pos") or row.get("position") or ""
                yds, td = yds_td_for(pos, row)
                rec = {
                    "pts": r1(row.get("fantasy_points")),
                    "opp": row.get("opponent_team") or "",
                    "team": row.get("team") or "",
                    "yds": yds,
                    "td": td,
                    "tgt": int(fnum(row.get("targets")) or 0),
                    "epa": epa_for(row),
                }
                tshare = r3(row.get("target_share"))
                if tshare is not None:
                    rec["tshare"] = tshare
                wopr = r3(row.get("wopr"))
                if wopr is not None:
                    rec["wopr"] = wopr
                xt = xtd.get((gsis, season, week))
                if xt:
                    if xt[0] is not None:
                        rec["xtd"] = xt[0]
                    if xt[1] is not None:
                        rec["res"] = xt[1]
                affl = roster.get((pid, season, week))
                if affl:
                    if affl["tid"] is not None:
                        rec["tid"] = affl["tid"]
                    if affl["slot"]:
                        rec["slot"] = affl["slot"]
                    rec["started"] = affl["started"]
                bucket = out.setdefault(str(pid), {}).setdefault(str(season), {})
                bucket[str(week)] = rec

    # roster-only weeks (bye / DNP / no nflverse row)
    for (pid, season, week), affl in roster.items():
        bucket = out.setdefault(str(pid), {}).setdefault(str(season), {})
        key = str(week)
        if key in bucket:
            continue
        rec = {
            "pts": affl["espn_pts"] if affl["espn_pts"] is not None else 0,
            "started": affl["started"],
        }
        if affl["tid"] is not None:
            rec["tid"] = affl["tid"]
        if affl["slot"]:
            rec["slot"] = affl["slot"]
        bucket[key] = rec

    # attach meta
    for pid, meta in espn_meta.items():
        if str(pid) not in out:
            continue
        out[str(pid)]["meta"] = {
            "gsis": meta["gsis"],
            "name": meta["name"],
            "pos": meta["pos"],
            "hs": meta["hs"],
        }
    return out, csv_years


def ensure_ngs():
    os.makedirs(NGS_DIR, exist_ok=True)
    paths = {}
    for kind in NGS_KINDS:
        dest = os.path.join(NGS_DIR, f"ngs_{kind}.csv.gz")
        paths[kind] = dest
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"NGS cache hit {dest} ({os.path.getsize(dest)} bytes)")
            continue
        url = NGS_URL.format(kind=kind)
        print(f"download {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"  wrote {dest} ({os.path.getsize(dest)} bytes)")
    return paths


def extract_ngs(gsis_to_espn, paths):
    out = {}
    coverage = {k: {"players": set(), "weeks": 0, "week0": 0} for k in NGS_KINDS}
    for kind, path in paths.items():
        keep = NGS_KEEP[kind]
        with gzip.open(path, "rt") as f:
            for row in csv.DictReader(f):
                if (row.get("season_type") or "REG").upper() != "REG":
                    continue
                gsis = row.get("player_gsis_id") or ""
                pid = gsis_to_espn.get(gsis)
                if pid is None:
                    continue
                week = int(float(row["week"]))
                season = int(float(row["season"]))
                rec = {}
                for src, dst in keep.items():
                    val = fnum(row.get(src))
                    if val is None:
                        continue
                    rec[dst] = r3(val) if dst in (
                        "sep", "cushion", "yacoe", "yac", "xyac",
                        "cpoe", "ttt", "agg", "xcomp", "comp",
                        "eff", "box8", "ryoe_att",
                    ) else r1(val)
                if not rec:
                    continue
                rec["kind"] = kind
                bucket = out.setdefault(str(pid), {}).setdefault(str(season), {})
                existing = bucket.get(str(week)) or {}
                existing.update(rec)
                bucket[str(week)] = existing
                coverage[kind]["players"].add(pid)
                if week == 0:
                    coverage[kind]["week0"] += 1
                else:
                    coverage[kind]["weeks"] += 1
    return out, coverage


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, separators=(",", ":"), sort_keys=True)
        f.write("\n")


def verify(nfl, ngs):
    rec = (nfl.get(str(NAILOR_ESPN)) or {}).get("2025") or {}
    weeks = [k for k in rec if k.isdigit() and int(k) > 0]
    pts = sum((rec[k].get("pts") or 0) for k in weeks)
    print(f"VERIFY Nailor 2025 NFL weeks={len(weeks)} pts={pts:.1f}")
    print(f"  weeks={sorted(int(k) for k in weeks)}")
    ngs25 = (ngs.get(str(NAILOR_ESPN)) or {}).get("2025") or {}
    ngs_w = [k for k in ngs25 if k.isdigit() and int(k) > 0]
    print(f"VERIFY Nailor 2025 NGS weeks={len(ngs_w)} (week0={'0' in ngs25})")
    if ngs_w:
        print(f"  ngs weeks={sorted(int(k) for k in ngs_w)}")
        print(f"  sample W{ngs_w[0]}={ngs25[ngs_w[0]]}")
    affl_w = [k for k in weeks if rec[k].get("tid") is not None or rec[k].get("slot")]
    print(f"VERIFY Nailor 2025 AFFL-rostered overlay weeks={len(affl_w)} {affl_w}")
    return len(weeks), pts


def main():
    pids, idx = affl_espn_pids()
    print(f"AFFL players (index ∪ year JSON): {len(pids)}")
    print(f"player_index.json: {len(idx)}")
    gsis_to_espn, espn_meta, xtd, roster = load_maps(pids)
    print(f"dim_player matched: {len(espn_meta)}")
    print(f"with gsis: {sum(1 for m in espn_meta.values() if m['gsis'])}")
    print(f"xtd player-weeks: {len(xtd)}")
    print(f"AFFL roster player-weeks: {len(roster)}")

    nfl, csv_years = extract_weekly(gsis_to_espn, espn_meta, xtd, roster)
    n_players = sum(1 for k in nfl if k != "meta" and any(
        wk.isdigit() for yr, weeks in nfl[k].items() if yr.isdigit() for wk in weeks
    ))
    n_pw = 0
    for pid, years in nfl.items():
        for y, weeks in years.items():
            if y == "meta":
                continue
            n_pw += sum(1 for w in weeks if w.isdigit() and int(w) > 0)
    print(f"nflverse CSV years: {csv_years}")
    print(f"AFFL players with any NFL week: {n_players}")
    print(f"NFL player-weeks written: {n_pw}")

    paths = ensure_ngs()
    ngs, cov = extract_ngs(gsis_to_espn, paths)
    ngs_players = len(ngs)
    ngs_weeks = 0
    ngs_w0 = 0
    for years in ngs.values():
        for y, weeks in years.items():
            for w in weeks:
                if not w.isdigit():
                    continue
                if int(w) == 0:
                    ngs_w0 += 1
                else:
                    ngs_weeks += 1
    print(f"NGS players: {ngs_players}")
    print(f"NGS weekly rows: {ngs_weeks}  week0 totals: {ngs_w0}")
    for kind, c in cov.items():
        print(f"  {kind}: players={len(c['players'])} weeks={c['weeks']} week0={c['week0']}")

    dump(OUT_NFL, nfl)
    dump(OUT_NGS, ngs)
    print(f"wrote {OUT_NFL} ({os.path.getsize(OUT_NFL)} bytes)")
    print(f"wrote {OUT_NGS} ({os.path.getsize(OUT_NGS)} bytes)")
    print("official NGS chart links: skipped (NGS player codes not in nflverse)")

    weeks, pts = verify(nfl, ngs)
    if weeks < 14:
        print(f"STOP: Nailor 2025 has {weeks} NFL weeks (need >= 14)")
        return 1
    if abs(pts - 71.7) > 2:
        print(f"STOP: Nailor 2025 pts {pts} not ≈ 71.7")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
