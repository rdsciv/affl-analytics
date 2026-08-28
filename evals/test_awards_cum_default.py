#!/usr/bin/env python3
"""CHI-137: Awards defaults to Cumulative. Year query still opens that season."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg: str) -> None:
    fails.append(msg)


def main() -> int:
    html = (SITE / "awards.html").read_text()
    js = (SITE / "awards.js").read_text()

    cum = re.search(r'<button[^>]*data-y="all"[^>]*>', html) or re.search(r'<button[^>]*data-y="cum"[^>]*>', html)
    y25 = re.search(r'<button[^>]*data-y="2025"[^>]*>', html)
    if not cum:
        fail("awards.html missing All chip")
    elif not re.search(r'class="[^"]*\bon\b', cum.group(0)):
        fail("awards.html All chip is not on by default")
    if y25 and re.search(r'class="[^"]*\bon\b', y25.group(0)):
        fail("awards.html 2025 chip is still on by default")

    if 'id="award-leaders"' not in html:
        fail("awards.html missing #award-leaders")
    elif "id=\"award-leaders\" hidden" not in html:
        fail("awards.html #award-leaders is not hidden before render")

    bust = re.search(r"awards\.js\?v=(\d+)", html)
    if not bust:
        fail("awards.html awards.js not cache-busted")
    elif int(bust.group(1)) < 6:
        fail(f"awards.js cache still v={bust.group(1)}")

    if "let scope = A.scopeFromURL()" in js:
        fail("awards.js still defaults scope from URL (bare URL is season)")
    if 'let scope = "cum"' not in js:
        fail("awards.js does not default scope to cum")

    if 'await pick(+qs.get("year") || A.years()[0])' in js:
        fail("awards.js still boots latest year when no year query")
    if 'const yearQ = qs.get("year")' not in js:
        fail("awards.js boot does not read year query separately")
    if 'scope = "season"' not in js:
        fail("awards.js does not set season when year query is present")
    if "if (yearQ)" not in js:
        fail("awards.js boot does not branch on year query")

    if "A.showYearRow(false)" in js or "showYearRow(false)" in js:
        fail("awards.js hides the year row; chips stay visible on Cumulative")

    if "leads.hidden = false" not in js:
        fail("awards.js never unhides #award-leaders after render")

    if fails:
        print("FAIL")
        for item in fails:
            print("-", item)
        return 1
    print("PASS CHI-137/142 awards All default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
