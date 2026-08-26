#!/usr/bin/env python3
"""Matchup Scores by Season: regular-season team-game high / avg / low."""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

YEARS = list(range(2014, 2026))
PLAYOFF_TIER = ("BRACKET", "PLAYOFF", "CONSOLATION")


def regular_weeks(yd):
    raw = yd.get("regWeeks")
    if isinstance(raw, list) and raw:
        return {int(w) for w in raw}
    if isinstance(raw, (int, float)) and raw > 0:
        return set(range(1, int(raw) + 1))
    return set()


def side_score(side):
    if not side:
        return None
    pts = side.get("pts")
    if pts is None or pts == "":
        return None
    try:
        n = float(pts)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def is_regular_matchup(week, matchup, reg):
    if int(week) not in reg:
        return False
    tier = matchup.get("tier") or "NONE"
    if tier != "NONE" and any(tok in str(tier).upper() for tok in PLAYOFF_TIER):
        return False
    return True


def season_stats(year, yd):
    scores = []
    reg = regular_weeks(yd)
    weeks = yd.get("weeks") or {}
    for wk, matchups in weeks.items():
        for m in matchups or []:
            if not is_regular_matchup(wk, m, reg):
                continue
            for side in (m.get("home"), m.get("away")):
                pts = side_score(side)
                if pts is not None:
                    scores.append(pts)
    if not scores:
        return None
    avg = sum(scores) / len(scores)
    high = max(scores)
    low = min(scores)
    return {
        "year": year,
        "n": len(scores),
        "avg": avg,
        "high": high,
        "low": low,
        "spread": high - low,
    }


def main():
    html = (SITE / "history.html").read_text()
    js_path = SITE / "score-trend.js"
    if "Matchup Scores by Season" not in html:
        fail("page missing “Matchup Scores by Season”")
    if "regular-season team games · high / average / low" not in html:
        fail("page missing score-trend subtitle")
    if 'id="score-trend-card"' not in html:
        fail("history.html missing score-trend-card")
    if "score-trend.js" not in html:
        fail("history.html missing score-trend.js script")
    if "chart.umd.min.js" not in html:
        fail("history.html missing chart.umd.min.js")
    if not js_path.exists():
        fail("site/score-trend.js missing")
    else:
        js = js_path.read_text()
        for needle in ("regWeeks", "High game", "seasonSides", "pts"):
            if needle not in js:
                fail(f"score-trend.js missing {needle}")

    # Do not clobber other History work
    for keep in ("Transaction Counter", "Waiver Report"):
        if keep not in html:
            fail(f"history.html lost {keep}")

    rows = {}
    for year in YEARS:
        path = SITE / "years" / f"{year}.json"
        if not path.exists():
            fail(f"missing years/{year}.json")
            continue
        yd = json.loads(path.read_text())
        row = season_stats(year, yd)
        if row is None:
            fail(f"{year}: no completed regular-season team games")
            continue
        rows[year] = row
        for key in ("avg", "high", "low", "n"):
            val = row[key]
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                fail(f"{year} {key} not finite: {val}")
        if row["n"] <= 0:
            fail(f"{year} n games <= 0")
        if not (row["high"] >= row["avg"] >= row["low"]):
            fail(
                f"{year} expected high >= avg >= low, "
                f"got {row['high']} >= {row['avg']} >= {row['low']}"
            )
        print(
            f"{year} n={row['n']} avg={row['avg']:.4f} "
            f"high={row['high']:.1f} low={row['low']:.1f} "
            f"spread={row['spread']:.1f}"
        )

    r2014 = rows.get(2014)
    if r2014:
        if not (50 < r2014["avg"] < 200):
            fail(f"2014 avg {r2014['avg']} not in (50, 200)")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
