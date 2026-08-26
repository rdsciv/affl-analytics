#!/usr/bin/env python3
"""Opportunity xTD from nflverse play-by-play.

Model (SPEC.md / METRICS.md):
    xTD = SUM over rush / pass-target plays of
          P(TD | yardline_100, down, ydstogo, play_type)
    fit per season from that season's pbp.
    residual = actual TDs - xTD

Rush xTD credits the rusher. Receiving xTD credits the targeted receiver.
Passing TDs are the receiver's TDs; they are not counted again on the QB.

P is an empirical frequency in bins of (yardline, down, ydstogo, play_type),
fit on that season's regular-season pbp only. Sparse bins fall back to
(yardline, play_type), then yardline alone. Laplace (0.5) on the raw count.

pbp is not shipped in the repo (~19 MB gzip per season). This script
downloads csv.gz from the nflverse release into data/pbp/ and streams it
with the stdlib (no pandas). If a download fails, that season is skipped
and the gap is reported. Nothing is invented.

    python3 compute_xtd.py              # 2014-2025, download if needed
    python3 compute_xtd.py --season 2025
    python3 compute_xtd.py --no-download   # only use files already on disk

Roster rollup (team portfolio) uses fact_roster_week, so it is populated
for 2018-2025 only. Player-week xTD itself is stored for every season
the pbp file loaded.
"""
import argparse
import csv
import gzip
import os
import sqlite3
import sys
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PBP = os.path.join(DATA, "pbp")
DB = os.path.join(HERE, "affl.db")
PBP_URL = ("https://github.com/nflverse/nflverse-data/releases/download/"
           "pbp/play_by_play_{year}.csv.gz")

KEEP = {
    "season", "week", "season_type",
    "yardline_100", "down", "ydstogo", "play_type",
    "rush_attempt", "pass_attempt",
    "rusher_player_id", "receiver_player_id",
    "rush_touchdown", "pass_touchdown", "touchdown",
    "qb_kneel", "qb_spike",
}

FIRST, LAST = 2014, 2025


def yard_bin(yl):
    try:
        yl = int(float(yl))
    except (TypeError, ValueError):
        return None
    if yl <= 0:
        return 1
    if yl <= 5:
        return yl
    if yl <= 10:
        return 10
    if yl <= 15:
        return 15
    if yl <= 20:
        return 20
    if yl <= 30:
        return 30
    if yl <= 50:
        return 50
    return 99


def togo_bin(ytg):
    try:
        ytg = int(float(ytg))
    except (TypeError, ValueError):
        return None
    if ytg <= 1:
        return 1
    if ytg <= 3:
        return 3
    if ytg <= 6:
        return 6
    if ytg <= 10:
        return 10
    return 15


def down_bin(d):
    try:
        d = int(float(d))
    except (TypeError, ValueError):
        return None
    if d < 1 or d > 4:
        return None
    return d


def flag(v):
    if v in (None, "", "NA", "na"):
        return 0
    try:
        return 1 if float(v) == 1 else 0
    except ValueError:
        return 1 if str(v).lower() in ("true", "t", "yes") else 0


def ensure_pbp(year, download=True):
    os.makedirs(PBP, exist_ok=True)
    dest = os.path.join(PBP, f"play_by_play_{year}.csv.gz")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return dest, "cached"
    if not download:
        return None, "missing"
    url = PBP_URL.format(year=year)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        if os.path.getsize(dest) < 1000:
            os.remove(dest)
            return None, "tiny"
        return dest, "downloaded"
    except Exception as e:
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        return None, f"FAIL({type(e).__name__}: {e})"


def iter_plays(path):
    with gzip.open(path, "rt", newline="") as f:
        reader = csv.DictReader(f)
        fields = [c for c in reader.fieldnames or [] if c in KEEP]
        for raw in reader:
            if raw.get("season_type") != "REG":
                continue
            if flag(raw.get("qb_kneel")) or flag(raw.get("qb_spike")):
                continue
            play = raw.get("play_type")
            rush = flag(raw.get("rush_attempt")) and raw.get("rusher_player_id")
            catch = flag(raw.get("pass_attempt")) and raw.get("receiver_player_id")
            if rush and play in (None, "", "run", "qb_kneel"):
                ptype = "run"
                pid = raw["rusher_player_id"]
                td = flag(raw.get("rush_touchdown")) or (
                    flag(raw.get("touchdown")) and play == "run"
                )
            elif catch:
                ptype = "pass"
                pid = raw["receiver_player_id"]
                td = flag(raw.get("pass_touchdown"))
            else:
                continue
            yb, db, tb = yard_bin(raw.get("yardline_100")), down_bin(raw.get("down")), togo_bin(raw.get("ydstogo"))
            if yb is None:
                continue
            try:
                week = int(float(raw["week"]))
                season = int(float(raw["season"]))
            except (TypeError, ValueError, KeyError):
                continue
            yield season, week, pid, ptype, yb, db, tb, td


def fit_and_score(path):
    """Two-pass: counts, then score. File is streamed twice (gzip is cheap)."""
    counts = defaultdict(lambda: [0, 0])  # key -> [plays, tds]

    def add(key, td):
        counts[key][0] += 1
        counts[key][1] += td

    n_plays = 0
    for season, week, pid, ptype, yb, db, tb, td in iter_plays(path):
        n_plays += 1
        add(("full", yb, db, tb, ptype), td)
        add(("yd_pt", yb, ptype), td)
        add(("yd", yb), td)
    if n_plays == 0:
        return [], 0

    def p_td(yb, db, tb, ptype):
        for key, min_n in (
            (("full", yb, db, tb, ptype), 8),
            (("yd_pt", yb, ptype), 8),
            (("yd", yb), 1),
        ):
            n, t = counts.get(key, (0, 0))
            if n >= min_n:
                return (t + 0.5) / (n + 1.0)
        return 0.0

    # player-week: gsis -> [rush_td, rec_td, rush_xtd, rec_xtd]
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for season, week, pid, ptype, yb, db, tb, td in iter_plays(path):
        p = p_td(yb, db, tb, ptype)
        slot = agg[(season, week, pid)]
        if ptype == "run":
            slot[0] += td
            slot[2] += p
        else:
            slot[1] += td
            slot[3] += p
    rows = []
    for (season, week, gsis), (rtd, ctd, rx, cx) in agg.items():
        actual = rtd + ctd
        xtd = rx + cx
        rows.append((season, week, gsis, rtd, ctd, actual, rx, cx, xtd, actual - xtd))
    return rows, n_plays


def persist(con, rows):
    gsis_to_pid = {g: pid for pid, g in con.execute(
        "SELECT player_id, gsis_id FROM dim_player WHERE gsis_id IS NOT NULL")}
    roster = {(s, w, pid): tid for s, w, tid, pid in con.execute(
        "SELECT season, week, team_id, player_id FROM fact_roster_week")}
    # if a player appears on two teams in a week (trade), last write wins;
    # rare and we do not guess which snap belonged to whom.
    out = []
    seasons = set()
    for season, week, gsis, rtd, ctd, actual, rx, cx, xtd, resid in rows:
        pid = gsis_to_pid.get(gsis)
        tid = roster.get((season, week, pid)) if pid is not None else None
        out.append((season, week, gsis, pid, tid, rtd, ctd, actual, rx, cx, xtd, resid))
        seasons.add(season)
    for s in seasons:
        con.execute("DELETE FROM fact_xtd_player_week WHERE season=?", (s,))
    con.executemany(
        """INSERT OR REPLACE INTO fact_xtd_player_week
           (season, week, gsis_id, player_id, team_id,
            rush_td, rec_td, actual_td, rush_xtd, rec_xtd, xtd, residual)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        out,
    )
    return len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()
    years = [args.season] if args.season else list(range(FIRST, LAST + 1))

    if not os.path.exists(DB):
        sys.exit(f"missing {DB} — run python3 build_db.py first")
    con = sqlite3.connect(DB)
    con.executescript(open(os.path.join(HERE, "schema.sql")).read())

    loaded = []
    gaps = []
    for y in years:
        path, status = ensure_pbp(y, download=not args.no_download)
        print(f"  pbp {y}: {status}")
        if path is None:
            gaps.append((y, status))
            continue
        rows, n_plays = fit_and_score(path)
        if not rows:
            gaps.append((y, "no scorable plays"))
            continue
        n = persist(con, rows)
        con.commit()
        loaded.append((y, n, n_plays))
        print(f"    {n_plays} plays -> {n} player-weeks")

    print(f"xTD seasons loaded: {len(loaded)}  gaps: {len(gaps)}")
    for y, why in gaps:
        print(f"  gap {y}: {why}")
    return 0 if loaded else 1


if __name__ == "__main__":
    sys.exit(main())
