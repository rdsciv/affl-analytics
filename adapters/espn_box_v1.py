#!/usr/bin/env python3
"""Versioned ESPN box-score matchup adapter (v1).

Reads the compacted season box cache written by fetch.py
(`data/box_{season}.json`). That cache is already on disk.

This module never opens `.env`, never imports `fetch`, and never talks
to ESPN. Credentials stay in runtime configuration.

    ADAPTER_ID      = espn_box
    ADAPTER_VERSION = v1
"""
import hashlib
import json
import os
from collections import defaultdict

ADAPTER_ID = "espn_box"
ADAPTER_VERSION = "v1"


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest(), os.path.getsize(path)


def load_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    return d[0] if isinstance(d, list) else d


def _reg_weeks(league, fallback=13):
    ss = ((league or {}).get("settings") or {}).get("scheduleSettings") or {}
    return ss.get("matchupPeriodCount") or fallback


def _source_rec(data_dir, path):
    sha, n = file_sha256(path)
    rel = os.path.relpath(path, os.path.dirname(data_dir))
    # data_dir is .../data, parent is the repo; store as data/box_2025.json
    rel = os.path.join(os.path.basename(data_dir), os.path.basename(path))
    return {"path": rel.replace("\\", "/"), "sha256": sha, "bytes": n}


def rows_from_box(box, season, reg_weeks):
    """Two sides per game. Same grain as fact_matchup / historical load_matchups."""
    rows = []
    for wk_s, games in ((box or {}).get("weeks") or {}).items():
        wk = int(wk_s)
        for g in games:
            h, a = g["home"], g["away"]
            if not h or not a or h.get("tid") is None or a.get("tid") is None:
                continue
            tier = g.get("tier", "NONE")
            if tier is None:
                tier = "NONE"
            playoff = 1 if (tier != "NONE" or wk > reg_weeks) else 0
            rows.append((season, wk, h["tid"], a["tid"], h["pts"], a["pts"], 1, tier, playoff))
            rows.append((season, wk, a["tid"], h["tid"], a["pts"], h["pts"], 0, tier, playoff))
    return rows


def rows_from_league_schedule(league, season, reg_weeks):
    """Pre-2018 fallback when the box cache has no weeks. Skips byes and 0-0."""
    synth = defaultdict(list)
    for g in (league or {}).get("schedule") or []:
        h, a = g.get("home"), g.get("away")
        if not h or not a:
            continue
        hp = round(h.get("totalPoints") or 0, 1)
        ap = round(a.get("totalPoints") or 0, 1)
        if not hp and not ap:
            continue
        synth[str(g["matchupPeriodId"])].append(
            {"tier": g.get("playoffTierType", "NONE") or "NONE",
             "home": {"tid": h["teamId"], "pts": hp},
             "away": {"tid": a["teamId"], "pts": ap}}
        )
    return rows_from_box({"weeks": dict(synth)}, season, reg_weeks)


def extract(data_dir, season, reg_weeks=None):
    """Parse one season. Returns rows + source checksums. No database writes."""
    box_path = os.path.join(data_dir, f"box_{season}.json")
    league_path = os.path.join(data_dir, f"league_{season}.json")
    league = load_json(league_path)
    if reg_weeks is None:
        reg_weeks = _reg_weeks(league, 13)
    box = load_json(box_path)
    weeks = (box or {}).get("weeks") or {}
    if weeks:
        rows = rows_from_box(box, season, reg_weeks)
        primary = box_path
    elif league:
        rows = rows_from_league_schedule(league, season, reg_weeks)
        primary = league_path
    else:
        rows = []
        primary = None
    sources = []
    for p in (box_path, league_path):
        if os.path.exists(p):
            sources.append(_source_rec(data_dir, p))
    return {
        "adapter": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "season": season,
        "reg_weeks": reg_weeks,
        "rows": rows,
        "sources": sources,
        "primary": os.path.basename(primary) if primary else None,
    }
