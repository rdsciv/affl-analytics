#!/usr/bin/env python3
"""CHI-66 / AFFL-043: Season Wrapped — that year only, PAR adds, kept draft, trade grades."""
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
PREVIEW = ROOT / "preview"
fails = []
fail = lambda m: fails.append(m)

NAV_PAGES = [
    "index.html", "scoreboard.html", "players.html", "draft.html",
    "trades.html", "roto.html", "teams.html", "history.html", "awards.html",
    "dictionary.html", "wrapped.html",
]
FG_ONLY = (
    "Bob Loblaw", "FantasyGenius", "FG League", "other league",
    "Kupp My Beer", "Mahomes Alone", "Josh Allen's Army",
)
CARD_TITLES = ("Champion", "Sacko", "PF King", "Luck", "Best Add", "Worst Draft", "Worst Trade", "Best Trade")


def nav_block(html):
    m = re.search(r'<nav class="site-nav">(.*?)</nav>', html, re.S)
    return m.group(1) if m else ""


def after_start(player, tid, after_wk):
    pts = starts = 0
    for row in player.get("wk") or []:
        if not row:
            continue
        week, fp, started, own = row[0], row[1] or 0, int(row[2] or 0), row[3]
        if week > after_wk and own == tid and started:
            pts += fp
            starts += 1
    return pts, starts


def grade_adds(yd):
    players = {p["pid"]: p for p in (yd.get("players") or []) if p.get("pid") is not None}
    bases = {b["position"]: b["baseline"] for b in ((yd.get("draftValue") or {}).get("baselines") or []) if b.get("baseline") is not None}
    drafted = {p["pid"] for p in players.values() if p.get("draft") and p["draft"].get("teamId") is not None}
    first = {}
    for m in yd.get("moves") or []:
        if m.get("type") not in ("WAIVER", "FREEAGENT"):
            continue
        for g in m.get("add") or []:
            if g.get("pid") is None or m.get("wk") is None:
                continue
            k = (g["pid"], m["tid"])
            if k not in first or m["wk"] < first[k]["wk"]:
                first[k] = {"pid": g["pid"], "tid": m["tid"], "wk": m["wk"]}
    for p in players.values():
        if p["pid"] in drafted or p.get("mainTeam") is None:
            continue
        k = (p["pid"], p["mainTeam"])
        if k not in first:
            first[k] = {"pid": p["pid"], "tid": p["mainTeam"], "wk": 0}
    rows = []
    for a in first.values():
        p = players.get(a["pid"])
        if not p:
            continue
        base = bases.get(p.get("pos"))
        if base is None:
            continue
        pts, starts = after_start(p, a["tid"], a["wk"])
        rows.append({
            "name": p["name"], "pos": p.get("pos"), "tid": a["tid"],
            "stPts": pts, "par": pts - base, "starts": starts, "pid": p["pid"],
        })
    rows.sort(key=lambda r: (-r["par"], -r["stPts"]))
    return rows


def kept_busts(yd):
    busts = list(((yd.get("draftValue") or {}).get("busts")) or [])
    traded = set()
    for tr in yd.get("trades") or []:
        for s in tr.get("sides") or []:
            for g in s.get("got") or []:
                if g.get("pid") is not None and g.get("from") is not None:
                    traded.add((g["pid"], g["from"]))
    return [b for b in busts if (b.get("pid"), b.get("tid") if b.get("tid") is not None else b.get("teamId")) not in traded]


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    champ = con.execute(
        "SELECT name, wins, losses, points_for FROM dim_team WHERE season=2025 AND final_rank=1"
    ).fetchone()
    power = list(con.execute(
        "SELECT team_id, allplay_w, allplay_l, power_rank FROM v_power WHERE season=2025 ORDER BY power_rank"
    ))
    luck = list(con.execute(
        "SELECT team_id, net_luck FROM v_luck WHERE season=2025 ORDER BY net_luck DESC"
    ))
    notables = list(con.execute(
        "SELECT kind, week, winner_pts, loser_pts FROM v_notable_matchup WHERE season=2025"
    ))
    if not champ:
        fail("no 2025 champion")
    if len(power) != 12:
        fail("power missing")
    if len(notables) < 6:
        fail("notables missing")
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=2025"
    )}
    PREVIEW.mkdir(exist_ok=True)
    lines = [
        "# 2025 Wrapped (season events only)", "",
        "CHI-66 / AFFL-043. Season chip = that year. Adds ranked by PAR. Trades graded after the deal week.",
        "", "## Champion", "",
        f"**{champ['name']}** {champ['wins']}-{champ['losses']} · {champ['points_for']:.2f} PF",
        "", "## Power (raw all-play)", "",
        "| rank | team | all-play |", "| --- | --- | --- |",
    ]
    for r in power:
        lines.append(f"| {r['power_rank']} | {names[r['team_id']]} | {r['allplay_w']}-{r['allplay_l']} |")
    lines += ["", "## Luck Index (v_luck)", "", "| team | net |", "| --- | --- |"]
    for r in luck:
        lines.append(f"| {names[r['team_id']]} | {r['net_luck']} |")
    lines += ["", "## Notables", "", "| kind | week | w_pts | l_pts |", "| --- | --- | --- | --- |"]
    for r in notables:
        lines.append(f"| {r['kind']} | {r['week']} | {r['winner_pts']} | {r['loser_pts']} |")
    lines += ["", "```", "python3 evals/test_wrapped_metrics.py", "```", ""]
    (PREVIEW / "WRAPPED.md").write_text("\n".join(lines))
    print(PREVIEW / "WRAPPED.md")

    html_path = SITE / "wrapped.html"
    js_path = SITE / "wrapped.js"
    css = (SITE / "styles.css").read_text()
    if not html_path.exists():
        fail("site/wrapped.html missing")
    if not js_path.exists():
        fail("site/wrapped.js missing")
    html = html_path.read_text() if html_path.exists() else ""
    js = js_path.read_text() if js_path.exists() else ""

    if 'id="year-picker"' not in html:
        fail("wrapped.html missing year-picker")
    if 'id="wrap-cards"' not in html:
        fail("wrapped.html missing wrap-cards")
    if 'id="wrap-trades-card"' not in html:
        fail("wrapped.html missing trade-grades list")
    if "wrapped.js" not in html:
        fail("wrapped.html does not load wrapped.js")
    if not re.search(r'<a[^>]+href="wrapped.html"[^>]*class="on"', html):
        fail("wrapped.html nav Wrapped link missing class=on")

    for page in NAV_PAGES:
        text = (SITE / page).read_text()
        nav = nav_block(text)
        if "wrapped.html" not in nav and "Wrapped" not in nav:
            fail(f"{page} nav missing Wrapped")
        for label in ("Dashboard", "Scoreboard", "Players", "Draft", "Trades", "Roto", "Teams", "History"):
            if label not in nav:
                fail(f"{page} nav lost {label}")

    for title in CARD_TITLES:
        if title not in js:
            fail(f"wrapped.js missing card title {title}")
    if "Most Titles" in js:
        fail("wrapped.js still has career Most Titles on season Wrapped")
    if "career · current franchise" in js:
        fail("wrapped.js still has career franchise chip on season view")
    for key in ("luckFG", "draftValue", "notables", "power", "franchiseName", "gradeAdds", "gradeTrades", "keptBusts"):
        if key not in js:
            fail(f"wrapped.js missing data key {key}")
    if ".wrap-" not in css:
        fail("styles.css missing .wrap- classes")
    if ".wrap-trade-bad" not in css:
        fail("styles.css missing .wrap-trade-bad")

    blob = html + "\n" + js
    for bad in FG_ONLY:
        if bad in blob:
            fail(f"FG-only name leaked: {bad}")

    data = json.loads((SITE / "data.json").read_text())
    y2025 = json.loads((SITE / "years" / "2025.json").read_text())
    preview = (PREVIEW / "WRAPPED.md").read_text()
    season = (data.get("seasons") or {}).get("2025") or {}
    teams = season.get("teams") or []
    champ_team = next((t for t in teams if t.get("finalRank") == 1), None)
    if not champ_team:
        fail("data.json 2025 champion missing")
    else:
        if champ["name"] not in preview:
            fail("WRAPPED.md missing warehouse champion name")
        if f"{champ['points_for']:.2f}" not in preview:
            fail("WRAPPED.md missing champion PF")
        if abs((champ_team.get("pf") or 0) - champ["points_for"]) > 0.02:
            fail(f"data.json champ PF {champ_team.get('pf')} != warehouse {champ['points_for']}")

    luck_js = y2025.get("luckFG") or []
    if not luck_js:
        fail("years/2025.json missing luckFG")
    else:
        top_net = max(r.get("net") or 0 for r in luck_js)
        if str(int(top_net)) not in preview and str(top_net) not in preview:
            fail("WRAPPED.md missing luck net from years JSON")

    notes_js = {r.get("kind"): r for r in (y2025.get("notables") or [])}
    for r in notables:
        rec = notes_js.get(r["kind"])
        if not rec:
            fail(f"years/2025.json missing notable {r['kind']}")
            continue
        if rec.get("week") != r["week"]:
            fail(f"notable {r['kind']} week {rec.get('week')} != warehouse {r['week']}")
        if abs(float(rec.get("winnerPts") or 0) - float(r["winner_pts"])) > 0.05:
            fail(f"notable {r['kind']} pts mismatch")

    # Best Add is PAR, not raw starter points
    if "adds[0].stPts" in js and "gradeAdds" not in js:
        fail("Best Add still reads raw waiver[0].stPts")
    if re.search(r"card\(\"Best Add\".*stPts", js) and "PAR" not in js.split('card("Best Add"')[1][:400]:
        fail("Best Add card does not show PAR")
    if "b.par - a.par" not in js and "(b.par - a.par)" not in js:
        fail("gradeAdds is not sorted by PAR")

    adds = grade_adds(y2025)
    if not adds:
        fail("no 2025 add grades")
    else:
        winner = adds[0]
        print(f"Best Add by PAR: {winner['name']} {winner['pos']} PAR={winner['par']:.1f} stPts={winner['stPts']:.1f}")
        jones = next((r for r in adds if r["name"] == "Daniel Jones"), None)
        if jones:
            print(f"Daniel Jones PAR={jones['par']:.1f} stPts={jones['stPts']:.1f}")
            raw_top = max(adds, key=lambda r: r["stPts"])
            if winner["name"] == "Daniel Jones" and jones["par"] < 0:
                fail("Best Add is Daniel Jones on negative PAR — raw QB points won")
            if jones["par"] + 0.05 < winner["par"] and winner["name"] == "Daniel Jones":
                fail("Daniel Jones is not the PAR leader but won Best Add")
            if winner["name"] == "Daniel Jones" and raw_top["name"] == "Daniel Jones" and jones["par"] <= 0:
                fail("Best Add justified by QB raw points alone")
            if winner["par"] < jones["par"] - 0.05:
                fail(f"Best Add {winner['name']} PAR {winner['par']} < Jones {jones['par']}")
        waiver = y2025.get("waiver") or []
        if waiver and waiver[0].get("name") == "Daniel Jones":
            if winner["name"] == "Daniel Jones" and (jones and jones["par"] <= 0):
                fail("Best Add still the raw-stPts waiver[0] QB")
        if winner["pos"] in ("QB", "K") and winner["par"] <= 0:
            fail(f"Best Add {winner['name']} {winner['pos']} has near-zero/negative PAR {winner['par']}")

    # Worst Draft must be a kept draftee, not traded Burrow
    busts = kept_busts(y2025)
    raw_busts = ((y2025.get("draftValue") or {}).get("busts")) or []
    if raw_busts and raw_busts[0].get("name") == "Joe Burrow":
        if busts and busts[0].get("name") == "Joe Burrow":
            fail("Joe Burrow still Worst Draft after he was traded")
        if "keptBusts" not in js:
            fail("wrapped.js does not filter traded draftees from Worst Draft")
    if busts:
        print(f"Worst Draft kept: {busts[0].get('name')} PAR={busts[0].get('par')}")
        if busts[0].get("name") == "Joe Burrow":
            fail("Worst Draft is traded Burrow")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/wrapped.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"wrapped.html HTTP {code}")
        else:
            print("wrapped.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-66: season Wrapped, PAR Best Add, kept Worst Draft, trade grades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
