#!/usr/bin/env python3
"""ESPN Moves overlay + History Transaction Counter wiring."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)


def main():
    path = SITE / "moves.json"
    if not path.exists():
        fail("site/moves.json missing")
        moves = {}
    else:
        moves = json.loads(path.read_text())
        y2014 = moves.get("2014") or {}
        y2019 = moves.get("2019") or {}

        def rec(year_bag, tid):
            return year_bag.get(str(tid)) or year_bag.get(tid) or {}

        def get(year_bag, tid, key="moves"):
            r = rec(year_bag, tid)
            return None if not r else r.get(key)

        if get(y2014, 7) != 27:
            fail(f"2014 tid 7 moves {get(y2014, 7)} != 27")
        if get(y2014, 4) != 44:
            fail(f"2014 tid 4 moves {get(y2014, 4)} != 44")
        if get(y2014, 10) != 41:
            fail(f"2014 tid 10 moves {get(y2014, 10)} != 41")
        r14 = rec(y2014, 7)
        if r14.get("drops") != 26:
            fail(f"2014 tid 7 drops {r14.get('drops')} != 26")
        if r14.get("trades") != 3:
            fail(f"2014 tid 7 trades {r14.get('trades')} != 3")
        print(f"2014 Feelers (tid 7) moves={get(y2014, 7)}")
        print(f"2014 Thunder (tid 4) moves={get(y2014, 4)}")
        print(f"2014 Horndogs (tid 10) moves={get(y2014, 10)}")

        r19 = rec(y2019, 7)
        if r19.get("moves") != 27:
            fail(f"2019 tid 7 moves {r19.get('moves')} != 27")
        if r19.get("drops") != 25:
            fail(f"2019 tid 7 drops {r19.get('drops')} != 25")
        if r19.get("trades") != 6:
            fail(f"2019 tid 7 trades {r19.get('trades')} != 6")
        if r19.get("moveToActive") != 96:
            fail(f"2019 tid 7 moveToActive {r19.get('moveToActive')} != 96")
        if r19.get("ir") != 0:
            fail(f"2019 tid 7 ir {r19.get('ir')} != 0")
        print(
            f"2019 Feelers (tid 7) moves={r19.get('moves')} drops={r19.get('drops')} "
            f"trades={r19.get('trades')} moveToActive={r19.get('moveToActive')} ir={r19.get('ir')}"
        )

    html = (SITE / "history.html").read_text()
    if "Transaction Counter" not in html:
        fail("history.html missing Transaction Counter")

    js = (SITE / "history.js").read_text()
    if "Moves" not in js:
        fail("history.js does not mention Moves")
    if "moves.json" not in js:
        fail("history.js does not mention moves.json")
    if "ir" not in js:
        fail("history.js does not read ir")
    if "byWeek" not in js:
        fail("history.js does not read byWeek")
    if "moveToActive" not in js:
        fail("history.js does not read moveToActive")
    if "bag.ir" not in js and ".ir" not in js:
        fail("history.js does not access ir field")
    if "bag.byWeek" not in js and ".byWeek" not in js:
        fail("history.js does not access byWeek field")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/history.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"history.html HTTP {code}")
        else:
            print("history.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"history.html not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
