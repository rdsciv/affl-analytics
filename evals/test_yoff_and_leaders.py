#!/usr/bin/env python3
"""Playoff hero tiles + franchise all-time scorers + player-page chrome."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []
fail = lambda m: fails.append(m)

TAYLOR = "4242335"
ROSAS = "3068939"  # consolation-only starter in 2018
WHITE = "4697815"  # Rachaad White, drafted 2022
BIJAN = "4430807"


def src(name):
    f = SITE / name
    return f.read_text() if f.exists() else ""


def http_ok(path):
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/" + path, timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"{path} HTTP {code}")
        else:
            print(f"{path} HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"{path} not reachable on 8765: {e}")


def player_years(pid, index, nfl):
    affl = list((index.get(str(pid)) or {}).get("years") or [])
    rec = nfl.get(str(pid)) or {}
    nfl_ys = [int(k) for k in rec if str(k).isdigit() and len(str(k)) == 4]
    return sorted(set(affl + nfl_ys))


def main():
    yoff_path = SITE / "yoff.json"
    lead_path = SITE / "franchise_leaders.json"
    if not yoff_path.exists():
        fail("site/yoff.json missing")
    if not lead_path.exists():
        fail("site/franchise_leaders.json missing")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    yoff = json.loads(yoff_path.read_text())
    leaders = json.loads(lead_path.read_text())
    index = json.loads((SITE / "player_index.json").read_text())
    nfl = json.loads((SITE / "nfl_weeks.json").read_text())
    js = src("players.js")
    html = src("players.html")
    tjs = src("teams.js")
    thtml = src("teams.html")

    graded = [k for k, v in yoff.items()
              if (v.get("nYoff") or 0) >= 3
              and isinstance(v.get("yoffstud"), (int, float))
              and isinstance(v.get("yoffdud"), (int, float))]
    print(f"graded players nYoff>=3: {len(graded)}")
    if not graded:
        fail("no player has nYoff>=3 with numeric yoffstud/yoffdud")

    jt = yoff.get(TAYLOR)
    if not jt:
        fail("Jonathan Taylor 4242335 missing from yoff.json")
    else:
        print("Taylor", jt)
        if (jt.get("rings") or 0) < 1:
            fail(f"Taylor rings {jt.get('rings')} expected >= 1 (2025 Shadowcocks champ roster)")
        if 2025 not in (jt.get("ringYears") or []):
            fail(f"Taylor ringYears {jt.get('ringYears')} missing 2025")
        if (jt.get("nYoff") or 0) < 3:
            fail(f"Taylor nYoff {jt.get('nYoff')} expected >= 3")

    ros = yoff.get(ROSAS) or {}
    print("Rosas (consolation-only)", ros)
    if (ros.get("nYoff") or 0) != 0:
        fail(f"Aldrick Rosas nYoff={ros.get('nYoff')} — consolation-only weeks must not count")

    feel = leaders.get("m18") or {}
    for pos in ("QB", "RB", "WR"):
        rows = feel.get(pos)
        if not rows:
            fail(f"Feelers m18 missing {pos} leaders")
        else:
            print(f"Feelers {pos} #1", rows[0])
            if not rows[0].get("name"):
                fail(f"Feelers {pos} top row has no name")

    if "yoffstud" not in js:
        fail("players.js hero missing yoffstud")
    if "AFFL titles" not in js and "titles" not in js:
        fail("players.js hero missing titles")
    if "drafted → yoff" not in js and "drafted" not in js:
        fail("players.js hero missing drafted → yoff")
    if "yoff.json" not in js:
        fail("players.js does not fetch yoff.json")
    if "proj.json" not in js:
        fail("players.js lost proj.json overlay")
    if "nfl_weeks.json" not in js:
        fail("players.js lost nfl_weeks.json overlay")
    if "ngs.json" not in js:
        fail("players.js lost ngs.json overlay")
    if "gatherLogs" not in js:
        fail("players.js lost gatherLogs")
    if "weekProj" not in js:
        fail("players.js lost weekProj")
    if "players.js?v=" not in html:
        fail("players.html did not cache-bust players.js")

    if "scorers-block" not in thtml:
        fail("teams.html missing scorers-block")
    if "All-time scorers" not in tjs and "Leading scorers" not in tjs:
        fail("teams.js missing All-time / Leading scorers card")
    if "franchise_leaders.json" not in tjs:
        fail("teams.js does not fetch franchise_leaders.json")
    if "playerLink" not in tjs:
        fail("teams.js lost playerLink")

    # chrome: no global view / squad / season strip on the players page
    if 'id="scope-picker"' in html and "hidden" not in html.split('id="scope-picker"')[0][-80:]:
        # allow hidden attribute on the row
        chunk = html[max(0, html.find("scope-picker") - 200): html.find("scope-picker") + 40]
        if "hidden" not in chunk:
            fail("players.html still shows scope-picker")
    if 'id="squad-picker"' in html:
        chunk = html[max(0, html.find("squad-picker") - 200): html.find("squad-picker") + 40]
        if "hidden" not in chunk:
            fail("players.html still shows squad-picker")
    if "scopePicker" in js:
        fail("players.js still renders scopePicker")
    if "squadPicker" in js:
        fail("players.js still renders squadPicker")
    if "yearPicker(" in js or "A.yearPicker" in js:
        fail("players.js still renders the global year picker")
    if "function playerYears" not in js and "function playerYears(" not in js:
        # it is a function playerYears(pid)
        if "function playerYears" not in js:
            fail("players.js missing playerYears()")

    wy = player_years(WHITE, index, nfl)
    print("Rachaad White years", wy)
    early = [y for y in wy if y < 2022]
    if early:
        fail(f"Rachaad White years include pre-2022 {early}")
    if 2022 not in wy or 2025 not in wy:
        fail(f"Rachaad White years {wy} should include 2022–2025")

    by = player_years(BIJAN, index, nfl)
    print("Bijan 4430807 years", by)
    if any(y < 2023 for y in by):
        fail(f"Bijan years include pre-2023 {by}")

    if "data-k=" not in js or "bindLogSort" not in js:
        fail("players.js game log thead is not sortable")
    if 'th class="s' not in js and "class=\"s" not in js:
        fail("players.js log headers missing sortable class")

    http_ok("players.html")
    http_ok("teams.html")
    http_ok("yoff.json")
    http_ok("franchise_leaders.json")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
