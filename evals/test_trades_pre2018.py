#!/usr/bin/env python3
"""2014-17 Front Office lock: unavailable, never a counted zero.

Fail if year 2014/2015 completed-trades or wire-moves render as 0.
Fail if 2014 grid still shows 2018-2025 counts.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails: list[str] = []

ACC_LABEL = re.compile(r"label:\s*(missing \? ['\"]—['\"] : String\(accepted\))")
WIRE_LABEL = re.compile(r"label:\s*(missing \? ['\"]—['\"] : fmt\(wire\))")


def fail(msg: str) -> None:
    fails.append(msg)


def grab_fn(src: str, name: str) -> str:
    m = re.search(rf"function {re.escape(name)}\s*\(", src)
    if not m:
        return ""
    brace = src.find("{", m.start())
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start() : i + 1]
    return ""


def eval_labels(js: str) -> None:
    kpi = grab_fn(js, "renderKPIs")
    acc = ACC_LABEL.search(kpi or "")
    wire = WIRE_LABEL.search(kpi or "")
    if not acc:
        fail("cannot extract completed-trades label expression")
        return
    if not wire:
        fail("cannot extract wire-moves label expression")
        return
    import subprocess
    script = (
        "const fmt = (n) => String(n);\n"
        f"const accExpr = () => {{ const missing = true; const accepted = 0; return {acc.group(1)}; }};\n"
        f"const wireExpr = () => {{ const missing = true; const wire = 0; return {wire.group(1)}; }};\n"
        f"const acc0 = () => {{ const missing = false; const accepted = 0; return {acc.group(1)}; }};\n"
        "const completed = accExpr(); const wire_label = wireExpr(); const real0 = acc0();\n"
        "console.log(JSON.stringify({completed, wire_label, real0}));\n"
    )
    try:
        out = subprocess.check_output(["node", "-e", script], timeout=5, text=True)
        bag = json.loads(out.strip())
    except Exception as e:
        fail(f"label eval failed: {e}")
        return
    completed = bag.get("completed")
    wire_label = bag.get("wire_label")
    real0 = bag.get("real0")
    if completed in (0, "0"):
        fail(f"2014/2015 completed-trades render as {completed!r} — must be unavailable, never 0")
    if wire_label in (0, "0"):
        fail(f"2014/2015 wire-moves render as {wire_label!r} — must be unavailable, never 0")
    if completed not in ("—", "unavailable"):
        fail(f"2014/2015 completed-trades label {completed!r} — want em-dash/unavailable")
    if wire_label not in ("—", "unavailable"):
        fail(f"2014/2015 wire-moves label {wire_label!r} — want em-dash/unavailable")
    if real0 != "0":
        fail(f"available-season 0 trades unexpectedly {real0!r}")


def eval_grid(js: str) -> None:
    grid = grab_fn(js, "renderTradeGrid")
    if not grid:
        fail("renderTradeGrid missing")
        return
    if "txUnavailable" not in grid and "year <= 2017" not in grid:
        fail("2014 grid is not gated unavailable")
    if "ALL.filter" not in grid:
        fail("season grid does not filter to the selected year")
    if re.search(r"GRID = buildTradeGrid\(ALL\)", grid) and "const src" not in grid:
        fail("2014 grid still builds the all-time 2018-2025 book")
    if "2018–2025" in grid:
        if 'scope === "cum"' not in grid and "scope === 'cum'" not in grid:
            fail("2014 grid still shows 2018-2025 counts (subtitle not All-only)")
    if "trade grid unavailable" not in grid:
        fail("2014 grid missing unavailable copy")
    if "available: false" not in grid:
        fail("2014 grid hook still exposes 2018-2025 deals")
    if "deals: null" not in grid:
        fail("2014 grid hook still has a deal count")


def live_8765() -> None:
    try:
        html = urllib.request.urlopen("http://127.0.0.1:8765/trades.html?year=2014", timeout=3).read().decode()
    except (urllib.error.URLError, TimeoutError) as e:
        fail(f"trades.html?year=2014 not reachable on 8765: {e}")
        return
    if "trades.js?v=15" not in html:
        fail("8765 trades.html is not serving trades.js?v=15")
    if 'id="trade-grid-note"' not in html:
        fail("8765 trades.html missing #trade-grid-note")
    try:
        js = urllib.request.urlopen("http://127.0.0.1:8765/trades.js?v=15", timeout=3).read().decode()
    except (urllib.error.URLError, TimeoutError) as e:
        fail(f"trades.js?v=15 not reachable on 8765: {e}")
        return
    if "function txUnavailable" not in js:
        fail("8765 trades.js?v=15 is stale (no txUnavailable)")
    if "ALL.filter" not in js:
        fail("8765 trades.js?v=15 is stale (grid not year-scoped)")
    if "short(s.tid)" in js:
        fail("8765 blotter still chops names via short()")


def eval_blotter(js: str, html: str) -> None:
    rt = grab_fn(js, "renderTrades")
    if not rt:
        fail("renderTrades missing")
        return
    if "short(s.tid)" in rt or "short(" in rt:
        fail("blotter cells still use short() — Grand Teeton Fee without Feelers")
    if ".slice(0, 16)" in rt:
        fail("blotter still slices franchise names to 16 chars")
    if "tName(s.tid)" not in rt:
        fail("blotter does not paint full tName()")
    if 'title="${A.esc(tName(s.tid))}"' not in rt and "title=" not in rt:
        fail("blotter name missing title with full franchise name")
    # Chopped invented stems must not be the visible cell text.
    chopped = (
        "Grand Teeton Fee",
        "Squaw Valley Ski",
        "San Diego Shadow",
    )
    for stem in chopped:
        if stem in rt and "Feelers" not in rt and "Skinners" not in rt and "Shadowc" not in rt:
            fail(f"blotter cells show {stem!r} without the rest of the franchise name")
    # Simulate the old short() against current names — blotter must not emit those.
    def short_old(n: str) -> str:
        return n[:16] + "…" if len(n) > 17 else n
    for full in (
        "Grand Teeton Feelers",
        "Squaw Valley Skinners",
        "San Diego Shadowcöcks",
    ):
        cut = short_old(full)
        if cut in rt:
            fail(f"blotter template contains chopped {cut!r}")
        if full.startswith("Grand Teeton Feelers"):
            if "Grand Teeton Fee" in cut and "Feelers" not in cut:
                # lock: this is what the old helper produced; renderTrades must not.
                pass
    if 'id="trade-blotter-block"' not in html:
        fail("trades.html missing #trade-blotter-block full-width blotter")
    if "white-space: normal" not in html and "white-space: normal" not in Path("/workspace/affl-qa/site/styles.css").read_text():
        fail("blotter names still nowrap/ellipsis")


def main() -> int:
    js_path = SITE / "trades.js"
    html_path = SITE / "trades.html"
    act_path = SITE / "activity.json"
    js = js_path.read_text() if js_path.is_file() else ""
    html = html_path.read_text() if html_path.is_file() else ""
    if not js:
        fail("missing site/trades.js")
    if not html:
        fail("missing site/trades.html")

    bust = re.search(r"trades\.js\?v=(\d+)", html)
    if not bust:
        fail("trades.html missing trades.js cache bust")
    elif int(bust.group(1)) < 15:
        fail(f"trades.js cache still v={bust.group(1)} (need v=15)")

    eval_blotter(js, html)

    if "function txUnavailable" not in js:
        fail("txUnavailable missing")
    kpi = grab_fn(js, "renderKPIs")
    if not kpi:
        fail("renderKPIs missing")
    else:
        if "txUnavailable" not in kpi:
            fail("renderKPIs does not call txUnavailable")
        if "no trades this season" in kpi and "unavailable" not in kpi:
            fail("completed-trades still uses counted-zero copy on 2014-17")
        if "unavailable — ESPN does not retain" not in kpi:
            fail("card 01 missing unavailable caption")
        if "unavailable — waiver and FA adds start in 2018" not in kpi:
            fail("card 03 missing unavailable caption")
        if "waiver claims and free-agent adds" not in kpi:
            fail("card 03 empty caption in season mode — no fallback subtitle")
        if "__afflTradeKPIs" not in kpi:
            fail("renderKPIs does not expose __afflTradeKPIs for eval")
        if "c.desc ?" not in kpi:
            fail("empty kpi-desc line is still always painted")
    eval_labels(js)
    eval_grid(js)

    if 'id="trade-grid-note"' not in html:
        fail("trades.html missing #trade-grid-note")
    if '<select class="team-select" id="year-picker"' not in html:
        fail("Season select missing")
    if 'id="squad-picker"' not in html:
        fail("Team select missing")
    if re.search(r'class="week-picker" id="year-picker"', html):
        fail("year chips came back")

    if not act_path.is_file():
        fail("missing site/activity.json")
    else:
        act = json.loads(act_path.read_text())
        managers = (act.get("cumulative") or {}).get("managers") or {}
        m18 = managers.get("m18") or {}
        m04 = managers.get("m04") or {}
        if m18.get("tradesProposed") != 2079:
            fail(f"Feelers proposed {m18.get('tradesProposed')} — expected 2079")
        if m18.get("tradesAccepted") != 37:
            fail(f"Feelers accepted {m18.get('tradesAccepted')} — expected 37")
        den = (m18.get("tradesAccepted") or 0) + (m18.get("tradesDeclined") or 0) + (m18.get("tradesVetoed") or 0)
        rate = round(100 * (m18.get("tradesAccepted") or 0) / den) if den else None
        if rate != 3:
            fail(f"Feelers accept rate {rate}% — expected 3%")
        if m04.get("tradesProposed") != 20:
            fail(f"Chewbacca proposed {m04.get('tradesProposed')} — expected 20")
        if (m04.get("tradesAccepted") or 0) != 0 or (m04.get("tradesDeclined") or 0) != 0 or (m04.get("tradesVetoed") or 0) != 0:
            fail("Chewbacca rate must stay unavailable (denom 0)")
        if "m01" in managers:
            fail("m01 leaked — must stay one Chupacabras (m07)")
        for y in ("2014", "2015", "2016", "2017"):
            rec = (act.get("years") or {}).get(y) or {}
            if rec.get("available") is True:
                fail(f"{y} marked available in activity.json")
            if rec.get("managers"):
                fail(f"{y} has manager zeros in activity.json")

    if "xProposed" not in js:
        fail("dual axis xProposed missing")

    live_8765()

    if fails:
        print("FAIL")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("2014-17 unavailable; grid year-scoped; blotter full names; v=15")
    return 0


if __name__ == "__main__":
    sys.exit(main())
