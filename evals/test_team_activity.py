#!/usr/bin/env python3
"""Wave T / Phase 9: team-season activity grid + value-added scatter."""
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


def main():
    html = (SITE / "teams.html").read_text(encoding="utf-8")
    js = (SITE / "teams.js").read_text(encoding="utf-8")
    css = (SITE / "styles.css").read_text(encoding="utf-8")

    if 'id="activity-block"' not in html:
        fail("teams.html missing #activity-block")
    if "function renderActivity" not in js:
        fail("teams.js missing renderActivity")
    if "team_activity.json" not in js:
        fail("teams.js does not load team_activity.json")
    if ".act-grid" not in css:
        fail("styles.css missing .act-grid")

    path = SITE / "team_activity.json"
    if not path.is_file():
        fail("missing site/team_activity.json — run scripts/compute_team_activity.py")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("evidence") != "verified":
        fail("team_activity evidence must be verified")
    seasons = data.get("seasons") or {}
    if "2017" in seasons:
        fail("must not include pre-2018 seasons in payload")
    if "2025" not in seasons:
        fail("missing 2025 season")
    s25 = seasons["2025"]
    teams = s25.get("teams") or {}
    if len(teams) != 12:
        fail(f"2025 teams {len(teams)} != 12")
    # Feelers tid 7
    feel = teams.get("7")
    if not feel:
        fail("2025 tid 7 (Feelers) missing")
    else:
        g = feel.get("grid") or {}
        counts = g.get("counts") or []
        total = sum(sum(r) for r in counts)
        if total < 10:
            fail(f"Feelers 2025 grid total moves {total} too low")
        if feel.get("transactions", 0) < 1:
            fail("Feelers transactions X < 1")
        print(
            f"feelers tx={feel.get('transactions')} VA={feel.get('valueAdded')} "
            f"gridMoves={total} maxCell={g.get('maxCell')}"
        )
    sc = s25.get("scatter") or []
    if len(sc) != 12:
        fail(f"scatter points {len(sc)} != 12")
    if s25.get("medianValueAdded") is None:
        fail("missing medianValueAdded")
    # note documents formula
    note = (data.get("note") or "").lower()
    if "value added" not in note and "started points" not in note:
        fail("payload note must document value-added formula")

    # script exists
    if not (ROOT / "scripts/compute_team_activity.py").is_file():
        fail("missing scripts/compute_team_activity.py")

    bust = re.search(r"teams\.js\?v=(\d+)", html)
    if not bust or int(bust.group(1)) < 13:
        fail("teams.js cache pin need v>=13")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/teams.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"teams.html HTTP {code}")
        else:
            print("teams.html HTTP 200")
        body = r.read().decode("utf-8", errors="ignore")
        if 'id="activity-block"' not in body:
            fail("served teams.html missing activity-block")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"teams.html not reachable: {e}")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/team_activity.json", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"team_activity.json HTTP {code}")
        else:
            print("team_activity.json HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"team_activity.json not reachable: {e}")

    # deep link page still 200
    try:
        url = "http://127.0.0.1:8765/teams.html?squad=m18&year=2025"
        r = urllib.request.urlopen(url, timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"deep link HTTP {code}")
        else:
            print(f"deep link HTTP 200 {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"deep link fail: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("Wave T: activity grid + value-added scatter on teams season view")
    return 0


if __name__ == "__main__":
    sys.exit(main())
