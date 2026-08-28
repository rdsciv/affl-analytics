#!/usr/bin/env python3
"""CHI-114 bind: three panes, two grains, FPOE split, no air-yard alias, 2013 skips season, logos capped."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing {path}")
        return ""
    return path.read_text()


def brace_after(src: str, needle: str) -> str:
    i = src.find(needle)
    if i < 0:
        return ""
    j = src.find("{", i)
    if j < 0:
        return ""
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j : k + 1]
    return src[j:]


def main() -> int:
    players_js = read(SITE / "players.js")
    teams_js = read(SITE / "teams.js")
    chi_js = read(SITE / "chi114.js")
    players_html = read(SITE / "players.html")
    teams_html = read(SITE / "teams.html")
    styles = read(SITE / "styles.css")
    js_blob = "\n".join([players_js, teams_js, chi_js])

    # three render functions (season FP/XFP, season FPOE, week)
    for name in ("renderChi114SeasonXfp", "renderChi114SeasonFpoe", "renderChi114WeekNfl"):
        for label, src in (("players.js", players_js), ("teams.js", teams_js), ("chi114.js", chi_js)):
            if name not in src and label != "chi114.js":
                fail(f"{label} missing {name}")
        if "drawSeasonXfp" not in chi_js or "drawWeekNfl" not in chi_js:
            fail("chi114.js missing drawSeasonXfp/drawWeekNfl")
        if "drawSeasonFpoe" not in chi_js:
            fail("chi114.js missing drawSeasonFpoe")

    # three canvases (or svgs) on each page: season, fpoe, week
    for label, html in (("players.html", players_html), ("teams.html", teams_html)):
        canvases = re.findall(r'<canvas[^>]+id="([^"]*chi114[^"]*)"', html)
        svgs = re.findall(r'<svg[^>]+id="([^"]*chi114[^"]*)"', html)
        n = len(canvases) + len(svgs)
        print(f"{label} chi114 canvases={canvases} svgs={len(svgs)}")
        if n < 3:
            fail(f"{label} needs three chi114 canvases/svgs, found {n}")
        ids = " ".join(canvases)
        if "season" not in ids or "week" not in ids or "fpoe" not in ids:
            fail(f"{label} canvases must include season, fpoe, and week grains: {canvases}")

    # landing Compare/WOPR stay landing-only
    if 'id="pl-compare"' not in players_html or 'id="wopr-persist"' not in players_html:
        fail("players.html lost Compare/WOPR landing chrome")
    if 'id="pl-chi114"' not in players_html:
        fail("players.html missing profile chi114 section")
    if 'id="tm-chi114"' not in teams_html:
        fail("teams.html missing franchise chi114 section")

    # playerSeasonXfp used for XFP/FPOE only
    take_s = brace_after(chi_js, "function takeSeasonXfp")
    if "playerSeasonXfp" not in take_s:
        fail("takeSeasonXfp does not read playerSeasonXfp")
    for banned in ("pass_yards", "rush_yards", "targets", "receptions", "rush_td", "pass_td", "rec_td", "week"):
        if re.search(r"\b" + banned + r"\b", take_s):
            fail(f"takeSeasonXfp touches week-grain field {banned}")
    if "xfp" not in take_s or "fpoe" not in take_s:
        fail("takeSeasonXfp must copy xfp and fpoe")

    # playerWeekNfl used for yards/TDs/volume only
    take_w = brace_after(chi_js, "function takeWeekNfl")
    if "playerWeekNfl" not in take_w:
        fail("takeWeekNfl does not read playerWeekNfl")
    for banned in ("xfp", "fpoe", "fp"):
        if re.search(r"\b" + banned + r"\b", take_w):
            fail(f"takeWeekNfl touches season-grain field {banned}")
    for need in ("pass_yards", "rush_yards", "targets", "receptions", "rush_td", "pass_td", "rec_td"):
        if need not in take_w:
            fail(f"takeWeekNfl missing {need}")

    # season FP/XFP draw must not plot week metrics or fpoe as a dataset
    draw_s = brace_after(chi_js, "function drawSeasonXfp")
    if re.search(r"pass_yards|rush_yards|targets|receptions", draw_s):
        fail("drawSeasonXfp plots week-grain metrics")
    if "SEASON_KEYS.map" in draw_s:
        fail("drawSeasonXfp maps SEASON_KEYS (would plot fpoe on FP/XFP)")
    if re.search(r'\["fp",\s*"xfp",\s*"fpoe"\]', draw_s):
        fail("drawSeasonXfp plots fpoe as a dataset")
    # allow reading r.fpoe if unused; fail if fpoe is in the drawn key list
    if re.search(r'XFP_PLOT_KEYS\s*=\s*\[[^\]]*fpoe', draw_s) or re.search(r'keys\s*=\s*\[[^\]]*fpoe', draw_s):
        fail("drawSeasonXfp includes fpoe in plot keys")

    # season FPOE pane: own scale, no week metrics, no fp/xfp series
    if "function drawSeasonFpoe" not in chi_js:
        fail("chi114.js missing function drawSeasonFpoe")
    if "drawSeasonFpoe:" not in chi_js:
        fail("drawSeasonFpoe not exported on window.CHI114")
    draw_f = brace_after(chi_js, "function drawSeasonFpoe")
    if not draw_f:
        fail("could not extract drawSeasonFpoe body")
    if re.search(r"pass_yards|rush_yards|targets|receptions|rush_td|pass_td|rec_td", draw_f):
        fail("drawSeasonFpoe plots week-grain metrics")
    if "SEASON_KEYS.map" in draw_f:
        fail("drawSeasonFpoe maps SEASON_KEYS (would plot fp/xfp)")
    if re.search(r'FPOE_PLOT_KEYS\s*=\s*\[[^\]]*"fp"', draw_f) or re.search(r'\["fp",\s*"xfp"', draw_f):
        fail("drawSeasonFpoe plots fp/xfp as series")
    if "fpoe" not in draw_f.lower() and "FPOE_PLOT_KEYS" not in draw_f:
        fail("drawSeasonFpoe does not plot fpoe")
    if "aggregateSeasonFpoe" not in draw_f:
        fail("drawSeasonFpoe team path must use aggregateSeasonFpoe (mean), not a roster sum")
    if re.search(r'mode === "team" \? aggregateSeason\(rowsIn\)', draw_f):
        fail("drawSeasonFpoe still sums the roster")
    if "Math.min(0" not in draw_f:
        fail("drawSeasonFpoe y-domain must include 0")
    if "function aggregateSeasonFpoe" not in chi_js:
        fail("missing aggregateSeasonFpoe")
    agg_f = brace_after(chi_js, "function aggregateSeasonFpoe")
    if "SKILL_POS" not in chi_js or not all(pos in chi_js for pos in ("QB", "RB", "WR", "TE")):
        fail("team FPOE must filter to rostered skill players")
    if "if (pos && !SKILL_POS" in chi_js:
        fail("missing pos still enters the FPOE mean")
    if "if (!SKILL_POS[pos])" not in chi_js:
        fail("aggregateSeasonFpoe must drop anyone who is not QB/RB/WR/TE")
    if "/ b.n" not in agg_f and "/b.n" not in agg_f and "sum /" not in agg_f:
        fail("aggregateSeasonFpoe is not a mean")

    draw_w = brace_after(chi_js, "function drawWeekNfl")
    if re.search(r"\bxfp\b|\bfpoe\b|\bfp\b", draw_w):
        fail("drawWeekNfl plots season XFP/FPOE/FP")

    # no pass_air_yards alias (forbidding comments are allowed)
    stripped = re.sub(r"/\*.*?\*/", "", js_blob, flags=re.S)
    stripped = re.sub(r"//.*?$", "", stripped, flags=re.M)
    if re.search(r"pass_air_yards|rec_air_yards", stripped):
        fail("JS aliases pass_air_yards/rec_air_yards")
    for y in range(2013, 2026):
        path = SITE / "years" / f"{y}.json"
        if not path.exists():
            fail(f"missing year bundle {path}")
            continue
        bag = json.loads(path.read_text())
        sx = bag.get("playerSeasonXfp")
        wk = bag.get("playerWeekNfl")
        if y == 2013:
            if sx and (sx.get("rows") or []):
                fail("2013 must not ship season XFP rows")
            if not (wk and wk.get("rows")):
                fail("2013 must ship playerWeekNfl rows")
        else:
            if not (sx and sx.get("rows")):
                fail(f"{y} missing playerSeasonXfp.rows")
            if not (wk and wk.get("rows")):
                fail(f"{y} missing playerWeekNfl.rows")
        if sx and sx.get("rows"):
            keys = set(sx["rows"][0])
            if keys != {"season", "player_id", "fp", "xfp", "fpoe"}:
                fail(f"{y} season keys {keys}")
        if wk and wk.get("rows"):
            row = wk["rows"][0]
            if "xfp" in row or "fpoe" in row or "fp" in row:
                fail(f"{y} week row mixed with XFP")
            if "pass_air_yards" in row or "rec_air_yards" in row:
                fail(f"{y} week row has air yards")
            for need in ("pass_yards", "rush_yards", "targets", "receptions", "rush_td", "pass_td", "rec_td"):
                if need not in row:
                    fail(f"{y} week row missing {need}")

    # 2013 skips XFP chart in JS
    if "2013" not in take_s or "skip" not in take_s.lower() and "!== 2013" not in take_s and "=== 2013" not in take_s:
        if "2013" not in chi_js:
            fail("chi114.js has no 2013 skip")
    if "2013" not in chi_js or not re.search(r"2013.*skip|skip.*2013|season !== 2013|=== 2013", chi_js):
        fail("2013 XFP skip not present in chi114.js")

    # logo class has max-width / max-height
    logo_block = re.search(
        r"(\.chi114-logo\s*,?\s*img\.chi114-logo|\.chi114-logo)\s*\{([^}]+)\}",
        styles,
    )
    if not logo_block:
        fail("styles.css missing .chi114-logo rule")
    else:
        body = logo_block.group(0)
        print("logo rule:", re.sub(r"\s+", " ", body)[:220])
        if "max-width" not in body or "max-height" not in body:
            fail(".chi114-logo must set max-width and max-height")
        if "object-fit" not in body or "contain" not in body:
            fail(".chi114-logo must use object-fit: contain")
        mx = re.search(r"max-width:\s*(\d+)px", body)
        my = re.search(r"max-height:\s*(\d+)px", body)
        if mx and int(mx.group(1)) > 28:
            fail(f".chi114-logo max-width {mx.group(1)} > 28")
        if my and int(my.group(1)) > 28:
            fail(f".chi114-logo max-height {my.group(1)} > 28")

    if "chi114.js" not in players_html or "chi114.js" not in teams_html:
        fail("html files must load chi114.js")
    if "players.js?v=39" not in players_html and "players.js?v=38" not in players_html and "players.js?v=37" not in players_html and "players.js?v=36" not in players_html:
        fail("players.js cache bust not bumped")
    if "teams.js?v=22" not in teams_html and "teams.js?v=21" not in teams_html and "teams.js?v=16" not in teams_html:
        fail("teams.js cache bust not bumped to v=22")
    if "chi114.js?v=5" not in players_html or "chi114.js?v=5" not in teams_html:
        fail("chi114.js cache bust not bumped to v=5")

    # 2025 Josh Allen bind
    y25 = json.loads((SITE / "years" / "2025.json").read_text())
    allen = next((r for r in y25["playerSeasonXfp"]["rows"] if r["player_id"] == 3918298), None)
    if not allen:
        fail("2025 Josh Allen missing from playerSeasonXfp")
    else:
        print("Josh Allen 2025", allen)
    weeks = [r for r in y25["playerWeekNfl"]["rows"] if r.get("player_id") == 3918298]
    print(f"Josh Allen 2025 week rows={len(weeks)}")
    if len(weeks) < 8:
        fail(f"Josh Allen 2025 week rows {len(weeks)} < 8")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
