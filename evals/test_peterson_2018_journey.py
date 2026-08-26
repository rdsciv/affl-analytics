#!/usr/bin/env python3
"""CHI-44 / AFFL-024: Peterson 2018 journey uses last home + real trade."""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def main():
    y2018 = json.loads((SITE / "years" / "2018.json").read_text())
    js = (SITE / "players.js").read_text()
    html = (SITE / "players.html").read_text()
    data = json.loads((SITE / "data.json").read_text())

    pl = next((p for p in (y2018.get("players") or []) if p.get("pid") == 10452), None)
    if not pl:
        fail("2018.json missing pid 10452")
        done()
        return 1
    draft = pl.get("draft") or {}
    if draft.get("teamId") != 11:
        fail(f"Peterson 2018 draft.teamId={draft.get('teamId')} != 11")
    if draft.get("bid") != 3:
        fail(f"Peterson 2018 bid={draft.get('bid')} != 3")
    if pl.get("mainTeam") != 6:
        fail(f"Peterson 2018 mainTeam={pl.get('mainTeam')} != 6")
    print(f"Peterson 2018 draft tid={draft.get('teamId')} bid={draft.get('bid')} mainTeam={pl.get('mainTeam')}")

    wks = pl.get("wk") or []
    early = [w for w in wks if int(w[0]) <= 3]
    late = [w for w in wks if int(w[0]) >= 4]
    if not early or any(w[3] != 11 for w in early):
        fail(f"W1-W3 tids {[w[3] for w in early]} not all 11")
    if not late or any(w[3] != 6 for w in late):
        fail(f"W4+ tids {[w[3] for w in late]} not all 6")
    print(f"W1-W3 tid 11 ({len(early)} wks) · W4+ tid 6 ({len(late)} wks)")

    trade = None
    for t in y2018.get("trades") or []:
        if int(t.get("wk") or 0) != 4:
            continue
        for side in t.get("sides") or []:
            for g in side.get("got") or []:
                if g.get("pid") == 10452 and g.get("from") == 11 and side.get("tid") == 6:
                    trade = t
    if not trade:
        fail("W4 trade 10452 from 11 to 6 missing")
    else:
        print("W4 trade 10452 from 11 Honolulu Horndogs to 6 DC Mighty Cucks")

    teams = {t["id"]: t for t in ((data.get("seasons") or {}).get("2018") or {}).get("teams") or []}
    if (teams.get(6) or {}).get("name") != "DC Mighty Cucks":
        fail(f"tName(6,2018) expected DC Mighty Cucks, got {(teams.get(6) or {}).get('name')}")
    if (teams.get(11) or {}).get("name") != "Honolulu Horndogs":
        fail(f"tName(11,2018) expected Honolulu Horndogs, got {(teams.get(11) or {}).get('name')}")

    fn = js.split("function yearHome", 1)[-1].split("function ", 1)[0]
    if ".find(" in fn:
        fail("yearHome still uses .find (first hit)")
    if "last" not in fn:
        fail("yearHome does not walk to last rostered week")
    if "function rosterStints" not in js:
        fail("players.js missing rosterStints")
    if "Traded" not in js or "Finished with" not in js:
        fail("renderJourney/rosterStints missing Traded / Finished with")
    if "One-team stretch" in js:
        fail("multi-stint years can still be labeled One-team stretch")
    if "before W1" not in js:
        fail("draft-before-first-week stint (Adams path) missing")
    journey_line = [ln for ln in html.splitlines() if "pl-journey" in ln]
    if not journey_line or "story-list" in journey_line[0]:
        fail("pl-journey is still only a ul.story-list")
    if "players.js?v=" not in html:
        fail("players.html missing players.js cache bust")
    bust = re.search(r"players\.js\?v=(\d+)", html)
    if bust and int(bust.group(1)) < 24:
        fail(f"players.js cache still v={bust.group(1)}")

    y2025 = json.loads((SITE / "years" / "2025.json").read_text())
    ad = next((p for p in (y2025.get("players") or []) if p.get("pid") == 16800), None)
    if not ad:
        fail("2025.json missing Adams 16800")
    else:
        d = ad.get("draft") or {}
        if d.get("teamId") != 3 or d.get("bid") != 22:
            fail(f"Adams 2025 draft {d}")
        first = (ad.get("wk") or [[None, None, None, None]])[0]
        if first[3] != 7:
            fail(f"Adams 2025 first week tid {first[3]} != 7")
        hit = False
        for t in y2025.get("trades") or []:
            if int(t.get("wk") or 0) != 1:
                continue
            for side in t.get("sides") or []:
                for g in side.get("got") or []:
                    if g.get("pid") == 16800 and g.get("from") == 3 and side.get("tid") == 7:
                        hit = True
        if not hit:
            fail("Adams 2025 W1 trade 3 to 7 missing")
        else:
            print("Adams 2025 auction $22 tid 3 Gringos · first week tid 7 Feelers · W1 trade exists")

    for url in ("http://127.0.0.1:8765/players.html", "http://127.0.0.1:8765/players.js"):
        try:
            r = urllib.request.urlopen(url, timeout=5)
            code = getattr(r, "status", None) or r.getcode()
            if code != 200:
                fail(f"{url} HTTP {code}")
            else:
                print(url.split("/")[-1], "HTTP 200")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fail(f"{url} not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    return 0


def done():
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)


if __name__ == "__main__":
    sys.exit(main())
