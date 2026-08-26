#!/usr/bin/env python3
"""CHI-95: same-year WOPR scatter + All-years top weekly chart is not careerRows."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def main():
    html = (SITE / "players.html").read_text()
    js = (SITE / "players.js").read_text()
    persist = js[js.find("Usage that sticks"): js.find("Flock-style compare")]
    load_fn = js.split("async function loadPlayer", 1)[-1].split("function renderYearChips", 1)[0]

    if "→" in persist or "→" in html:
        fail("WOPR chips/copy still use → year pairing")
    if "year-N+1" in persist or "year-N+1" in html:
        fail("year-N+1 pairing remains")
    if re.search(r"function woprPersistPoints\s*\(\s*ydN\s*,\s*ydN1", js):
        fail("woprPersistPoints still takes year-N and year-N+1 files")
    if "same-year" not in persist.lower() and "same year" not in persist.lower():
        fail("persist block does not say same-year")
    if re.search(r"renderChart\s*\(\s*focus\s*,\s*rows\s*\)", load_fn):
        fail("loadPlayer still passes rows (All=careerRows) to renderChart")
    if "chartRows" not in load_fn:
        fail("loadPlayer missing chartRows")
    if not re.search(r"playerYears\s*\([^)]*\)\s*\[\s*0\s*\]", load_fn):
        fail("All-years top chart is not latest year (playerYears(...)[0])")
    if not re.search(r"renderCareerChart\s*\(\s*focus\s*,\s*careerRows\s*\)", load_fn):
        fail("renderCareerChart must still receive careerRows")

    bust = re.search(r"players\.js\?v=(\d+)", html)
    if not bust:
        fail("players.html missing players.js cache")
    elif int(bust.group(1)) < 31:
        fail(f"players.js cache still v={bust.group(1)}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-95: same-year WOPR + All-years top chart != careerRows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
