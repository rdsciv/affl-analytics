#!/usr/bin/env python3
"""Cache NCAAF career lines for 2025 AFFL rookies / first-year players.

Writes site/college_stats.json. ESPN is hit here only — never from the browser.
collegeAthlete.id == NFL player id. No invented college mapping.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
YEAR_PATH = os.path.join(SITE, "years", "2025.json")
BIO_PATH = os.path.join(SITE, "player_bio.json")
OUT = os.path.join(SITE, "college_stats.json")

UA = {
    "User-Agent": "AFFL-college-stats/1.0 (+local cache; not a browser)",
    "Accept": "application/json",
}
STATS = "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{id}/stats"
OVERVIEW = "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{id}/overview"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/athletes/{id}"
PUBLIC = "https://www.espn.com/college-football/player/_/id/{id}"

JEANTY = "4890973"
MAX_ROOKIES = 9
SKILL = ("QB", "RB", "WR", "TE")
POS_CAT = {"QB": "passing", "RB": "rushing", "WR": "receiving", "TE": "receiving", "K": "kicking"}


def get_json(url, timeout=30):
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


def clean_num(v):
    if v is None:
        return ""
    s = str(v).replace(",", "").strip()
    return s


def idx_of(labels, *names):
    up = [str(x).upper() for x in labels]
    for n in names:
        if n.upper() in up:
            return up.index(n.upper())
    return None


def line_from_category(cat):
    labels = cat.get("labels") or []
    totals = [clean_num(x) for x in (cat.get("totals") or [])]
    name = (cat.get("name") or "").lower()
    if name in ("rushing", "receiving"):
        a = idx_of(labels, "CAR", "REC")
        y = idx_of(labels, "YDS")
        t = idx_of(labels, "TD")
        parts = []
        for i in (a, y, t):
            if i is not None and i < len(totals) and totals[i] != "":
                parts.append(totals[i])
        return "-".join(parts)
    if name == "passing":
        c = idx_of(labels, "CMP", "COMP")
        a = idx_of(labels, "ATT")
        y = idx_of(labels, "YDS")
        t = idx_of(labels, "TD")
        parts = []
        for i in (c, a, y, t):
            if i is not None and i < len(totals) and totals[i] != "":
                parts.append(totals[i])
        return "-".join(parts)
    if name == "kicking":
        fg = idx_of(labels, "FGM", "FG")
        fga = idx_of(labels, "FGA")
        xp = idx_of(labels, "XPM", "XP", "PAT")
        bits = []
        if fg is not None and fga is not None and fg < len(totals) and fga < len(totals):
            bits.append(f"{totals[fg]}/{totals[fga]} FG")
        if xp is not None and xp < len(totals) and totals[xp] != "":
            bits.append(f"{totals[xp]} XP")
        return " · ".join(bits)
    return ""


def years_from_categories(categories):
    years = set()
    for cat in categories or []:
        for row in cat.get("statistics") or []:
            season = row.get("season") or {}
            y = season.get("year")
            if y is None and isinstance(season, dict):
                y = season.get("displayName")
            try:
                years.add(int(y))
            except (TypeError, ValueError):
                pass
    return sorted(years)


def college_from_stats(data, fallback=""):
    teams = data.get("teams") or {}
    names = []
    seen = set()
    for slug, t in teams.items():
        loc = (t.get("location") or t.get("displayName") or t.get("shortDisplayName") or "").strip()
        if loc and loc not in seen:
            seen.add(loc)
            names.append(loc)
    if names:
        return " / ".join(names)
    return fallback


def parse_stats_payload(data, pos, fallback_college=""):
    categories = data.get("categories") or []
    if not categories:
        return [], "", fallback_college
    want = POS_CAT.get(pos, "")
    chosen = None
    if want:
        for cat in categories:
            if (cat.get("name") or "").lower() == want and cat.get("totals"):
                chosen = cat
                break
    if chosen is None:
        for cat in categories:
            n = (cat.get("name") or "").lower()
            if n in ("passing", "rushing", "receiving", "kicking") and cat.get("totals"):
                chosen = cat
                break
    line = line_from_category(chosen) if chosen else ""
    years = years_from_categories(categories)
    college = college_from_stats(data, fallback_college)
    return years, line, college


def parse_overview_payload(data, pos, fallback_college=""):
    """Overview career splits: yearly rows, no totals — sum the primary cols."""
    block = data.get("statistics") or {}
    cats = block.get("categories") or []
    labels = block.get("labels") or []
    splits = block.get("splits") or []
    if not splits:
        return [], "", fallback_college
    want = POS_CAT.get(pos, "rushing")
    offset = 0
    count = 0
    hit = None
    for cat in cats:
        n = (cat.get("name") or "").lower()
        c = int(cat.get("count") or 0)
        if n == want:
            hit = (offset, c, n)
            break
        offset += c
    if hit is None:
        offset, count, name = 0, min(5, len(labels)), (cats[0].get("name") if cats else "")
    else:
        offset, count, name = hit
    years = []
    acc = [0] * count
    have = [False] * count
    for split in splits:
        try:
            years.append(int(str(split.get("displayName") or "").split()[0]))
        except (TypeError, ValueError):
            pass
        stats = split.get("stats") or []
        for i in range(count):
            j = offset + i
            if j >= len(stats):
                continue
            raw = clean_num(stats[j])
            if raw == "":
                continue
            try:
                acc[i] += float(raw)
                have[i] = True
            except ValueError:
                pass
    fake = {
        "name": name,
        "labels": labels[offset:offset + count],
        "totals": [str(int(acc[i]) if have[i] and acc[i] == int(acc[i]) else acc[i]) if have[i] else ""
                   for i in range(count)],
    }
    return sorted(set(years)), line_from_category(fake), fallback_college


def fetch_one(pid, pos, fallback_college=""):
    """Use NFL id as college athlete id. Do not invent a different id."""
    url = STATS.format(id=pid)
    data, code = get_json(url)
    if code == 200 and data:
        years, line, college = parse_stats_payload(data, pos, fallback_college)
        if line or years:
            return years, line, college, url
    if code in (403, 404, 0):
        data, ocode = get_json(OVERVIEW.format(id=pid))
        if ocode == 200 and data:
            years, line, college = parse_overview_payload(data, pos, fallback_college)
            if line or years:
                return years, line, college, OVERVIEW.format(id=pid)
        data, ccode = get_json(CORE.format(id=pid))
        if ccode == 200 and data:
            # core athlete card has no career line — honest empty with source
            return [], "", fallback_college, CORE.format(id=pid)
        data, pcode = get_json(PUBLIC.format(id=pid))
        if pcode == 200:
            return [], "", fallback_college, PUBLIC.format(id=pid)
    return [], "", fallback_college, ""


def empty_rec(name, college):
    return {"name": name, "college": college or "", "years": [], "line": "", "source": ""}


def first_college(raw):
    if not raw:
        return ""
    return str(raw).replace("|", ";").split(";")[0].strip()


def nfl_season_count(bio):
    nfl = bio.get("nflByYear") or {}
    return len(nfl)


def pick_rookies(year_bundle, bio):
    players = year_bundle.get("players") or []
    by_pid = {str(p.get("pid")): p for p in players if p.get("pid") is not None}
    cands = []
    for pid, p in by_pid.items():
        rec = bio.get(pid) or {}
        nfl_n = nfl_season_count(rec)
        if nfl_n >= 3:
            continue
        dy = rec.get("draftYear")
        affl_years = sorted(int(y) for y in (rec.get("ageByYear") or rec.get("nflByYear") or {}) if str(y).isdigit())
        first_affl = (not affl_years) or (min(affl_years) >= 2025 and len(affl_years) <= 2)
        rookie = dy == 2025
        if not (rookie or (first_affl and nfl_n <= 1)):
            continue
        if not rookie and nfl_n > 1:
            continue
        pick = rec.get("draftPick")
        try:
            pick_i = int(pick) if pick not in (None, "") else 999
        except (TypeError, ValueError):
            pick_i = 999
        cands.append({
            "pid": pid,
            "name": p.get("name") or "",
            "pos": p.get("pos") or "",
            "college": first_college(rec.get("college") or ""),
            "draftPick": pick_i,
            "draftYear": dy,
        })
    # Jeanty first if present, then skill by draft capital
    out = []
    seen = set()
    if JEANTY in by_pid:
        hit = next((c for c in cands if c["pid"] == JEANTY), None)
        if hit:
            out.append(hit)
            seen.add(JEANTY)
        else:
            rec = bio.get(JEANTY) or {}
            p = by_pid[JEANTY]
            if nfl_season_count(rec) < 3:
                out.append({
                    "pid": JEANTY,
                    "name": p.get("name") or "Ashton Jeanty",
                    "pos": p.get("pos") or "RB",
                    "college": first_college(rec.get("college") or "Boise State"),
                    "draftPick": rec.get("draftPick") or 6,
                    "draftYear": rec.get("draftYear"),
                })
                seen.add(JEANTY)
    skill = [c for c in cands if c["pid"] not in seen and c["pos"] in SKILL]
    skill.sort(key=lambda c: (c["draftPick"], c["pos"], c["name"]))
    for c in skill:
        if len(out) >= MAX_ROOKIES:
            break
        out.append(c)
        seen.add(c["pid"])
    if len(out) < 5:
        rest = [c for c in cands if c["pid"] not in seen]
        rest.sort(key=lambda c: (c["draftPick"], c["pos"], c["name"]))
        for c in rest:
            if len(out) >= MAX_ROOKIES:
                break
            out.append(c)
    return out


def main():
    year_bundle = json.load(open(YEAR_PATH))
    bio = json.load(open(BIO_PATH))
    rookies = pick_rookies(year_bundle, bio)
    if not rookies:
        raise SystemExit("no 2025 AFFL rookies / first-year players found")
    cache = {}
    for i, c in enumerate(rookies):
        pid = str(c["pid"])
        years, line, college, source = fetch_one(pid, c["pos"], c["college"])
        rec = {
            "name": c["name"],
            "college": college or c["college"] or "",
            "years": years,
            "line": line,
            "source": source,
        }
        if not line and not years:
            rec = empty_rec(c["name"], college or c["college"])
            rec["source"] = source
        cache[pid] = rec
        print(f"  {pid} {c['name']} {c['pos']} college={rec['college']!r} years={rec['years']} line={rec['line']!r}")
        if i + 1 < len(rookies):
            time.sleep(0.25)
    json.dump(cache, open(OUT, "w"), indent=2, sort_keys=True)
    json.dump(cache, open(os.path.join(ROOT, "data", "college_stats.json"), "w"), indent=2, sort_keys=True)
    print(f"wrote {OUT} ({len(cache)} rookies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
