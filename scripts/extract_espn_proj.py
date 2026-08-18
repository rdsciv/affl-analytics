#!/usr/bin/env python3
"""Extract ESPN weekly projected fantasy points into site/proj.json.

The compacted season caches (data/box_YYYY.json) store only
[pid, slot, actual_pts] — they drop projections. Leftover raw weekly
dumps (data/box_w*.json) are ESPN mMatchup payloads and still carry
projected totals. Historical backfill dumps live at
data/box_raw/{year}/w{n}.json and are merged without wiping 2025.

On those raw dumps, ESPN does not use a `projectedPoints` field.
Weekly projection is:

    player.stats[] where
        statSourceId == 1          # 1 = projected, 0 = actual
        scoringPeriodId == week    # that week only; 0 is season
        statSplitTypeId == 1       # weekly split (preferred)
    .appliedTotal

`appliedTotal` is already scored with this league's AFFL settings.
We store that number. We do not scrape ESPN, do not pull a public
"standard" board, and do not invent 0 for a missing week.
A stored 0 means ESPN actually projected 0.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "site", "proj.json")

TAYLOR = 4242335


def fnum(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def weekly_applied(stats, week, source_id):
    """Return appliedTotal for source/week. Prefer statSplitTypeId == 1."""
    best = None
    best_split = None
    field = None
    for st in stats or []:
        if st.get("statSourceId") != source_id:
            continue
        if st.get("scoringPeriodId") != week:
            continue
        tot = fnum(st.get("appliedTotal"))
        if tot is None:
            tot = fnum(st.get("appliedProjectedReal"))
        if tot is None:
            continue
        split = st.get("statSplitTypeId")
        if best is None or split == 1:
            best = tot
            best_split = split
            src = "appliedTotal" if st.get("appliedTotal") is not None else "appliedProjectedReal"
            field = (
                f"stats[statSourceId={source_id},"
                f"scoringPeriodId={week},statSplitTypeId={split}].{src}"
            )
            if split == 1:
                break
    return best, field


def extract_raw(path, fallback_week=None):
    """Yield (season, week, pid, proj, field) from a raw ESPN dump."""
    try:
        d = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(d, dict) or "schedule" not in d:
        return
    season = d.get("seasonId")
    if not season:
        return
    file_week = d.get("scoringPeriodId") or fallback_week
    for g in d.get("schedule") or []:
        week = g.get("matchupPeriodId") or file_week
        if week is None:
            continue
        if file_week is not None and week != file_week:
            continue
        for side in ("home", "away"):
            s = g.get(side) or {}
            roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
            if not roster:
                continue
            for e in roster.get("entries") or []:
                ppe = e.get("playerPoolEntry") or {}
                p = ppe.get("player") or {}
                pid = p.get("id") if p.get("id") is not None else e.get("playerId")
                if pid is None:
                    continue
                # fallbacks on the player object (rare)
                proj, field = weekly_applied(p.get("stats"), week, 1)
                if proj is None:
                    for key in ("appliedProjectedReal", "projectedPointTotal"):
                        if key in p:
                            proj = fnum(p.get(key))
                            if proj is not None:
                                field = f"player.{key}"
                                break
                        if key in ppe:
                            proj = fnum(ppe.get(key))
                            if proj is not None:
                                field = f"playerPoolEntry.{key}"
                                break
                if proj is None:
                    continue
                yield int(season), int(week), int(pid), proj, field


def compacted_has_proj(path):
    """True if a box_YYYY.json still carries projection fields."""
    try:
        d = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(d, dict):
        return False
    if "schedule" in d:
        return True
    weeks = d.get("weeks") or {}
    for games in weeks.values():
        for g in games or []:
            for side in ("home", "away"):
                for row in ((g.get(side) or {}).get("roster") or []):
                    if isinstance(row, dict) and any(
                        k in row
                        for k in ("proj", "projected", "appliedProjectedReal", "projectedPointTotal")
                    ):
                        return True
                    if isinstance(row, (list, tuple)) and len(row) > 3:
                        return True
    return False


def put(out, season, week, pid, proj):
    y = out.setdefault(str(season), {})
    p = y.setdefault(str(pid), {})
    key = str(week)
    # keep first; values from the same box should match
    if key not in p:
        p[key] = round(proj, 2) if proj != 0 else 0


def print_taylor_sample():
    """VERIFY: print one Jonathan Taylor 2025 week sample from the raw box."""
    path = os.path.join(DATA, "box_w1.json")
    if not os.path.exists(path):
        print("VERIFY: data/box_w1.json missing — cannot print Taylor sample")
        return
    d = json.load(open(path))
    week = d.get("scoringPeriodId") or 1
    print("VERIFY Jonathan Taylor 2025 week sample (from data/box_w1.json)")
    print(f"  seasonId={d.get('seasonId')} scoringPeriodId={week}")
    for g in d.get("schedule") or []:
        if g.get("matchupPeriodId") not in (None, week):
            continue
        for side in ("home", "away"):
            s = g.get(side) or {}
            roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
            if not roster:
                continue
            for e in roster.get("entries") or []:
                ppe = e.get("playerPoolEntry") or {}
                p = ppe.get("player") or {}
                if (p.get("id") or e.get("playerId")) != TAYLOR:
                    continue
                print(f"  name={p.get('fullName')} pid={p.get('id')}")
                print(f"  player keys={sorted(p.keys())}")
                print("  stats rows:")
                for st in p.get("stats") or []:
                    print(
                        "   ",
                        {
                            "statSourceId": st.get("statSourceId"),
                            "scoringPeriodId": st.get("scoringPeriodId"),
                            "statSplitTypeId": st.get("statSplitTypeId"),
                            "appliedTotal": st.get("appliedTotal"),
                            "appliedProjectedReal": st.get("appliedProjectedReal"),
                            "projectedPointTotal": st.get("projectedPointTotal"),
                        },
                    )
                actual, af = weekly_applied(p.get("stats"), week, 0)
                proj, pf = weekly_applied(p.get("stats"), week, 1)
                print(f"  W1 actual={actual} via {af}")
                print(f"  W1 proj={proj} via {pf}")
                return
    print("  Taylor not found in box_w1 matchup rosters")


def print_taylor_season(out):
    print("Jonathan Taylor 2025 W1–W17 actual vs proj (from leftover box_w*.json)")
    rec = (out.get("2025") or {}).get(str(TAYLOR)) or {}
    for w in range(1, 18):
        path = os.path.join(DATA, f"box_w{w}.json")
        actual = None
        proj = None
        if os.path.exists(path):
            d = json.load(open(path))
            week = d.get("scoringPeriodId") or w
            for g in d.get("schedule") or []:
                if g.get("matchupPeriodId") not in (None, week, w):
                    continue
                for side in ("home", "away"):
                    s = g.get(side) or {}
                    roster = s.get("rosterForCurrentScoringPeriod") or s.get("rosterForMatchupPeriod")
                    if not roster:
                        continue
                    for e in roster.get("entries") or []:
                        ppe = e.get("playerPoolEntry") or {}
                        p = ppe.get("player") or {}
                        if (p.get("id") or e.get("playerId")) != TAYLOR:
                            continue
                        actual, _ = weekly_applied(p.get("stats"), week, 0)
                        if actual is None:
                            actual = fnum(ppe.get("appliedStatTotal"))
                        proj, _ = weekly_applied(p.get("stats"), week, 1)
        stored = rec.get(str(w))
        if actual is None and proj is None and stored is None:
            print(f"  W{w}: skip (no box / no proj — bye or not rostered)")
            continue
        print(f"  W{w}: actual={actual}  proj={proj}  stored={stored}")


def main():
    out = {}
    field_seen = {}
    raw_files = 0
    compacted = []

    # 0) keep any already-exported years (do not wipe 2025)
    if os.path.exists(OUT):
        try:
            existing = json.load(open(OUT))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            for season, players in existing.items():
                if not isinstance(players, dict):
                    continue
                for pid, weeks in players.items():
                    if not isinstance(weeks, dict):
                        continue
                    for wk, proj in weeks.items():
                        val = fnum(proj)
                        if val is None:
                            continue
                        try:
                            put(out, int(season), int(wk), int(pid), val)
                        except (TypeError, ValueError):
                            continue
            print(f"seeded existing {OUT}: years={sorted(out)}")

    # 1) leftover raw weekly dumps
    for name in sorted(os.listdir(DATA), key=lambda n: (len(n), n)):
        m = re.fullmatch(r"box_w(\d+)\.json", name)
        if not m:
            continue
        path = os.path.join(DATA, name)
        n = 0
        for season, week, pid, proj, field in extract_raw(path, fallback_week=int(m.group(1))):
            put(out, season, week, pid, proj)
            field_seen[field] = field_seen.get(field, 0) + 1
            n += 1
        raw_files += 1
        print(f"read {name}: {n} player-weeks with weekly proj")

    # 1b) historical raw weekly dumps (data/box_raw/{year}/w{n}.json)
    raw_root = os.path.join(DATA, "box_raw")
    if os.path.isdir(raw_root):
        year_dirs = sorted(
            n for n in os.listdir(raw_root)
            if n.isdigit() and os.path.isdir(os.path.join(raw_root, n))
        )
        for year_name in year_dirs:
            ydir = os.path.join(raw_root, year_name)
            names = [n for n in os.listdir(ydir) if re.fullmatch(r"w(\d+)\.json", n)]
            names.sort(key=lambda n: int(re.fullmatch(r"w(\d+)\.json", n).group(1)))
            year_n = 0
            for name in names:
                m = re.fullmatch(r"w(\d+)\.json", name)
                path = os.path.join(ydir, name)
                n = 0
                for season, week, pid, proj, field in extract_raw(path, fallback_week=int(m.group(1))):
                    put(out, season, week, pid, proj)
                    field_seen[field] = field_seen.get(field, 0) + 1
                    n += 1
                raw_files += 1
                year_n += n
                print(f"read box_raw/{year_name}/{name}: {n} player-weeks with weekly proj")
            print(f"box_raw/{year_name}: {year_n} player-weeks")
    else:
        print("no data/box_raw/ tree")

    # 2) season box_YYYY.json — only if they still look like raw ESPN or carry proj
    for name in sorted(os.listdir(DATA)):
        m = re.fullmatch(r"box_(\d{4})\.json", name)
        if not m:
            continue
        path = os.path.join(DATA, name)
        d = json.load(open(path))
        if isinstance(d, dict) and "schedule" in d:
            n = 0
            for season, week, pid, proj, field in extract_raw(path):
                put(out, season, week, pid, proj)
                field_seen[field] = field_seen.get(field, 0) + 1
                n += 1
            print(f"read {name} (raw): {n} player-weeks")
        else:
            has = compacted_has_proj(path)
            compacted.append((name, has))
            print(
                f"read {name}: compacted [pid, slot, actual] — "
                + ("has extra proj-like fields" if has else "no projection fields")
            )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")

    n_pw = sum(len(weeks) for year in out.values() for weeks in year.values())
    n_players = sum(len(year) for year in out.values())
    print()
    print("field names used:")
    for k, v in sorted(field_seen.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5}  {k}")
    print(f"wrote {OUT}")
    print(f"years: {sorted(out)}")
    print(f"players with any proj: {n_players}")
    print(f"player-weeks with a projection: {n_pw}")
    for y in sorted(out):
        pw = sum(len(w) for w in out[y].values())
        print(f"  {y}: {len(out[y])} players, {pw} player-weeks")
    print()
    print_taylor_sample()
    print()
    print_taylor_season(out)
    if not field_seen:
        print("STOP: no projected totals and no projected stat lines in the box cache.")
        print("Did not scrape live ESPN.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
