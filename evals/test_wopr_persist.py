#!/usr/bin/env python3
"""Players landing: year-N WOPR vs year-N+1 AFFL Fantasy Points Per Game.

Gates:
- card exists on the list/landing (not only the open player card)
- uses wopr and next-year AFFL points / NFL games, not PPR, not AFFL starts
- Tre Tucker 2025 cannot appear as FPpG >= 40
- max FPpG in the 2024→2025 pair is in a sane per-game range
- JS divides by games and drops the point when games are missing
- no Tittsburgh
- Jefferson 4262921 or Adams 16800 appear in the 2024→2025 pool
  if those pids are in the year JSON
"""
import json
import math
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

JEFFERSON = 4262921
ADAMS = 16800
TUCKER = 4428718
KNOWN = (JEFFERSON, ADAMS)


def num(v):
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def first_num(row, keys):
    if not row:
        return None
    for k in keys:
        if row.get(k) is not None:
            n = num(row.get(k))
            if n is not None:
                return n
    return None


def year_n_sample_ok(row):
    games = first_num(row, ("games", "g", "gp"))
    targets = first_num(row, ("targets", "tgt"))
    if games is not None or targets is not None:
        return (games is not None and games >= 8) or (targets is not None and targets >= 30)
    return num(row.get("fp")) is not None


def nfl_games(nfl, pid, year):
    rec = ((nfl.get(str(pid)) or {}).get(str(year))) or {}
    if not isinstance(rec, dict):
        return None
    n = sum(1 for k in rec if str(k).isdigit() and int(k) > 0)
    return n if n > 0 else None


def next_affl_fppg(next_row, next_player, year, nfl):
    fp = num(next_row.get("fp") if next_row else None)
    if fp is None:
        return None
    games = first_num(next_row, ("games", "g", "gp"))
    if not (games and games > 0):
        games = first_num(next_player, ("games", "g", "gp"))
    if not (games and games > 0):
        pid = None
        if next_row and next_row.get("pid") is not None:
            pid = int(next_row["pid"])
        elif next_player and next_player.get("pid") is not None:
            pid = int(next_player["pid"])
        games = nfl_games(nfl, pid, year) if pid is not None else None
    if not (games and games > 0):
        return None
    return fp / games


def by_pid(rows):
    out = {}
    for r in rows or []:
        if r and r.get("pid") is not None:
            out[int(r["pid"])] = r
    return out


def persist_points(yd_n, yd_n1, nfl):
    u0 = by_pid(yd_n.get("receivingUsage"))
    u1 = by_pid(yd_n1.get("receivingUsage"))
    p1 = by_pid(yd_n1.get("players"))
    next_year = yd_n1.get("year")
    out = []
    for pid, row in u0.items():
        pos = str(row.get("pos") or "").upper()
        if pos not in ("WR", "TE"):
            continue
        wopr = num(row.get("wopr"))
        if wopr is None:
            continue
        nxt = u1.get(pid)
        if not nxt:
            continue
        if not year_n_sample_ok(row):
            continue
        if num(row.get("fp")) is None or num(nxt.get("fp")) is None:
            continue
        fppg = next_affl_fppg(nxt, p1.get(pid), next_year, nfl)
        if fppg is None:
            continue
        out.append({
            "pid": pid,
            "name": row.get("name") or nxt.get("name"),
            "pos": pos,
            "wopr": wopr,
            "fppg": fppg,
            "fp": num(nxt.get("fp")),
        })
    return out


def r_squared(pts):
    n = len(pts)
    if n < 2:
        return None
    xs = [p["wopr"] for p in pts]
    ys = [p["fppg"] for p in pts]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    return r * r


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()
    css = (SITE / "styles.css").read_text()
    y24 = json.loads((SITE / "years/2024.json").read_text())
    y25 = json.loads((SITE / "years/2025.json").read_text())
    nfl = json.loads((SITE / "nfl_weeks.json").read_text())

    if "Usage that sticks" not in html:
        fail("players.html missing Usage that sticks card")
    if 'id="wopr-persist"' not in html:
        fail("players.html missing #wopr-persist")
    if 'id="wopr-persist-chart"' not in html:
        fail("players.html missing #wopr-persist-chart")
    if 'id="wopr-persist-sub"' not in html:
        fail("players.html missing #wopr-persist-sub")
    if 'id="pp-search"' not in html or 'id="pp-grid"' not in html:
        fail("player search/grid was removed")
    if html.find('id="wopr-persist"') > html.find('id="pp-grid"'):
        fail("persist card is not on the list/landing (it sits after the grid)")

    if "function woprPersistPoints" not in js:
        fail("players.js missing woprPersistPoints")
    if "function woprNextAfflFppg" not in js:
        fail("players.js missing woprNextAfflFppg")
    if "function woprNflGames" not in js:
        fail("players.js missing woprNflGames")
    if "function woprR2" not in js:
        fail("players.js missing woprR2 (R² must be computed in JS from plotted points)")
    if "row.wopr" not in js and "woprNum(row.wopr)" not in js:
        fail("players.js does not read year-N wopr")
    persist_fn = js.split("function woprPersistPoints", 1)[-1].split("function woprR2", 1)[0]
    fppg_fn = js.split("function woprNextAfflFppg", 1)[-1].split("function woprPersistPairs", 1)[0]
    games_fn = js.split("function woprNflGames", 1)[-1].split("function woprNextAfflFppg", 1)[0]
    if "wopr" not in persist_fn:
        fail("woprPersistPoints does not use wopr")
    if "nxt.fp" not in persist_fn and "nextRow.fp" not in fppg_fn and "nextRow && nextRow.fp" not in fppg_fn:
        fail("persist scatter does not use next-year AFFL fp")
    if "ppr" in persist_fn.lower() or "ppr" in fppg_fn.lower():
        fail("persist scatter mentions PPR")
    if "pwopr" in js.lower() or "koalaty" in js.lower() or "pff" in persist_fn.lower():
        fail("fake Koalaty/PFF PWOPR leaked into players.js")
    if "Tittsburgh" in js or "Tittsburgh" in html:
        fail("Tittsburgh appears on the players page")
    if "memberName" in persist_fn or "firstName" in persist_fn:
        fail("persist scatter uses owner first names")
    if "starts" in fppg_fn or "starts" in games_fn:
        fail("woprNextAfflFppg still divides season fp by AFFL starts")
    if "fp / games" not in fppg_fn and "fp/games" not in fppg_fn:
        fail("woprNextAfflFppg does not divide fp by games")
    if "return null" not in fppg_fn:
        fail("woprNextAfflFppg does not drop the point when games are missing")
    if "y: fppg" not in persist_fn and "y:fppg" not in persist_fn:
        fail("woprPersistPoints does not plot fppg as y")
    if re.search(r"y:\s*(nxt\.fp|nextRow\.fp|fp)\b", persist_fn):
        fail("woprPersistPoints still plots raw fp as y")
    if "Fantasy Points Per Game" not in js:
        fail("axis/copy does not spell out Fantasy Points Per Game")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html did not cache-bust players.js")
    elif int(bust.group(1)) < 26:
        fail(f"players.js cache still v={bust.group(1)}")
    css_bust = re.search(r"styles\.css\?v=(\d+)", html)
    if not css_bust:
        fail("players.html did not cache-bust styles.css")
    elif int(css_bust.group(1)) < 21:
        fail(f"styles.css cache still v={css_bust.group(1)}")
    if "#wopr-persist" not in css:
        fail("styles.css missing #wopr-persist rules")

    u24 = {int(r["pid"]): r for r in (y24.get("receivingUsage") or []) if r.get("pid") is not None}
    u25 = {int(r["pid"]): r for r in (y25.get("receivingUsage") or []) if r.get("pid") is not None}
    present = [pid for pid in KNOWN if pid in u24 and pid in u25]
    pts = persist_points(y24, y25, nfl)
    r2 = r_squared(pts)
    print(f"2024→2025 n={len(pts)} R²={None if r2 is None else round(r2, 6)}")
    if present:
        pool_ids = {p["pid"] for p in pts}
        hit = [pid for pid in present if pid in pool_ids]
        names = {JEFFERSON: "Jefferson", ADAMS: "Adams"}
        if not hit:
            fail("2024→2025 pool missing known WR "
                 + ", ".join(f"{names[p]} {p}" for p in present)
                 + " even though year JSON has them")
        else:
            for p in pts:
                if p["pid"] in hit:
                    print(f"  {p['name']} pid={p['pid']} wopr={p['wopr']} "
                          f"fppg={p['fppg']:.2f}")
    else:
        print("known WRs not in both year JSONs; pool membership skipped")

    tucker_usage = u25.get(TUCKER)
    tucker_pt = next((p for p in pts if p["pid"] == TUCKER), None)
    if tucker_usage:
        fp = num(tucker_usage.get("fp"))
        games = nfl_games(nfl, TUCKER, 2025)
        print(f"Tre Tucker 2025 fp={fp} nfl_games={games} "
              f"fppg={None if fp is None or not games else round(fp / games, 4)}")
        if tucker_pt is None:
            fail("Tre Tucker missing from 2024→2025 persist pool")
        else:
            if tucker_pt["fppg"] >= 40:
                fail(f"Tre Tucker FPpG is {tucker_pt['fppg']:.2f} (>= 40); season total plotted as per-game")
            if fp is not None and games:
                expect = fp / games
                if abs(tucker_pt["fppg"] - expect) > 1e-6:
                    fail(f"Tre Tucker FPpG {tucker_pt['fppg']} != fp/games {expect}")
            if games and tucker_pt["fppg"] > 15:
                fail(f"Tre Tucker FPpG {tucker_pt['fppg']:.2f} still not a real per-game")

    if pts:
        mx = max(p["fppg"] for p in pts)
        print(f"2024→2025 max FPpG={mx:.2f}")
        if mx >= 30:
            fail(f"max FPpG {mx:.2f} is not a sane per-game range")
        for p in pts:
            if p["fp"] is not None and abs(p["fppg"] - p["fp"]) < 1e-9 and p["fp"] >= 40:
                fail(f"{p['name']} y equals raw season fp {p['fp']}")

    for p in pts:
        if p["wopr"] is None or p["fppg"] is None:
            fail(f"plotted point missing wopr/fppg: {p}")
        if p["pos"] not in ("WR", "TE"):
            fail(f"non WR/TE in pool: {p}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        body = r.read().decode("utf-8", "replace")
        if code != 200:
            fail(f"players.html HTTP {code}")
        elif "Usage that sticks" not in body:
            fail("8765 players.html missing Usage that sticks")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
