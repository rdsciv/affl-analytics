#!/usr/bin/env python3
"""2014–2017 season-long AFFL rosters: draft ∪ starts ∪ snapshot, real NFL pts."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

NEED_2014_7 = {11278, 13934, 14881, 5536}
DRAFT_ONLY_CANDIDATES = {11258, 15893, 2330}  # CJ, Ellington, Brady


def main():
    path = SITE / "pre2018_season_rosters.json"
    if not path.exists():
        fail("site/pre2018_season_rosters.json missing")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    data = json.loads(path.read_text())
    feel = (data.get("2014") or {}).get("7") or []
    print(f"2014 tid 7 season roster n={len(feel)}")
    by_pid = {}
    for row in feel:
        pid = row.get("pid")
        by_pid[int(pid)] = row
        print(
            f"  {row.get('name')} pid={pid} starts={row.get('starts')} "
            f"nflPts={row.get('nflPts')} drafted={row.get('drafted')} snap={row.get('snapshot')}"
        )

    for pid in NEED_2014_7:
        if pid not in by_pid:
            fail(f"2014 tid 7 missing pid {pid}")

    draft_only = [
        pid for pid in DRAFT_ONLY_CANDIDATES
        if pid in by_pid and by_pid[pid].get("drafted") and not by_pid[pid].get("snapshot")
    ]
    if not draft_only:
        fail("2014 tid 7 missing a drafted-not-on-snapshot pid (CJ/Ellington/Brady)")
    else:
        print("draft-only pids present:", draft_only)

    forte = by_pid.get(11278) or {}
    pts = forte.get("nflPts")
    print(f"Forte nflPts={pts}")
    if not isinstance(pts, (int, float)):
        fail(f"Forte nflPts is {pts!r}, need a real number from nflverse")
    elif pts <= 100:
        fail(f"Forte nflPts {pts} is not > 100")

    js = (SITE / "teams.js").read_text()
    html = (SITE / "teams.html").read_text()
    if "Season roster" not in js:
        fail("teams.js does not mention Season roster")
    if "pre2018_season_rosters" not in js:
        fail("teams.js does not mention pre2018_season_rosters")
    if "season-roster-block" not in html:
        fail("teams.html missing #season-roster-block")
    if "Tittsburgh" in js.split("function renderSeasonRoster")[1][:2500] if "function renderSeasonRoster" in js else "":
        fail("Season roster renderer mentions Tittsburgh")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/teams.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"teams.html HTTP {code}")
        else:
            print("teams.html HTTP 200")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/pre2018_season_rosters.json", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail(f"pre2018_season_rosters.json HTTP {c2}")
        else:
            print("pre2018_season_rosters.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
