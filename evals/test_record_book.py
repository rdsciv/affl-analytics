#!/usr/bin/env python3
"""CHI-50 / AFFL-031: History record book sections from AFFL data."""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []
fail = lambda m: fails.append(m)
BANNED = ("Bob Loblaw", "FantasyGenius Record Book")


def main():
    html = (SITE / "history.html").read_text()
    js = (SITE / "history.js").read_text()
    css = (SITE / "styles.css").read_text()
    data = json.loads((SITE / "data.json").read_text())

    for needle in (
        "Record Book",
        "Winning / Losing Streaks",
        "Team Records",
        "Hall of Fame Performances",
        "HOF Scores",
        "Owners Tenure",
        'id="rb-awards"',
        'id="rb-alltime-note"',
        "not duplicated",
        "Point Title",
        "Combined",
    ):
        if needle not in html:
            fail(f"history.html missing {needle!r}")

    if "Franchise Records" not in html:
        fail("history.html lost Franchise Records")

    for fn in (
        "function renderRecordBook",
        "function computeWeeklyStreaks",
        "function computeHof",
        "function renderAwardIcons",
        "need weekly results",
        "player week grain missing",
        "r.weeks",
        "p.wk",
    ):
        if fn not in js:
            fail(f"history.js missing {fn!r}")

    if ".rb-card" not in css or ".rb-award" not in css:
        fail("styles.css missing .rb- record-book classes")
    if not css.rstrip().endswith("}") and ".rb-award" not in css.split("/* ---------- History record book")[-1]:
        fail("record-book CSS not appended")

    for needle in BANNED:
        if needle in html or needle in js:
            fail(f"other-league name leaked: {needle}")

    # Streaks can be computed: year files have weekly matchup pts.
    have_pts = 0
    have_player_wk = 0
    for y in range(2014, 2026):
        path = SITE / "years" / f"{y}.json"
        if not path.exists():
            fail(f"missing years/{y}.json")
            continue
        yd = json.loads(path.read_text())
        weeks = yd.get("weeks") or {}
        for mus in weeks.values():
            for m in mus or []:
                h, a = (m or {}).get("home") or {}, (m or {}).get("away") or {}
                if h.get("pts") is not None and a.get("pts") is not None:
                    have_pts += 1
        for p in yd.get("players") or []:
            if p.get("wk"):
                have_player_wk += 1

    print(f"weekly matchup sides with pts: {have_pts}")
    print(f"players with week logs: {have_player_wk}")
    if have_pts < 100:
        fail("not enough weekly matchup pts to compute streaks")
    if have_player_wk < 100:
        fail("not enough player week logs for HOF")

    names = [f.get("currentName") or "" for f in data.get("franchises") or []]
    if any("Loblaw" in n for n in names):
        fail("franchise currentName includes Loblaw")
    print("franchises:", ", ".join(n for n in names if n))

    import re
    css_m = re.search(r"styles\.css\?v=(\d+)", html)
    js_m = re.search(r"history\.js\?v=(\d+)", html)
    if not css_m or int(css_m.group(1)) < 27:
        fail("history.html css pin not bumped (need styles.css?v>=27)")
    if not js_m or int(js_m.group(1)) < 16:
        fail("history.js pin not bumped (need history.js?v>=16)")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
