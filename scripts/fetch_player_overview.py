#!/usr/bin/env python3
"""Cache ESPN common/v3 athlete overview for a small AFFL starter set.

Writes site/player_overview.json. ESPN is hit here only — never from the browser.
Same ESPN athlete ids already stored (Hurts 4040715). Honest empty fields.
Does not replace nflverse weekly stats / NGS or 2014-17 benches.
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
OUT = os.path.join(SITE, "player_overview.json")
DATA_OUT = os.path.join(ROOT, "data", "player_overview.json")

UA = {
    "User-Agent": "AFFL-player-overview/1.0 (+local cache; not a browser)",
    "Accept": "application/json",
}
OVERVIEW = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{id}/overview"
ATHLETE = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{id}"
FANTASY_NEWS = "https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId={id}"
HEADSHOT = "https://a.espncdn.com/i/headshots/nfl/players/full/{id}.png"

HURTS = "4040715"
# Only rostered skill player with empty nflverse headshot_url (2022). Fallback demo.
HUNTLEY = "4244732"
SKILL = ("QB", "RB", "WR", "TE")
MIN_PLAYERS = 8
MAX_PLAYERS = 15
NEWS_CAP = 6


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


def pick_ids(year_bundle):
    players = year_bundle.get("players") or []
    by_pid = {str(p.get("pid")): p for p in players if p.get("pid") is not None}
    skill = [
        p for p in players
        if str(p.get("pos") or "") in SKILL and (p.get("starts") or 0) >= 8
    ]
    skill.sort(key=lambda p: (-(p.get("starts") or 0), -(p.get("tot") or 0), p.get("name") or ""))
    out = []
    seen = set()

    def add(pid, name="", pos=""):
        pid = str(pid)
        if pid in seen or not pid.lstrip("-").isdigit():
            return
        if pid.startswith("-"):
            return
        p = by_pid.get(pid) or {}
        out.append({
            "pid": pid,
            "name": p.get("name") or name or "",
            "pos": p.get("pos") or pos or "",
        })
        seen.add(pid)

    add(HURTS, "Jalen Hurts", "QB")
    for p in skill:
        if len(out) >= MAX_PLAYERS - 1:
            break
        add(p.get("pid"), p.get("name") or "", p.get("pos") or "")
    add(HUNTLEY, "Caleb Huntley", "RB")
    if len(out) < MIN_PLAYERS:
        rest = [p for p in players if str(p.get("pos") or "") in SKILL]
        rest.sort(key=lambda p: (-(p.get("starts") or 0), p.get("name") or ""))
        for p in rest:
            if len(out) >= MIN_PLAYERS:
                break
            add(p.get("pid"), p.get("name") or "", p.get("pos") or "")
    return out[:MAX_PLAYERS]


def parse_next_game(block):
    if not isinstance(block, dict) or not block:
        return None
    league = block.get("league") or {}
    events = league.get("events") or []
    ev = events[0] if events else {}
    if not ev and not block.get("displayName"):
        return None
    name = ev.get("name") or ""
    short = ev.get("shortName") or ""
    if not name and not short:
        return None
    return {
        "displayName": block.get("displayName") or "",
        "name": name,
        "shortName": short,
        "date": ev.get("date") or "",
        "weekText": ev.get("weekText") or "",
        "status": ev.get("status") or "",
        "location": ev.get("location") or "",
    }


def parse_news(items):
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        headline = (item.get("headline") or item.get("linkText") or "").strip()
        if not headline:
            continue
        published = item.get("published") or item.get("lastModified") or ""
        out.append({"headline": headline, "published": published})
        if len(out) >= NEWS_CAP:
            break
    return out


def parse_fantasy_news(data):
    feed = data.get("feed") if isinstance(data, dict) else None
    if feed is None and isinstance(data, list):
        feed = data
    items = []
    for item in feed or []:
        if not isinstance(item, dict):
            continue
        headline = (item.get("headline") or item.get("title") or "").strip()
        if not headline:
            continue
        published = item.get("published") or item.get("lastModified") or ""
        items.append({"headline": headline, "published": published})
    return items


def parse_college(athlete):
    if not isinstance(athlete, dict):
        return ""
    col = athlete.get("college")
    if isinstance(col, dict):
        return (col.get("name") or col.get("shortName") or "").strip()
    if isinstance(col, str):
        return col.strip()
    team = athlete.get("collegeTeam")
    if isinstance(team, dict):
        return (team.get("shortDisplayName") or team.get("location") or "").strip()
    return ""


def parse_draft(athlete):
    if not isinstance(athlete, dict):
        return ""
    return (athlete.get("displayDraft") or "").strip()


def parse_rotowire(block):
    if not isinstance(block, dict) or not block:
        return ""
    return (block.get("headline") or block.get("description") or "").strip()


def empty_rec(name):
    return {
        "name": name or "",
        "college": "",
        "draft": "",
        "nextGame": None,
        "news": [],
        "headshotFallback": "",
        "rotowire": "",
    }


def fetch_one(pid, fallback_name=""):
    rec = empty_rec(fallback_name)
    rec["headshotFallback"] = HEADSHOT.format(id=pid)

    data, code = get_json(OVERVIEW.format(id=pid))
    if code == 200 and isinstance(data, dict):
        rec["nextGame"] = parse_next_game(data.get("nextGame"))
        rec["news"] = parse_news(data.get("news"))
        rec["rotowire"] = parse_rotowire(data.get("rotowire"))

    athlete_data, acode = get_json(ATHLETE.format(id=pid))
    athlete = (athlete_data or {}).get("athlete") if isinstance(athlete_data, dict) else None
    if acode == 200 and isinstance(athlete, dict):
        rec["name"] = athlete.get("displayName") or athlete.get("fullName") or rec["name"]
        rec["college"] = parse_college(athlete)
        rec["draft"] = parse_draft(athlete)
        hs = athlete.get("headshot") or {}
        href = hs.get("href") if isinstance(hs, dict) else ""
        if href:
            rec["headshotFallback"] = href

    if not rec["news"]:
        fdata, fcode = get_json(FANTASY_NEWS.format(id=pid))
        if fcode == 200 and fdata:
            rec["news"] = parse_news(parse_fantasy_news(fdata) or (fdata.get("news") if isinstance(fdata, dict) else None))

    if not rec["name"]:
        rec["name"] = fallback_name
    return rec, code, acode


def main():
    year_bundle = json.load(open(YEAR_PATH))
    chosen = pick_ids(year_bundle)
    if not chosen:
        raise SystemExit("no 2025 AFFL starters found")
    cache = {}
    for i, c in enumerate(chosen):
        pid = str(c["pid"])
        rec, ocode, acode = fetch_one(pid, c["name"])
        cache[pid] = rec
        ng = rec.get("nextGame") or {}
        news0 = (rec.get("news") or [{}])[0].get("headline", "") if rec.get("news") else ""
        print(
            f"  {pid} {rec['name']} overview={ocode} athlete={acode} "
            f"college={rec['college']!r} draft={rec['draft']!r} "
            f"next={ng.get('shortName') or ''} news0={news0[:60]!r}"
        )
        if i + 1 < len(chosen):
            time.sleep(0.25)
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    json.dump(cache, open(OUT, "w"), indent=2, sort_keys=True)
    json.dump(cache, open(DATA_OUT, "w"), indent=2, sort_keys=True)
    print(f"wrote {OUT} ({len(cache)} players)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
