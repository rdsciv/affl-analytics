#!/usr/bin/env python3
"""CHI-57 / AFFL-038: Awards one picker + position breakout."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

POS_CHIPS = ("ALL", "QB", "RB", "WR", "TE", "K", "DST")
LANCE_PID = 4383351


def norm_pos(p):
    u = str(p or "").upper().replace(" ", "")
    if u in ("DST", "D/ST", "DEF"):
        return "DST"
    return u


def filter_starts(starts, want):
    if not want or want == "ALL":
        return list(starts or [])
    return [s for s in (starts or []) if norm_pos(s.get("pos")) == want]


def cucks_tid(data, year):
    for t in ((data.get("seasons") or {}).get(str(year), {}) or {}).get("teams") or []:
        if t.get("owner") == "m02":
            return t.get("id")
    return None


def main():
    html = (SITE / "awards.html").read_text()
    js = (SITE / "awards.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())
    y2022 = json.loads((SITE / "years" / "2022.json").read_text())

    if 'id="scope-picker"' in html:
        fail("awards.html still has #scope-picker")
    if re.search(r'picker-label">\s*View\s*<', html):
        fail("awards.html still has View row")
    if "View" in html and 'id="scope-picker"' in html:
        fail("awards.html still has View / scope picker")

    if "Cumulative" not in html:
        fail("awards.html missing Cumulative chip")
    for y in range(2014, 2026):
        if f'data-y="{y}"' not in html and f">{y}<" not in html:
            fail(f"awards.html missing year chip {y}")

    if 'id="pos-picker"' not in html:
        fail("awards.html missing #pos-picker")
    for pos in POS_CHIPS:
        if f'data-pos="{pos}"' not in html:
            fail(f"awards.html missing pos chip {pos}")

    bust = re.search(r"awards\.js\?v=(\d+)", html)
    if not bust:
        fail("awards.html awards.js not cache-busted")
    elif int(bust.group(1)) < 4:
        fail(f"awards.js cache still v={bust.group(1)}")

    if "function normPos" not in js:
        fail("awards.js missing normPos")
    if "function filterStarts" not in js:
        fail("awards.js missing filterStarts")
    if "function applyPos" not in js:
        fail("awards.js missing applyPos")
    if '"D/ST"' not in js or '"DEF"' not in js:
        fail("awards.js missing DST aliases D/ST / DEF")
    if "applyPos(raw, pos)" not in js:
        fail("awards.js does not filter boards by pos")
    if "ngs-chip" not in js or 'class="ngs-chip' not in js:
        fail("awards.js missing ngs-chip markup")
    if "<b>" not in js or " · " not in js or "%" not in js:
        fail("awards.js missing ngs-chip <b>POS</b> n · pct markup")
    if "ngs-chip al" not in js and 'chipTint' not in js and '"al"' not in js:
        fail("awards.js missing All-League ngs-chip tint")
    if "bush" not in js:
        fail("awards.js missing bush chip tint")
    if "scopePicker" in js or "showYearRow" in js:
        fail("awards.js still uses scopePicker / showYearRow")
    if 'data-y="cum"' not in js and "Cumulative" not in js:
        fail("awards.js missing Cumulative-first year chips")

    if ".award-pos" not in css:
        fail("styles.css missing .award-pos")
    if ".ngs-chip.al" not in css:
        fail("styles.css missing .ngs-chip.al")
    if ".ngs-chip.bush" not in css:
        fail("styles.css missing .ngs-chip.bush")

    bush = ((y2022.get("awards") or {}).get("bushLeague") or [])
    tid = cucks_tid(data, 2022)
    row = next((r for r in bush if r.get("tid") == tid), None)
    if not row:
        fail(f"2022 bush missing Cucks tid {tid}")
        lance = []
    else:
        lance = [s for s in (row.get("starts") or []) if s.get("pid") == LANCE_PID]
        if len(lance) != 2:
            fail(f"Trey Lance should appear twice in Cucks 2022 bush, got {len(lance)}")
        wks = sorted((s.get("wk"), s.get("pts"), norm_pos(s.get("pos"))) for s in lance)
        if wks != [(1, 10.0, "QB"), (2, 2.5, "QB")]:
            fail(f"Lance 2022 bush weeks {wks} != [(1, 10.0, QB), (2, 2.5, QB)]")
        qb = filter_starts(row.get("starts") or [], "QB")
        wr = filter_starts(row.get("starts") or [], "WR")
        qb_lance = [s for s in qb if s.get("pid") == LANCE_PID]
        wr_lance = [s for s in wr if s.get("pid") == LANCE_PID]
        if len(qb_lance) != 2:
            fail(f"QB filter should keep both Lance starts, got {len(qb_lance)}")
        if wr_lance:
            fail(f"WR filter should drop Lance, got {wr_lance}")
        print(f"Cucks 2022 bush: {len(row.get('starts') or [])} starts, Lance QB x{len(qb_lance)}")

    # cumulative honesty: Cucks 42 ALL, QB split includes both Lance weeks
    all_starts = []
    for y in range(2014, 2026):
        bundle = json.loads((SITE / "years" / f"{y}.json").read_text())
        tid_y = cucks_tid(data, y)
        for r in ((bundle.get("awards") or {}).get("bushLeague") or []):
            if r.get("tid") == tid_y:
                all_starts.extend(r.get("starts") or [])
    qb_all = filter_starts(all_starts, "QB")
    print(f"Cucks cum bush ALL={len(all_starts)} QB={len(qb_all)}")
    if len(all_starts) != 42:
        fail(f"Cucks cum bush ALL {len(all_starts)} != 42")
    lance_cum = [s for s in qb_all if s.get("pid") == LANCE_PID]
    if len(lance_cum) != 2:
        fail(f"Cucks QB cum should still include both Lance starts, got {len(lance_cum)}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/awards.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"awards.html HTTP {code}")
        else:
            print("awards.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"awards.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
