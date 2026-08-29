#!/usr/bin/env python3
"""CHI-147 review gate: History All-Play career, Players QB default, Trades v=9 lock."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def career_allplay(data: dict, owner: str) -> tuple[int, int]:
    w = l = 0
    for ys, season in (data.get("seasons") or {}).items():
        year = int(ys)
        if year < 2014 or year > 2025:
            continue
        for t in season.get("teams") or []:
            if t.get("owner") == owner:
                w += int(t.get("allplayW") or 0)
                l += int(t.get("allplayL") or 0)
    return w, l


def main() -> int:
    hist_js = (SITE / "history.js").read_text()
    hist_html = (SITE / "history.html").read_text()
    players_js = (SITE / "players.js").read_text()
    players_html = (SITE / "players.html").read_text()
    trades_js = (SITE / "trades.js").read_text()
    trades_html = (SITE / "trades.html").read_text()
    data = json.loads((SITE / "data.json").read_text())
    act = json.loads((SITE / "activity.json").read_text())

    # --- CHI-120 History All-Play ---
    if "careerStandRows" not in hist_js:
        fail("history.js missing careerStandRows")
    if "pickedYear == null ? careerStandRows()" not in hist_js:
        fail("All does not bind careerStandRows")
    if "pickedYear == null ? careerStandRows() : seasonStandRows" not in hist_js:
        fail("year selected is not season-only")
    if "career All-Play 2014–2025" not in hist_js and "career All-Play 2014-2025" not in hist_js:
        fail("All subtitle is not career 2014–2025")
    if "parseSeasonParam" not in hist_js:
        fail("parseSeasonParam missing")
    if 'String(raw).toLowerCase() === "all"' not in hist_js:
        fail("All is not exclusive of a year")
    if re.search(r'id="year-picker"[^>]*></div>', hist_html) or 'class="week-picker" id="year-picker"' in hist_html:
        fail("year-picker is still chips — All+year can both paint on")
    if '<select class="team-select" id="year-picker"' not in hist_html:
        fail("year-picker must be a single select")
    if not re.search(r'<option[^>]*value="all"[^>]*>All</option>', hist_html):
        fail("Season select missing All")
    yp = re.search(r'<select class="team-select" id="year-picker"[^>]*>([\s\S]*?)</select>', hist_html)
    if not yp:
        fail("year-picker select body missing")
    else:
        opts = re.findall(r'<option[^>]*value="([^"]+)"', yp.group(1))
        if not opts or opts[0] != "all" or opts[1:] != [str(y) for y in range(2014, 2026)]:
            fail(f"year-picker options {opts} — want All then 2014-2025 exclusive")
        if not re.search(r'<option[^>]*value="all"[^>]*selected', yp.group(1)):
            fail("Season select default is not All")
    feel_w, feel_l = career_allplay(data, "m18")
    if (feel_w, feel_l) != (954, 727):
        fail(f"Feelers career All-Play {feel_w}-{feel_l} — expected 954-727")
    y2025 = None
    for t in (data.get("seasons") or {}).get("2025", {}).get("teams") or []:
        if t.get("owner") == "m18":
            y2025 = (int(t.get("allplayW") or 0), int(t.get("allplayL") or 0))
    if y2025 == (954, 727):
        fail("2025 season All-Play equals career — binder or payload is collapsed")
    if y2025 != (93, 61):
        fail(f"2025 Feelers All-Play {y2025} — expected 93-61")

    # --- CHI-138 Players default ---
    if 'pos: "QB"' not in players_js:
        fail("PP.pos default is not QB")
    if re.search(r"const PP = \{[^}]*pos: \"ALL\"", players_js):
        fail("PP still defaults pos ALL")
    if 'sort: "tot"' not in players_js:
        fail("PP.sort default is not career AFFL pts (tot)")
    if 'id="pp-sort"' not in players_html:
        fail("players.html missing #pp-sort")
    bust = re.search(r"players\.js\?v=(\d+)", players_html)
    if not bust:
        fail("players.html missing players.js cache bust")
    elif int(bust.group(1)) < 43:
        fail(f"players.js cache still v={bust.group(1)} (need v=43)")
    if "paintDbChips" not in players_js:
        fail("paintDbChips missing")
    sorts = re.search(r"const DB_SORTS = \[([\s\S]*?)\];", players_js)
    if not sorts:
        fail("DB_SORTS missing")
    else:
        body = sorts.group(1).lower()
        if "success" in body:
            fail("success rate invented in DB_SORTS")
        if "ypc" in body:
            fail("YPC invented in DB_SORTS")
        if "ppr" in body:
            fail("PPR invented in DB_SORTS")
    if 'key: "tot"' not in players_js:
        fail("DB_SORTS missing tot")

    # --- CHI-145 / CHI-112 Trades lock ---
    bust = re.search(r"trades\.js\?v=(\d+)", trades_html)
    if not bust:
        fail("trades.html missing trades.js cache bust")
    elif int(bust.group(1)) < 9:
        fail(f"trades.js cache still v={bust.group(1)} (need v=9)")
    cum = (act.get("cumulative") or {})
    managers = cum.get("managers") or {}
    if len(managers) != 16:
        fail(f"Activity Y-axis managers {len(managers)} — expected 16 named")
    m18 = managers.get("m18") or {}
    m04 = managers.get("m04") or {}
    if m18.get("tradesProposed") != 2079:
        fail(f"Feelers proposed {m18.get('tradesProposed')} — expected 2079")
    if m18.get("tradesAccepted") != 37:
        fail(f"Feelers accepted {m18.get('tradesAccepted')} — expected 37")
    denom = (m18.get("tradesAccepted") or 0) + (m18.get("tradesDeclined") or 0) + (m18.get("tradesVetoed") or 0)
    rate = round(100 * (m18.get("tradesAccepted") or 0) / denom) if denom else None
    if rate != 3:
        fail(f"Feelers accept rate {rate}% — expected 3%")
    if m04.get("tradesProposed") != 20:
        fail(f"Chewbacca proposed {m04.get('tradesProposed')} — expected 20")
    if (m04.get("tradesAccepted") or 0) != 0 or (m04.get("tradesDeclined") or 0) != 0 or (m04.get("tradesVetoed") or 0) != 0:
        fail("Chewbacca rate must stay unavailable (denom 0)")
    if "xProposed" not in trades_js:
        fail("trades.js missing dual axis xProposed")
    if 'id="activity-rates"' not in trades_html:
        fail("trades.html missing rates table")
    if "Player N" in trades_js or "Player N" in hist_js:
        fail("Player N invented")
    if re.search(r"year\s*<\s*2018[^;\n]*\b0\b", trades_js):
        fail("2014–17 painted as 0")
    for y in ("2014", "2015", "2016", "2017"):
        rec = (act.get("years") or {}).get(y) or {}
        if rec.get("available") is True:
            fail(f"{y} marked available")
        if rec.get("managers"):
            fail(f"{y} has manager zeros")
    if "PPR" in trades_js and "non-PPR" not in players_js:
        fail("PPR leaked")

    # --- Gabagooners career book: no empty 0-0-0 on History ---
    if "function inCareerBook" not in hist_js:
        fail("history.js missing inCareerBook")
    cr = re.search(r"function careerRows\(\) \{([\s\S]*?)\n  \}", hist_js)
    if not cr or "inCareerBook" not in cr.group(1):
        fail("History franchise records still include no-career Gabagooners")
    h2h = re.search(r"function renderH2H\(\) \{([\s\S]*?)\n  \}", hist_js)
    if not h2h or "inCareerBook" not in h2h.group(1):
        fail("History H2H still includes Gabagooners")
    if "inCareerBook(r.owner)" not in hist_js:
        fail("History All-Play still allows a 0-0-0 m22 row")
    if "if (!by[oid]) return" not in hist_js:
        fail("rollFranchises still seeds empty Gabagooners")
    if 'id === "m22"' not in hist_js:
        fail("inCareerBook does not drop m22")
    gaba = next((f for f in (data.get("franchises") or []) if f.get("owner") == "m22"), None)
    if gaba and ((gaba.get("years") or []) or (gaba.get("seasons") or 0)):
        fail("Gabagooners have 2014-2025 seasons")
    for ys, season in (data.get("seasons") or {}).items():
        if any(t.get("owner") == "m22" for t in (season.get("teams") or [])):
            fail(f"Gabagooners appear in season {ys}")
    if 2026 in {int(y) for y in (data.get("seasons") or {})}:
        fail("AFFL 2026 season invented in data.json")
    bust = re.search(r"history\.js\?v=(\d+)", hist_html)
    if not bust or int(bust.group(1)) < 24:
        fail("history.js cache not bumped to v=24")


    # --- CHI-147 Players: exclusive Expected/Weekly chips, no empty overview ---
    chi_js = (SITE / "chi114.js").read_text()
    chips_fn = re.search(r"function chips\(el, values, selected, onPick, allLabel\) \{([\s\S]*?)\n  \}", chi_js)
    if not chips_fn:
        fail("chi114.js missing chips()")
    else:
        body = chips_fn.group(1)
        if 'sel.has(v) ? " on"' in body and "!allOn && sel.has(v)" not in body:
            fail("Expected/Weekly chips still class-on every selected year under All")
        if "!allOn && sel.has(v)" not in body:
            fail("chi114 chips() does not keep year buttons off when All is on")
        if "sel.size > 1" in body and "sel.delete" in body:
            fail("chi114 chips() is still multi-select (All+year can both be on)")
        if "sel.clear()" not in body:
            fail("chi114 chips() click is not exclusive")
    if "yearsAvail.length ? [yearsAvail[yearsAvail.length - 1]]" in chi_js:
        fail("week grain still defaults to latest year instead of All")
    if 'label: allOn ? "All"' not in chi_js:
        fail("CHI-114 All grain still badges the latest year")
    if "Number(r.y) === Number(latestY)" in players_js:
        fail("Weekly Fantasy Production still fakes latest year under All")
    if 'hide("#pl-overview", !profile)' in players_js:
        fail("setPageMode still unhides empty #pl-overview")
    if re.search(r'<section[^>]*id="pl-overview"', players_html):
        fail("#pl-overview is still a stub in players.html")
    if 'id="player-year-row"' in players_html:
        fail("Players still has page-level #player-year-row chips")
    if 'id="player-year-picker"' not in players_html:
        fail("Weekly Fantasy Production missing chart-local #player-year-picker")
    if "!allOn && y === logYear" not in players_js:
        fail("Weekly Fantasy year chips are not exclusive of All")
    if 'yrLabel = y === "all" ? "career"' not in players_js:
        fail("hero badge is not career when All")
    if "Player N" in players_js or "Player N" in players_html:
        fail("Player N invented on Players")

    # --- card franchise: full A.franchiseName, never chopped ---
    if ".slice(0, 16)" in players_js:
        fail("card franchise still slices to 16 chars")
    if "function cardFranchise" not in players_js:
        fail("cardFranchise helper missing")
    if "function cardOwner" not in players_js:
        fail("cardOwner helper missing")
    cf = re.search(r"function cardFranchise\(p\) \{([\s\S]*?)\n  \}", players_js)
    if not cf or "A.franchiseName" not in cf.group(1):
        fail("cardFranchise does not use A.franchiseName")
    if 'return name || "unavailable"' not in players_js:
        fail("missing AFFL home is not unavailable")
    rg = re.search(r"function renderGrid\(\) \{([\s\S]*?)\n  \}", players_js)
    if not rg:
        fail("renderGrid missing")
    else:
        body = rg.group(1)
        if "cardFranchise(p)" not in body:
            fail("renderGrid does not call cardFranchise")
        if "pp-fran" not in body or "title=" not in body:
            fail("card franchise missing title=full name")
        if ".slice(0, 16)" in body or "tName(p.mainTeam, year)" in body:
            fail("renderGrid still uses sliced tName")
    styles = (SITE / "styles.css").read_text()
    if "text-overflow: ellipsis" not in styles.split(".pp-sub")[1][:200]:
        fail(".pp-sub is not CSS-ellipsis")
    chopped = ["Grand Teeton Fee", "Tijuana Sanchito", "Westeros Warlord", "Poulsbo Pollywog", "Squaw Valley Ski"]
    # visible franchise text = .pp-fran inner, not a raw HTML substring of the full name
    for raw in re.findall(r'class="pp-fran"[^>]*>([^<]*)</span>', players_js):
        if raw in chopped:
            fail(f"players.js card template hardcodes chopped franchise {raw}")

    if "chi114.js?v=6" not in players_html:
        fail("players.html chi114.js cache not v=6")

    app_js = (SITE / "app.js").read_text()
    teams_js = (SITE / "teams.js").read_text()
    for label, src in (("app.js", app_js), ("history.js", hist_js), ("teams.js", teams_js), ("trades.js", trades_js)):
        if "slice(0, 16)" in src or "slice(0, 15)" in src or "slice(0, 17)" in src:
            fail(f"{label} still prefix-chops franchise names")
    index_html = (SITE / "index.html").read_text()
    bust = re.search(r"app\.js\?v=(\d+)", index_html)
    if not bust or int(bust.group(1)) < 24:
        fail(f"app.js cache {bust.group(1) if bust else None} — need v=24")
    bust = re.search(r"history\.js\?v=(\d+)", hist_html)
    if not bust or int(bust.group(1)) < 25:
        fail(f"history.js cache {bust.group(1) if bust else None} — need v=25")
    bust = re.search(r"teams\.js\?v=(\d+)", (SITE / "teams.html").read_text())
    if not bust or int(bust.group(1)) < 25:
        fail(f"teams.js cache {bust.group(1) if bust else None} — need v=25")
    bust = re.search(r"trades\.js\?v=(\d+)", trades_html)
    if not bust or int(bust.group(1)) < 15:
        fail(f"trades.js cache {bust.group(1) if bust else None} — need v=15")

    import subprocess
    sim = Path(__file__).resolve().parent / "chi147_chip_sim.mjs"
    if not sim.is_file():
        fail("missing evals/chi147_chip_sim.mjs")
    else:
        try:
            out = subprocess.check_output(["node", str(sim)], timeout=10, text=True)
            if "chip-sim-ok" not in out:
                fail("exclusive chip sim did not confirm")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            fail(f"exclusive chip sim failed: {e}")

    # --- CHI-147 Age All is pick a season, not 2025 live ---
    fn = re.search(r"function ageScatterSeason\(\) \{([\s\S]*?)\n  \}", hist_js)
    if not fn:
        fail("ageScatterSeason missing")
    else:
        body = fn.group(1)
        if "getFullYear" in body:
            fail("ageScatterSeason All path still falls through to getFullYear")
        if re.search(r"return 2025|y > 2025", body):
            fail("ageScatterSeason still clamps All to 2025")
        if "return null" not in body:
            fail("ageScatterSeason does not return null when All")
    if "live roster age" in hist_js:
        fail("history.js still uses live roster age")
    if "live roster age" in hist_html:
        fail("history.html still uses live roster age")
    sub_m = re.search(r'id="age-scatter-sub">([^<]*)</div>', hist_html)
    if not sub_m or sub_m.group(1).strip() != "All · pick a season":
        fail(f"HTML default #age-scatter-sub is {sub_m.group(1) if sub_m else None} — want All · pick a season")
    if '"All · pick a season"' not in hist_js and "'All · pick a season'" not in hist_js:
        fail("renderAgeScatter All subtitle is not All · pick a season")
    ra = re.search(r"function renderAgeScatter\(\) \{([\s\S]*?)\n  function ", hist_js)
    if not ra:
        fail("renderAgeScatter missing")
    else:
        body = ra.group(1)
        pick = body.find("All · pick a season")
        rows = body.find("seasonAgeRows")
        if pick < 0:
            fail("renderAgeScatter missing All · pick a season")
        if rows >= 0 and pick > rows:
            fail("renderAgeScatter calls seasonAgeRows before All early-return")
        if "live roster age" in body:
            fail("renderAgeScatter still paints live roster age")
        if "Youngest team" not in hist_js or "Oldest team" not in hist_js:
            fail("Youngest team / Oldest team chips missing")
        if "new Date(+scatterYear, 11, 31)" not in body and "new Date(+scatterYear, 11, 31)" not in hist_js:
            fail("year path does not bind asOf to Dec 31 of that season")


    # --- CHI-147 All: Race matches Age stub; year-only cards collapse ---
    if 'id="race-wrap"' not in hist_html:
        fail("history.html missing #race-wrap")
    if "function hideRaceCanvas" not in hist_js:
        fail("history.js missing hideRaceCanvas")
    if "function syncYearOnlyCards" not in hist_js:
        fail("history.js missing syncYearOnlyCards")
    rr = re.search(r"function renderRace\(\) \{([\s\S]*?)\n  let ngsKey", hist_js)
    if not rr:
        fail("renderRace missing")
    else:
        body = rr.group(1)
        if "pickedYear == null" not in body:
            fail("renderRace All path does not key off pickedYear == null")
        if "All · pick a season" not in body:
            fail("renderRace All subtitle is not All · pick a season")
        if "hideRaceCanvas" not in body:
            fail("renderRace All path does not hide/destroy THE RACE canvas")
        if "showRaceCanvas" not in body:
            fail("renderRace year path does not restore THE RACE canvas")
        pick = body.find("pickedYear == null")
        chart = body.find("new Chart")
        if pick < 0 or (chart >= 0 and pick > chart):
            fail("renderRace builds a Chart before the All early-return")
    hide = re.search(r"function hideRaceCanvas\(\) \{([\s\S]*?)\n  \}", hist_js)
    if not hide:
        fail("cannot parse hideRaceCanvas")
    else:
        hb = hide.group(1)
        if "wrap.hidden = true" not in hb and "hidden = true" not in hb:
            fail("hideRaceCanvas does not set wrap hidden")
        if 'display = "none"' not in hb and "display = 'none'" not in hb:
            fail("hideRaceCanvas does not display:none the wrap/canvas")
        if "raceChart.destroy" not in hb:
            fail("hideRaceCanvas does not destroy the Race Chart")
        if "height = \"0\"" not in hb and "height = '0'" not in hb:
            fail("hideRaceCanvas does not collapse wrap/canvas height")
    sync = re.search(r"function setYearOnlyOpen\(open\) \{([\s\S]*?)\n  \}", hist_js)
    if not sync:
        fail("setYearOnlyOpen missing")
    else:
        sb = sync.group(1)
        if "el.hidden = !open" not in sb:
            fail("setYearOnlyOpen does not hide year-only section cards")
    blocks = re.search(r"const YEAR_ONLY_BLOCKS = \[([^\]]+)\]", hist_js)
    if not blocks:
        fail("YEAR_ONLY_BLOCKS missing")
    else:
        ids = blocks.group(1)
        for need in ("custody-par-block", "txn-block", "tx-log-block", "waiver-value-block", "waiver-block"):
            if need not in ids:
                fail(f"YEAR_ONLY_BLOCKS missing {need}")
        if "age-scatter-block" in ids:
            fail("Age card must not collapse on All")
        if "race-block" in ids:
            fail("THE RACE card must stay as a compact stub on All")
    if "syncYearOnlyCards();" not in hist_js:
        fail("syncYearOnlyCards is never called")
    if 'id="age-scatter-block"' not in hist_html:
        fail("Age card missing")
    age_fn = re.search(r"function renderAgeScatter\(\) \{([\s\S]*?)\n  function ", hist_js)
    if age_fn and "el.style.display = open ? \"\" : \"none\"" in age_fn.group(1):
        fail("Age render was restyled")
    if "live roster age" in hist_js or "live roster age" in hist_html:
        fail("live roster age leaked")

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print(f"CHI-147: Feelers All-Play {feel_w}-{feel_l}; Players QB/tot; Feelers trades 2079/37/3%; Chewbacca 20/unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
