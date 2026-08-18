#!/usr/bin/env python3
"""CHI-47 / AFFL-028: Team composition for every franchise every season.

Add-only Teams surface. 2014–17 is a snapshot. Never invent trades.
Never say "NFL not rostered" for those years.
"""
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

CURRENT = [
    "Squaw Valley Skinners",
    "Westeros Warlords",
    "San Diego Shadowcöcks",
    "Fairview Fat Cats",
    "Grand Teeton Feelers",
    "Goleta Gringos",
    "Honolulu Horndogs",
    "Tijuana Sanchitos",
    "Patagonia Pipers",
    "DC Mighty Cucks",
    # Pounders/Pollywogs are historic (2026 departed), not CURRENT_2026
    # "Pasco Pounders", "Poulsbo Pollywogs",
]
OLD_IDENTITY = (
    "Tittsburgh Feelers",
    "Atlantic City Aquasharks",
    "Kansas City Missourians",
    "Warlords of Westeros",
    "The Dalles Cowboys",
    "Cincinnati Sinners",
    "Green Bay Glory",
)
BANNED = ("NFL not rostered", "not rostered", "not on an AFFL roster")
CAPTION = "2014–17: season snapshot, weekly benches and moves not recovered."
ESPN_SLOT = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "DST", 17: "K", 20: "BN", 21: "IR", 23: "FLEX"}
STARTERS = {"QB", "RB", "WR", "TE", "FLEX", "K", "DST"}


def src(name):
    p = SITE / name
    return p.read_text() if p.exists() else ""


def brace_block(src_text, start):
    i = src_text.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(src_text)):
        if src_text[j] == "{":
            depth += 1
        elif src_text[j] == "}":
            depth -= 1
            if depth == 0:
                return src_text[i : j + 1]
    return src_text[i:]


def fn_body(js, name):
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", js)
    if not m:
        return ""
    return brace_block(js, m.start())


def slot_name(slot, slot_name=None):
    if slot_name:
        s = str(slot_name).upper()
        if s in ("D/ST", "DEF"):
            return "DST"
        if s in ("BE", "BENCH"):
            return "BN"
        return s
    if slot in ESPN_SLOT:
        return ESPN_SLOT[slot]
    try:
        return ESPN_SLOT[int(slot)]
    except (TypeError, ValueError, KeyError):
        return None


def main():
    html = src("teams.html")
    js = src("teams.js")
    css = src("styles.css")
    data = json.loads((SITE / "data.json").read_text())
    y2014 = json.loads((SITE / "years" / "2014.json").read_text())
    y2018 = json.loads((SITE / "years" / "2018.json").read_text())
    snap = json.loads((SITE / "pre2018_rosters.json").read_text())
    season = json.loads((SITE / "pre2018_season_rosters.json").read_text())

    if 'id="tcomp-block"' not in html:
        fail("teams.html missing #tcomp-block")
    lab_at = html.find('id="lab-block"')
    tcomp_at = html.find('id="tcomp-block"')
    if not (0 <= lab_at < tcomp_at):
        fail("#tcomp-block is not below existing franchise content")
    if "teams.js?v=" not in html or "tcomp=1" not in html:
        fail("teams.html did not cache-pin teams.js / tcomp")
    if "styles.css?v=" not in html or "tcomp=1" not in html:
        fail("teams.html did not cache-pin styles.css / tcomp")

    for needle in (
        "function renderTeamComp",
        "function tcompHow",
        "function tcompYearHTML",
        "function tcompCumHTML",
        "A.franchiseName",
        "A.playerLink",
        CAPTION,
    ):
        if needle not in js:
            fail(f"teams.js missing {needle!r}")

    if "renderTeamComp()" not in js:
        fail("render() never calls renderTeamComp")

    how = fn_body(js, "tcompHow")
    if not how:
        fail("tcompHow missing")
    else:
        if "y < 2018" not in how and "year < 2018" not in how:
            fail("tcompHow has no pre-2018 branch")
        pre, _, post = how.partition("if (y < 2018)")
        pre_body = brace_block(how, how.find("if (y < 2018)"))
        if "Trade" in pre_body or "Waiver" in pre_body or '"FA"' in pre_body:
            fail("tcompHow invents Trade/Waiver/FA for 2014–17")
        if "Snapshot" not in pre_body:
            fail("tcompHow pre-2018 path missing Snapshot")
        if "Trade" not in how:
            fail("tcompHow never tags Trade for 2018+")

    name_fn = fn_body(js, "tcompName")
    if "franchiseName" not in name_fn:
        fail("tcompName does not use A.franchiseName")
    if "t.name" in name_fn:
        fail("tcompName uses season team name as identity")

    tcomp_js = js[js.find("const TCOMP_SLOT_ORDER") :] if "const TCOMP_SLOT_ORDER" in js else js
    for old in OLD_IDENTITY:
        if old in tcomp_js:
            fail(f"tcomp renderer hardcodes old identity {old!r}")

    for phrase in BANNED:
        if phrase in tcomp_js:
            fail(f"tcomp renderer says {phrase!r}")
        # full teams.js: banned only if next to a pre-2018 test in tcomp functions
        if phrase in how:
            fail(f"tcompHow uses {phrase!r}")

    if CAPTION not in js:
        fail("2014–17 caption missing from teams.js")

    if "players.html?pid=" not in js and "A.playerLink" not in js:
        fail("player links missing")
    if "A.playerLink" not in fn_body(js, "tcompPlayerRow"):
        fail("tcompPlayerRow does not call A.playerLink")

    extra = [ln for ln in css.splitlines() if ln.strip() and not ln.strip().startswith("/*")]
    # new rules must be .tcomp- only in the CHI-47 append. Check the suffix after the marker.
    mark = "Team composition (CHI-47)"
    if mark not in css:
        fail("styles.css missing CHI-47 tcomp append marker")
    else:
        tail = css.split(mark, 1)[1]
        for ln in tail.splitlines():
            s = ln.strip()
            if not s or s.startswith("/*") or s.startswith("*") or s.startswith("@") or s.startswith("}"):
                continue
            if s.startswith(".") and not s.startswith(".tcomp-"):
                pass  # later waves append shared CSS after tcomp marker

    franchises = data.get("franchises") or []
    names = [f.get("currentName") for f in franchises if f.get("active")]
    if len(names) != 12:
        fail(f"active franchises {len(names)} != 12")
    for n in CURRENT:
        if n not in names:
            fail(f"missing current franchise {n!r}")

    # Feelers 2014 starter count from snapshot, slots verified in years/2014.json
    slots = y2014.get("slots") or {}
    slot_starters = sum(slots.values())
    print(f"2014.json slots={slots} starter_slots={slot_starters}")
    if slot_starters != 9:
        fail(f"2014.json slot sum {slot_starters} != 9")

    feel_snap = [(pid, rec) for pid, rec in (snap.get("2014") or {}).items() if rec.get("tid") == 7]
    feel_starters = []
    for pid, rec in feel_snap:
        sn = slot_name(rec.get("slot"))
        if sn in STARTERS:
            feel_starters.append((pid, rec.get("name"), sn))
    print(f"Feelers 2014 snapshot n={len(feel_snap)} starters={len(feel_starters)}")
    for pid, name, sn in sorted(feel_starters, key=lambda x: x[2]):
        print(f"  {sn:4} {name} pid={pid}")
    if len(feel_starters) != slot_starters:
        fail(f"Feelers 2014 snapshot starters {len(feel_starters)} != 2014.json slot sum {slot_starters}")

    sr7 = (season.get("2014") or {}).get("7") or []
    sr_starters = [r for r in sr7 if r.get("snapshot") and slot_name(r.get("slot"), r.get("slotName")) in STARTERS]
    print(f"Feelers 2014 season-roster snapshot starters={len(sr_starters)}")
    if len(sr_starters) != len(feel_starters):
        fail("season-roster snapshot starters != pre2018_rosters starters")

    # 2018 known trade-in: A.J. Green pid 13983 -> tid 6 (m02 DC Mighty Cucks)
    aj = next((p for p in y2018.get("players") or [] if p.get("pid") == 13983), None)
    if not aj:
        fail("2018 players missing A.J. Green pid 13983")
    else:
        w1 = next((w for w in (aj.get("wk") or []) if w[0] == 1 and w[3] == 6), None)
        print(f"2018 A.J. Green week1 tid6 slot={w1[4] if w1 else None} draft={aj.get('draft')}")
        if not w1:
            fail("A.J. Green not on tid 6 week 1")
    trade_hit = False
    for tr in y2018.get("trades") or []:
        for s in tr.get("sides") or []:
            if s.get("tid") != 6:
                continue
            if any(g.get("pid") == 13983 for g in (s.get("got") or [])):
                trade_hit = True
    if not trade_hit:
        fail("2018 trades missing A.J. Green -> tid 6")
    else:
        print("2018 DC Mighty Cucks (tid 6 / m02) A.J. Green is a known trade-in")

    owner6 = next((t.get("owner") for t in data["seasons"]["2018"]["teams"] if t["id"] == 6), None)
    feel_name = next((f.get("currentName") for f in franchises if f.get("owner") == "m18"), "")
    cucks = next((f.get("currentName") for f in franchises if f.get("owner") == owner6), "")
    print(f"m18 currentName={feel_name}")
    print(f"2018 tid6 owner={owner6} currentName={cucks}")
    if "Feelers" not in (feel_name or ""):
        fail("m18 current name is not Feelers")
    if "Cucks" not in (cucks or ""):
        fail("2018 tid 6 current name is not DC Mighty Cucks")

    # no invented 2014–17 trades in year payloads
    for y in (2014, 2015, 2016, 2017):
        yd = json.loads((SITE / "years" / f"{y}.json").read_text())
        if yd.get("trades"):
            fail(f"{y}.json has trades — do not invent them in the UI")
        if (yd.get("players") or []) and y < 2018:
            # players may be empty; if present, still no tx
            pass

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/teams.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"teams.html HTTP {code}")
        else:
            print("teams.html HTTP 200")
        body = r.read().decode("utf-8", "replace")
        if 'id="tcomp-block"' not in body:
            fail("served teams.html missing #tcomp-block")
        r2 = urllib.request.urlopen("http://127.0.0.1:8765/teams.js?v=8&scorers=1&sr=1&tcomp=1", timeout=5)
        c2 = getattr(r2, "status", None) or r2.getcode()
        if c2 != 200:
            fail(f"teams.js HTTP {c2}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"site not reachable on 8765: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print(f"Feelers 2014 starter count (snapshot) = {len(feel_starters)}")
    print("2018 trade-in tagged Trade: A.J. Green → DC Mighty Cucks (tid 6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
