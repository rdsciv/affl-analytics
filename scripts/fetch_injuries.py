#!/usr/bin/env python3
"""Cache NFL injury report + depth charts from ESPN sports APIs.

Writes site/injuries.json (keyed by athlete id) and site/depthcharts.json.
ESPN is hit here only — never from the browser.

Injuries: sports.core per-team /teams/{id}/injuries?limit=100, then resolve $refs.
Do not use site /teams/{id}/injuries (empty) or the league-wide dump.
Depth: site.api /teams/{id}/depthcharts (Hurts is PHI QB1).
Athlete-level /injuries without a year is 404 — not used.
Status is ESPN's own string. Empty if missing. Never invent IR.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
YEAR_PATH = os.path.join(SITE, "years", "2025.json")
INJ_OUT = os.path.join(SITE, "injuries.json")
DEPTH_OUT = os.path.join(SITE, "depthcharts.json")

UA = {
    "User-Agent": "AFFL-injuries/1.0 (+local cache; not a browser)",
    "Accept": "application/json",
}

# ESPN NFL team ids — same map as fetch.py PRO (1–30, 33, 34; no 31/32).
TEAMS = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN",
    8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR",
    15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI",
    22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WSH",
    29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}

INJ_LIST = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/teams/{id}/injuries?limit=100"
DEPTH_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{id}/depthcharts"
ATHLETE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/{id}"

ATHLETE_RE = re.compile(r"/athletes/(\d+)", re.I)
TEAM_RE = re.compile(r"/teams/(\d+)", re.I)

# Fantasy-facing position from depth-chart slot / parent abbrev.
POS_MAP = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "LWR": "WR", "RWR": "WR",
    "SWR": "WR", "SLWR": "WR", "SRWR": "WR", "TE": "TE", "PK": "K", "K": "K",
    "P": "P", "LS": "LS",
}

SKILL = ("QB", "RB", "WR", "TE", "K")


def https(url):
    if not url:
        return url
    return url.replace("http://", "https://", 1)


def get_json(url, timeout=30):
    url = https(url)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = getattr(r, "status", None) or r.getcode()
        if code != 200 or not raw:
            return None, code or 0
        try:
            return json.loads(raw.decode("utf-8")), 200
        except json.JSONDecodeError:
            return None, 200
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, 0


def athlete_id_from(obj_or_url):
    if isinstance(obj_or_url, dict):
        if obj_or_url.get("id") not in (None, ""):
            return str(obj_or_url["id"])
        obj_or_url = obj_or_url.get("$ref") or ""
    m = ATHLETE_RE.search(str(obj_or_url or ""))
    return m.group(1) if m else ""


def team_abbr_from(obj, fallback=""):
    if isinstance(obj, dict):
        if obj.get("abbreviation"):
            return str(obj["abbreviation"]).upper()
        ref = obj.get("$ref") or ""
        m = TEAM_RE.search(ref)
        if m:
            return TEAMS.get(int(m.group(1)), fallback)
    return fallback


def espn_status(payload):
    """Pass through ESPN's status. Do not invent IR or remap Active."""
    s = payload.get("status")
    if s not in (None, ""):
        return str(s)
    typ = payload.get("type") or {}
    desc = typ.get("description") or typ.get("name") or ""
    if not desc:
        return ""
    desc = str(desc)
    if desc.startswith("INJURY_STATUS_"):
        desc = desc[len("INJURY_STATUS_"):].replace("_", " ")
    return desc[:1].upper() + desc[1:] if desc else ""


def comment_of(payload):
    for k in ("shortComment", "longComment", "comment"):
        v = payload.get(k)
        if v:
            return str(v)
    return ""


def names_from_year():
    out = {}
    if not os.path.exists(YEAR_PATH):
        return out
    year = json.load(open(YEAR_PATH))
    for pid, meta in (year.get("pmeta") or {}).items():
        if meta and meta[0]:
            out[str(pid)] = meta[0]
    for p in year.get("players") or []:
        pid = p.get("pid")
        if pid is not None and p.get("name"):
            out[str(pid)] = p["name"]
    return out


def parse_depth(team_id, payload, name_map):
    """Compact per-athlete depth. Rank 1 = first listed at that slot."""
    abbr = (payload.get("team") or {}).get("abbreviation") or TEAMS.get(team_id, "")
    abbr = str(abbr).upper()
    rows = {}
    for chart in payload.get("depthchart") or []:
        positions = chart.get("positions") or {}
        for slot in positions.values():
            pos_obj = slot.get("position") or {}
            raw = (pos_obj.get("abbreviation") or "").upper()
            parent = ((pos_obj.get("parent") or {}).get("abbreviation") or "").upper()
            pos = POS_MAP.get(raw) or POS_MAP.get(parent) or raw
            athletes = slot.get("athletes") or []
            for i, a in enumerate(athletes):
                aid = str(a.get("id") or "")
                if not aid:
                    continue
                name = a.get("displayName") or a.get("fullName") or ""
                if name:
                    name_map[aid] = name
                rank = i + 1
                rec = {
                    "athleteId": aid,
                    "name": name or name_map.get(aid, ""),
                    "team": abbr,
                    "pos": pos,
                    "rank": rank,
                    "depth": f"{abbr} {pos}{rank}" if pos else "",
                }
                prev = rows.get(aid)
                if prev is None:
                    rows[aid] = rec
                    continue
                # Prefer skill-position rows, then the better (lower) rank.
                prev_skill = prev["pos"] in SKILL
                new_skill = pos in SKILL
                if new_skill and not prev_skill:
                    rows[aid] = rec
                elif new_skill == prev_skill and rank < prev["rank"]:
                    rows[aid] = rec
    return rows


def fetch_all_depth(name_map):
    out = {}
    print("depth charts: %d teams" % len(TEAMS))
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(get_json, DEPTH_URL.format(id=tid)): tid for tid in TEAMS}
        for fut in as_completed(futs):
            tid = futs[fut]
            data, code = fut.result()
            abbr = TEAMS[tid]
            if code != 200 or not data:
                print("  depth %s (%s) HTTP %s — skip" % (abbr, tid, code))
                continue
            rows = parse_depth(tid, data, name_map)
            out.update(rows)
            print("  depth %s %d athletes" % (abbr, len(rows)))
    return out


def list_injury_refs(tid):
    data, code = get_json(INJ_LIST.format(id=tid))
    if code != 200 or not data:
        return [], code
    items = data.get("items") or []
    refs = []
    for it in items:
        ref = it.get("$ref") if isinstance(it, dict) else None
        if ref:
            refs.append(https(ref))
        elif isinstance(it, dict) and it.get("id"):
            refs.append(it)  # already resolved
    return refs, 200


def row_from_injury(payload, team_abbr, name_map):
    aid = athlete_id_from(payload.get("athlete") or payload.get("$ref") or "")
    if not aid:
        return None
    name = name_map.get(aid, "")
    team = team_abbr_from(payload.get("team"), team_abbr)
    return {
        "athleteId": aid,
        "name": name,
        "status": espn_status(payload),
        "comment": comment_of(payload),
        "team": team,
        "date": payload.get("date") or "",
    }


def newer(a, b):
    """True if a should replace b (newer date, else keep existing)."""
    da, db = a.get("date") or "", b.get("date") or ""
    return da > db


def fetch_all_injuries(name_map):
    refs = []
    print("injury lists: %d teams" % len(TEAMS))
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(list_injury_refs, tid): tid for tid in TEAMS}
        for fut in as_completed(futs):
            tid = futs[fut]
            items, code = fut.result()
            abbr = TEAMS[tid]
            if code != 200:
                print("  inj %s (%s) HTTP %s — empty" % (abbr, tid, code))
                continue
            print("  inj %s %d refs" % (abbr, len(items)))
            for ref in items:
                refs.append((abbr, ref))

    rows = {}
    resolved = 0
    failed = 0

    def resolve(pair):
        abbr, ref = pair
        if isinstance(ref, dict):
            return abbr, ref, 200
        data, code = get_json(ref)
        return abbr, data, code

    print("resolving %d injury $refs" % len(refs))
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(resolve, pair) for pair in refs]
        for fut in as_completed(futs):
            abbr, data, code = fut.result()
            if code != 200 or not data:
                failed += 1
                continue
            rec = row_from_injury(data, abbr, name_map)
            if not rec or not rec["athleteId"]:
                failed += 1
                continue
            resolved += 1
            aid = rec["athleteId"]
            prev = rows.get(aid)
            if prev is None or newer(rec, prev):
                rows[aid] = rec
    print("resolved %d refs (%d failed/empty) → %d athletes" % (resolved, failed, len(rows)))
    return rows


def fill_names(rows, name_map):
    missing = [aid for aid, rec in rows.items() if not rec.get("name")]
    if not missing:
        return
    print("athlete names: %d missing" % len(missing))

    def one(aid):
        data, code = get_json(ATHLETE.format(id=aid))
        if code != 200 or not data:
            return aid, ""
        return aid, data.get("displayName") or data.get("fullName") or ""

    filled = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for aid, name in ex.map(one, missing):
            if name:
                name_map[aid] = name
                rows[aid]["name"] = name
                filled += 1
    print("  filled %d names (%d still empty)" % (filled, len(missing) - filled))


def main():
    t0 = time.time()
    name_map = names_from_year()
    print("year-file names: %d" % len(name_map))

    depth = fetch_all_depth(name_map)
    injuries = fetch_all_injuries(name_map)
    fill_names(injuries, name_map)
    # depth names already applied; backfill injury names into depth
    for aid, rec in depth.items():
        if not rec.get("name"):
            rec["name"] = name_map.get(aid, "")

    os.makedirs(SITE, exist_ok=True)
    json.dump(injuries, open(INJ_OUT, "w"), indent=2, sort_keys=True)
    json.dump(depth, open(DEPTH_OUT, "w"), indent=2, sort_keys=True)

    hurts = depth.get("4040715") or {}
    print("wrote %s (%d injuries)" % (INJ_OUT, len(injuries)))
    print("wrote %s (%d depth rows)" % (DEPTH_OUT, len(depth)))
    print("Hurts depth: %s" % (hurts.get("depth") or hurts or "missing"))
    print("elapsed %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
