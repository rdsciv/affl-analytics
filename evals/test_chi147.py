#!/usr/bin/env python3
"""CHI-147 review gate: History All-Play career, Players QB default, Trades v=9 lock."""
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
    elif int(bust.group(1)) < 40:
        fail(f"players.js cache still v={bust.group(1)} (need v=40)")
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
    if not bust or int(bust.group(1)) < 22:
        fail("history.js cache not bumped to v>=22")

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
