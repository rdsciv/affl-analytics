#!/usr/bin/env python3
"""Eight-feature site payloads. Called from export_site.py.

Uses warehouse tables already on disk (fact_nfl_week, fact_xtd_*,
fact_roster_week, fact_draft_pick, v_power / v_luck_weighted / v_standings,
nflverse roster CSVs). Does not invent NGS, college team-season totals,
or 2025 records.
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import sqlite3
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SITE = os.path.join(HERE, "site")
BIO = os.path.join(SITE, "player_bio.json")
MILES = os.path.join(SITE, "miles.json")
NCAA_DIR = os.path.join(SITE, "logos", "ncaa")
ESPN_TEAMS = (
    "https://site.web.api.espn.com/apis/site/v2/sports/football/"
    "college-football/teams?limit=2000"
)

CATES = [58, 40, 24, 13, 12, 9]
POS_SKILL = {"RB", "WR", "TE", "FB"}
POS_AWARD = {"QB", "RB", "WR", "TE", "K", "DST"}
UA = {"User-Agent": "Mozilla/5.0 AFFL-analytics"}

# nflverse roster college -> ESPN location / short name
COLLEGE_ALIASES = {
    "louisiana state": "lsu",
    "southern california": "usc",
    "mississippi": "ole miss",
    "central florida": "ucf",
    "texas christian": "tcu",
    "brigham young": "byu",
    "southern methodist": "smu",
    "nevada-las vegas": "unlv",
    "nevada las vegas": "unlv",
    "north carolina state": "nc state",
    "texas a&m": "texas a&m",
    "pennsylvania": "penn",
    "pittsburgh": "pitt",
    "connecticut": "uconn",
    "massachusetts": "umass",
    "southern mississippi": "southern miss",
    "alabama-birmingham": "uab",
    "texas-san antonio": "utsa",
    "texas-el paso": "utep",
    "louisiana-lafayette": "louisiana",
    "louisiana lafayette": "louisiana",
    "ull": "louisiana",
    "louisiana-monroe": "ul monroe",
    "middle tennessee": "middle tennessee",
    "middle tennessee state": "middle tennessee",
    "appalachian state": "app state",
    "florida international": "fiu",
    "miami (ohio)": "miami (oh)",
    "miami ohio": "miami (oh)",
    "miami (oh)": "miami (oh)",
    "north carolina-charlotte": "charlotte",
    "hawaii": "hawai'i",
    "bowling green state": "bowling green",
    "texas state": "texas state",
    "western kentucky": "western kentucky",
    "eastern illinois": "eastern illinois",
    "south florida": "south florida",
    "southern florida": "south florida",
    "cal poly": "cal poly",
    "california": "california",
    "miami": "miami",
    "miami (fla)": "miami",
    "miami (fl)": "miami",
    "miami, o": "miami (oh)",
    "miami, oh": "miami (oh)",
    "minn state-mankato": "minnesota state",
    "minnesota state-mankato": "minnesota state",
    "monmouth, nj": "monmouth",
    "monmouth (nj)": "monmouth",
    "southeast missouri": "southeast missouri state",
    "tiffin university": "tiffin",
    "wayne state (mich)": "wayne state (mi)",
    "west texas a&m": "west texas",
    "wisconsin-platteville": "wisconsin platteville",
    "western state, colo": "western colorado",
    "jackson state university": "jackson state",
}


def _r(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def _norm(s):
    s = html.unescape(s or "").strip().lower()
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)
    return s


def _slug(name):
    s = html.unescape(name or "").strip().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def _round1(x):
    return None if x is None else round(float(x), 1)


def _round2(x):
    return None if x is None else round(float(x), 2)


def _round3(x):
    return None if x is None else round(float(x), 3)


def _round4(x):
    return None if x is None else round(float(x), 4)


def _draft_round(pick):
    try:
        pick = int(float(pick))
    except (TypeError, ValueError):
        return None
    if pick <= 0:
        return None
    return min(7, (pick - 1) // 32 + 1)


def _norm_pos(pos):
    if pos in ("DST", "D/ST", "D-ST"):
        return "DST"
    return pos


# ---------------------------------------------------------------------------
# 1. Opportunity / receiving usage (2018+)
# ---------------------------------------------------------------------------
def receiving_usage(con, year):
    if year < 2018:
        return None
    rostered = {r[0] for r in con.execute(
        "SELECT DISTINCT player_id FROM fact_roster_week WHERE season=?", (year,))}
    if not rostered:
        return None
    yardage = con.execute(
        "SELECT yardage_mode FROM dim_season WHERE season=?", (year,)
    ).fetchone()
    bucket = (yardage[0] if yardage else "FRACTIONAL") == "BUCKET"

    weekly = _r(con, """
        SELECT p.player_id AS pid, p.name, p.position AS pos,
               COALESCE(ps.nfl_team, '') AS nfl,
               n.targets, n.air_yards, n.air_yards_share, n.target_share,
               n.rec_yards, n.receptions, n.carries, n.rush_yards,
               n.rec_tds, n.rush_tds, n.two_pt, n.fumbles_lost
          FROM fact_nfl_week n
          JOIN dim_player p ON p.gsis_id = n.gsis_id
          LEFT JOIN player_season ps
                 ON ps.season = n.season AND ps.player_id = p.player_id
         WHERE n.season = ?""", (year,))

    agg = {}
    for r in weekly:
        pid = r["pid"]
        if pid not in rostered:
            continue
        if r["pos"] not in POS_SKILL:
            continue
        a = agg.setdefault(pid, {
            "pid": pid, "name": r["name"], "pos": r["pos"], "nfl": r["nfl"],
            "tgt": 0.0, "air": 0.0, "recy": 0.0, "rec": 0.0,
            "car": 0.0, "ry": 0.0, "retd": 0.0, "rtd": 0.0,
            "tp": 0.0, "fl": 0.0, "team_tgt": 0.0, "team_air": 0.0,
        })
        tgt = float(r["targets"] or 0)
        air = float(r["air_yards"] or 0)
        recy = float(r["rec_yards"] or 0)
        a["tgt"] += tgt
        a["air"] += air
        a["recy"] += recy
        a["rec"] += float(r["receptions"] or 0)
        a["car"] += float(r["carries"] or 0)
        a["ry"] += float(r["rush_yards"] or 0)
        a["retd"] += float(r["rec_tds"] or 0)
        a["rtd"] += float(r["rush_tds"] or 0)
        a["tp"] += float(r["two_pt"] or 0)
        a["fl"] += float(r["fumbles_lost"] or 0)
        tshare = r["target_share"]
        ashare = r["air_yards_share"]
        if tgt and tshare and float(tshare) > 0:
            a["team_tgt"] += tgt / float(tshare)
        if air and ashare and float(ashare) != 0:
            a["team_air"] += air / float(ashare)

    xtd = {(r["player_id"]): r for r in _r(con, """
        SELECT player_id, actual_td, xtd FROM v_xtd_player_season
         WHERE season=? AND player_id IS NOT NULL""", (year,))}
    # FP is full-season AFFL actual from the same fact_nfl_week rows as xFP.
    # v_player_season_any is ESPN points only for weeks the player was on an
    # AFFL roster, so streamers (Nailor week 16 only) showed 0.0 vs 74 xFP.

    out = []
    for pid, a in agg.items():
        if a["tgt"] < 1 and a["car"] < 1:
            continue
        tgt_share = (a["tgt"] / a["team_tgt"]) if a["team_tgt"] > 0 else (0.0 if a["tgt"] == 0 else None)
        air_share = (a["air"] / a["team_air"]) if a["team_air"] != 0 else (0.0 if a["air"] == 0 else None)
        if tgt_share is None:
            wopr = None
        else:
            wopr = 1.5 * tgt_share + 0.7 * (air_share or 0.0)
        adot = (a["air"] / a["tgt"]) if a["tgt"] > 0 else None
        racr = (a["recy"] / a["air"]) if a["air"] else None
        xs = xtd.get(pid)
        td = xs["actual_td"] if xs else None
        xv = xs["xtd"] if xs else None
        if bucket:
            ypts = int(a["ry"] // 10) + int(a["recy"] // 10)
        else:
            ypts = a["ry"] * 0.1 + a["recy"] * 0.1
        xfp = None if xv is None else round(ypts + 6.0 * xv, 1)
        actual_td = td if td is not None else (a["rtd"] + a["retd"])
        fp = ypts + 6.0 * actual_td + 2.0 * a["tp"] - 2.0 * a["fl"]
        out.append({
            "pid": pid,
            "name": a["name"],
            "pos": a["pos"],
            "nfl": a["nfl"] or None,
            "tgtShare": _round3(tgt_share),
            "airYardsShare": _round3(air_share),
            "wopr": _round3(wopr),
            "adot": _round1(adot),
            "racr": _round2(racr),
            "xfp": xfp,
            "fp": _round1(fp),
            "xtd": _round2(xv),
            "td": _round2(td),
        })
    out.sort(key=lambda r: (-(r["wopr"] or -1), -(r["fp"] or 0)))
    return out


# ---------------------------------------------------------------------------
# 4. Trophies + luck (2014+)
# ---------------------------------------------------------------------------
def _median_weeks(con, year):
    """tid -> (medianW, medianL) from regular-season weekly scores."""
    weeks = defaultdict(list)
    for r in _r(con, """
        SELECT week, team_id, points FROM fact_matchup
         WHERE season=? AND is_playoff=0""", (year,)):
        weeks[r["week"]].append((r["team_id"], r["points"]))
    wins = defaultdict(int)
    losses = defaultdict(int)
    tids = set()
    for sides in weeks.values():
        pts = sorted(p for _, p in sides)
        n = len(pts)
        if n == 0:
            continue
        mid = n // 2
        med = pts[mid] if n % 2 else (pts[mid - 1] + pts[mid]) / 2.0
        for tid, p in sides:
            tids.add(tid)
            if p >= med:
                wins[tid] += 1
            else:
                losses[tid] += 1
    return {t: (wins[t], losses[t]) for t in tids}


def trophies(con, year):
    h2h = con.execute(
        "SELECT team_id FROM dim_team WHERE season=? AND final_rank=1", (year,)
    ).fetchone()
    med = _median_weeks(con, year)
    pf = {r["team_id"]: r["points_for"] for r in _r(con, """
        SELECT team_id, points_for FROM v_standings_regular WHERE season=?""", (year,))}
    median_tid = None
    if med:
        median_tid = max(med, key=lambda t: (med[t][0], pf.get(t) or 0))
    ap = _r(con, """
        SELECT team_id FROM v_power WHERE season=?
         ORDER BY power_ratio DESC, allplay_w DESC, allplay_l ASC""", (year,))
    roto_tid = None
    if year >= 2018:
        rr = con.execute("""
            SELECT team_id FROM fact_roto_team_season
             WHERE season=? AND phase='regular' ORDER BY total_rank""", (year,)).fetchone()
        if rr:
            roto_tid = rr[0]
    return {
        "h2hChampionTid": h2h[0] if h2h else None,
        "medianChampionTid": median_tid,
        "allPlayChampionTid": ap[0]["team_id"] if ap else None,
        "rotoChampionTid": roto_tid,
    }


def luck_card(con, year, lineup_iq=None):
    iq = {}
    for r in lineup_iq or []:
        tid = r.get("teamId") if isinstance(r, dict) else None
        if tid is not None:
            iq[tid] = r.get("eff")
    med = _median_weeks(con, year)
    xtdp = {r["team_id"]: r for r in _r(con, """
        SELECT team_id, actual_td, xtd FROM v_xtd_portfolio WHERE season=?""", (year,))}
    rows = _r(con, """
        SELECT s.team_id AS tid, s.wins AS actualW, s.losses AS actualL,
               s.points_for AS pf, s.games,
               p.allplay_w AS allPlayW, p.allplay_l AS allPlayL,
               p.power_pct AS allPlayPct, p.power_ratio,
               lw.exp_wins AS expectedWins, lw.weighted_luck AS scheduleLuckWins
          FROM v_standings_regular s
          JOIN v_power p ON p.season=s.season AND p.team_id=s.team_id
          JOIN v_luck_weighted lw ON lw.season=s.season AND lw.team_id=s.team_id
         WHERE s.season=?
         ORDER BY s.team_id""", (year,))
    out = []
    for r in rows:
        tid = r["tid"]
        mw, ml = med.get(tid, (None, None))
        xs = xtdp.get(tid)
        out.append({
            "tid": tid,
            "actualW": r["actualW"],
            "actualL": r["actualL"],
            "pf": _round1(r["pf"]),
            "allPlayW": r["allPlayW"],
            "allPlayL": r["allPlayL"],
            "allPlayPct": _round4(r["allPlayPct"]),
            "medianW": mw,
            "medianL": ml,
            "expectedWins": r["expectedWins"],
            "scheduleLuckWins": r["scheduleLuckWins"],
            "xtdFor": _round2(xs["xtd"]) if xs else None,
            "tdFor": _round2(xs["actual_td"]) if xs else None,
            "managementPct": _round4(iq.get(tid)),
        })
    return out


# ---------------------------------------------------------------------------
# 5. Auction DNA (2016–2025 auction; 2014–15 snake = null)
# ---------------------------------------------------------------------------
def auction_dna(con, year):
    auction = con.execute(
        "SELECT auction_draft FROM dim_season WHERE season=?", (year,)
    ).fetchone()
    if not auction or not auction[0]:
        return None
    by = defaultdict(list)
    for r in _r(con, """
        SELECT team_id AS tid, bid FROM fact_draft_pick WHERE season=?""", (year,)):
        by[r["tid"]].append(int(r["bid"] or 0))
    out = []
    for tid, bids in sorted(by.items()):
        bids_desc = sorted(bids, reverse=True)
        top6 = (bids_desc + [0] * 6)[:6]
        rest = sum(bids_desc[6:]) if len(bids_desc) > 6 else 0
        total = sum(bids_desc) or 1
        l1 = sum(abs(a - b) for a, b in zip(top6, CATES))
        out.append({
            "tid": tid,
            "top6Spend": top6,
            "restSpend": rest,
            "top6Share": _round3(sum(top6) / total),
            "catesCurve": list(CATES),
            "l1Distance": l1,
        })
    return out


# ---------------------------------------------------------------------------
# 6. All-League / Bush League (2018+, started=1, one per pos per week)
# ---------------------------------------------------------------------------
def awards(con, year):
    if year < 2018:
        return None
    reg = con.execute(
        "SELECT reg_weeks FROM dim_season WHERE season=?", (year,)
    ).fetchone()
    reg_weeks = reg[0] if reg else 14
    rows = _r(con, """
        SELECT r.week, r.team_id AS tid, r.player_id AS pid,
               p.name, p.position AS pos, r.points
          FROM fact_roster_week r
          JOIN dim_player p ON p.player_id = r.player_id
         WHERE r.season=? AND r.started=1 AND r.week<=?""", (year, reg_weeks))
    if not rows:
        return None
    by = defaultdict(list)
    teams = set()
    for r in rows:
        pos = _norm_pos(r["pos"])
        if pos not in POS_AWARD:
            continue
        teams.add(r["tid"])
        by[(r["week"], pos)].append(r)
    al = defaultdict(list)
    bu = defaultdict(list)
    for cands in by.values():
        cands_top = sorted(cands, key=lambda x: (-(x["points"] or 0), x["pid"]))
        cands_bot = sorted(cands, key=lambda x: ((x["points"] or 0), x["pid"]))
        al[cands_top[0]["tid"]].append(cands_top[0])
        bu[cands_bot[0]["tid"]].append(cands_bot[0])

    def pack(bucket):
        out = []
        for tid in sorted(teams):
            hits = bucket.get(tid) or []
            top_name, top_pts, top_pid = None, None, None
            starts = []
            if hits:
                tally = defaultdict(lambda: [0, 0.0, None, None])
                for h in sorted(hits, key=lambda x: (x["week"], x["pos"] or "", x["pid"])):
                    pos = _norm_pos(h["pos"])
                    starts.append({
                        "wk": h["week"],
                        "pid": h["pid"],
                        "name": h["name"],
                        "pos": pos,
                        "pts": _round1(h["points"] or 0),
                    })
                    t = tally[h["pid"]]
                    t[0] += 1
                    t[1] += h["points"] or 0
                    t[2] = h["name"]
                    t[3] = h["pid"]
                best = max(tally.values(), key=lambda t: (t[0], t[1]))
                top_name, top_pts, top_pid = best[2], _round1(best[1]), best[3]
            out.append({
                "tid": tid,
                "count": len(hits),
                "topPlayer": top_name,
                "topPlayerPid": top_pid,
                "topPlayerPts": top_pts,
                "starts": starts,
            })
        return out

    return {"allLeague": pack(al), "bushLeague": pack(bu)}


# ---------------------------------------------------------------------------
# 7. Week-1 vs acquired (2018+)
# ---------------------------------------------------------------------------
def w1_acquired(con, year):
    if year < 2018:
        return None
    w1 = defaultdict(set)
    for r in _r(con, """
        SELECT team_id, player_id FROM fact_roster_week
         WHERE season=? AND week=1""", (year,)):
        w1[r["team_id"]].add(r["player_id"])
    if not w1:
        return None
    pts = _r(con, """
        SELECT team_id AS tid, player_id AS pid, SUM(points) AS pts
          FROM fact_roster_week WHERE season=?
         GROUP BY team_id, player_id""", (year,))
    by = defaultdict(lambda: [0.0, 0.0])
    for r in pts:
        tid = r["tid"]
        if r["pid"] in w1.get(tid, ()):
            by[tid][0] += r["pts"] or 0
        else:
            by[tid][1] += r["pts"] or 0
    teams = sorted(set(w1) | set(by))
    out = []
    for tid in teams:
        w1pts, acq = by[tid]
        tot = w1pts + acq
        out.append({
            "tid": tid,
            "w1Pts": _round1(w1pts),
            "acquiredPts": _round1(acq),
            "w1Share": _round3(w1pts / tot) if tot else None,
            "acquiredShare": _round3(acq / tot) if tot else None,
        })
    return out


# ---------------------------------------------------------------------------
# 3. RB miles (NFL rush+rec touches, 2014+ on disk)
# ---------------------------------------------------------------------------
def write_miles(con):
    rows = _r(con, """
        SELECT p.player_id AS pid, n.season,
               SUM(COALESCE(n.carries,0) + COALESCE(n.receptions,0)) AS touches
          FROM fact_nfl_week n
          JOIN dim_player p ON p.gsis_id = n.gsis_id
         GROUP BY p.player_id, n.season""")
    by = defaultdict(dict)
    for r in rows:
        by[r["pid"]][int(r["season"])] = int(r["touches"] or 0)
    payload = {}
    for pid, seasons in by.items():
        if not any(seasons.values()):
            continue
        running = 0
        asof = {}
        for y in sorted(seasons):
            running += seasons[y]
            asof[str(y)] = running
        payload[str(pid)] = {
            "pid": pid,
            "nflTouchesBySeason": {str(y): n for y, n in sorted(seasons.items())},
            "careerNflTouchesAsOf": asof,
            "collegeTouches": None,
        }
    json.dump(payload, open(MILES, "w"), separators=(",", ":"))
    print(f"  miles: {len(payload)} players -> site/miles.json")
    return payload


# ---------------------------------------------------------------------------
# 2. College / draft on player_bio + NCAA logos
# ---------------------------------------------------------------------------
def _roster_draft_index():
    """espn_id -> best roster row (draft / college / birth)."""
    best = {}
    for y in range(2014, 2026):
        path = os.path.join(DATA, f"roster_{y}.csv")
        if not os.path.exists(path):
            continue
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                eid = (row.get("espn_id") or "").strip()
                if not eid:
                    continue
                score = (int(bool(row.get("draft_number")))
                         + int(bool(row.get("draft_club")))
                         + int(bool(row.get("college")))
                         + int(bool(row.get("birth_date")))
                         + int(bool(row.get("entry_year"))))
                prev = best.get(eid)
                if prev is None or score > prev[0]:
                    best[eid] = (score, row)
    return {eid: rec for eid, (score, rec) in best.items()}


def _espn_teams():
    req = urllib.request.Request(ESPN_TEAMS, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    teams = []
    for sport in data.get("sports") or []:
        for league in sport.get("leagues") or []:
            for wrap in league.get("teams") or []:
                t = wrap.get("team") or wrap
                logos = t.get("logos") or []
                href = None
                for lg in logos:
                    rel = lg.get("rel") or []
                    if "default" in rel or not href:
                        href = lg.get("href")
                    if "default" in rel and "full" in rel:
                        href = lg.get("href")
                        break
                names = []
                for key in ("location", "shortDisplayName", "nickname",
                            "displayName", "name", "abbreviation"):
                    v = t.get(key)
                    if v:
                        names.append(_norm(v))
                teams.append({"names": names, "href": href, "id": t.get("id"),
                              "location": t.get("location") or t.get("shortDisplayName")})
    return teams


def _college_parts(college):
    raw = html.unescape(college or "").strip()
    if not raw:
        return []
    # nflverse joins transfers with ";"
    parts = [p.strip() for p in raw.replace("|", ";").split(";") if p.strip()]
    return parts or [raw]


def _match_one(name, teams):
    key = _norm(name)
    if not key:
        return None
    alias = COLLEGE_ALIASES.get(key, key)
    alias = _norm(alias)
    for t in teams:
        if key in t["names"] or alias in t["names"]:
            return t
    for t in teams:
        for n in t["names"]:
            if COLLEGE_ALIASES.get(n, n) == alias:
                return t
    return None


def _match_college(college, teams):
    for part in _college_parts(college):
        hit = _match_one(part, teams)
        if hit:
            return hit
    return None


def download_ncaa_logos(con, colleges):
    """Download ESPN default logos for AFFL-roster colleges. Missing stays missing."""
    os.makedirs(NCAA_DIR, exist_ok=True)
    try:
        teams = _espn_teams()
    except Exception as e:
        print(f"  ncaa logos: ESPN list failed ({type(e).__name__}: {e})")
        return {}
    print(f"  ncaa logos: {len(teams)} ESPN teams, {len(colleges)} AFFL colleges")
    matched = {}
    unmatched = []
    for college in sorted(colleges):
        t = _match_college(college, teams)
        if not t or not t.get("href"):
            unmatched.append(college)
            continue
        # slug from the first matching part so transfers share the primary school file
        parts = _college_parts(college)
        slug_src = parts[0]
        for part in parts:
            if _match_one(part, teams):
                slug_src = part
                break
        slug = _slug(slug_src)
        dest = os.path.join(NCAA_DIR, f"{slug}.png")
        if not (os.path.exists(dest) and os.path.getsize(dest) > 200):
            try:
                req = urllib.request.Request(t["href"], headers=UA)
                with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
                    f.write(r.read())
                if os.path.getsize(dest) < 200:
                    os.remove(dest)
                    unmatched.append(college)
                    continue
            except Exception:
                if os.path.exists(dest):
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                unmatched.append(college)
                continue
        matched[college] = f"logos/ncaa/{slug}.png"
    print(f"  ncaa logos: {len(matched)} downloaded/cached, {len(unmatched)} unmatched")
    if unmatched:
        print("    unmatched: " + ", ".join(unmatched[:20])
              + ("…" if len(unmatched) > 20 else ""))
    return matched


def write_player_bio(con):
    bio = {}
    if os.path.exists(BIO):
        bio = json.load(open(BIO))
    roster = _roster_draft_index()

    affl = {r[0] for r in con.execute("SELECT DISTINCT player_id FROM fact_roster_week")}
    affl |= {r[0] for r in con.execute(
        "SELECT DISTINCT player_id FROM fact_draft_pick WHERE player_id IS NOT NULL")}
    colleges = set()
    for pid in affl:
        rec = bio.get(str(pid)) or {}
        row = roster.get(str(pid)) or {}
        col = html.unescape((rec.get("college") or row.get("college") or "")).strip()
        if col:
            colleges.add(col)
    logos = download_ncaa_logos(con, colleges)

    n_draft = 0
    for pid_s, rec in list(bio.items()):
        row = roster.get(pid_s) or {}
        college = html.unescape((rec.get("college") or row.get("college") or "") or "") or None
        if college:
            rec["college"] = college
        pick = row.get("draft_number") or None
        club = (row.get("draft_club") or "").strip() or None
        entry = row.get("entry_year") or row.get("rookie_year") or None
        try:
            pick_i = int(float(pick)) if pick not in (None, "") else None
        except ValueError:
            pick_i = None
        try:
            year_i = int(float(entry)) if entry not in (None, "") and pick_i else None
        except ValueError:
            year_i = None
        rec["collegeLogo"] = logos.get(college) if college else None
        rec["draftYear"] = year_i
        rec["draftRound"] = _draft_round(pick_i) if pick_i else None
        rec["draftPick"] = pick_i
        rec["draftTeam"] = club if pick_i else (club if club else None)
        if not pick_i:
            rec["draftTeam"] = None
        rec["breakoutAge"] = None
        rec["dominator"] = None
        rec["earlyDeclare"] = None
        rec["classYear"] = None
        if pick_i:
            n_draft += 1
        bio[pid_s] = rec

    # players in roster/index but missing from bio
    for eid, row in roster.items():
        if eid in bio:
            continue
        college = html.unescape((row.get("college") or "")).strip() or None
        pick = row.get("draft_number") or None
        try:
            pick_i = int(float(pick)) if pick not in (None, "") else None
        except ValueError:
            pick_i = None
        entry = row.get("entry_year") or row.get("rookie_year")
        try:
            year_i = int(float(entry)) if entry not in (None, "") and pick_i else None
        except ValueError:
            year_i = None
        bio[eid] = {
            "birth": (row.get("birth_date") or None) or None,
            "college": college,
            "ageByYear": {},
            "nflByYear": {},
            "collegeLogo": logos.get(college) if college else None,
            "draftYear": year_i,
            "draftRound": _draft_round(pick_i) if pick_i else None,
            "draftPick": pick_i,
            "draftTeam": (row.get("draft_club") or "").strip() or None if pick_i else None,
            "breakoutAge": None,
            "dominator": None,
            "earlyDeclare": None,
            "classYear": None,
        }
        if pick_i:
            n_draft += 1

    json.dump(bio, open(BIO, "w"), separators=(",", ":"))
    print(f"  player_bio: {len(bio)} players, {n_draft} with draft capital, "
          f"{sum(1 for v in bio.values() if v.get('collegeLogo'))} logos")
    return bio


def patch_year(con, bundle, year):
    """Attach the six year-scoped keys. Mutates bundle."""
    bundle["receivingUsage"] = receiving_usage(con, year)
    bundle["trophies"] = trophies(con, year)
    bundle["luckCard"] = luck_card(con, year, bundle.get("lineupIQ") or [])
    bundle["auctionDna"] = auction_dna(con, year)
    bundle["awards"] = awards(con, year)
    bundle["w1Acquired"] = w1_acquired(con, year)
    return bundle
