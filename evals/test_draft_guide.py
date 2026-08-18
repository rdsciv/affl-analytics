#!/usr/bin/env python3
"""CHI-60: AFFL Draft Guide — class grid + scout modal, AFFL data only.

Card exists, URL pid wiring, no Mendoza/Sumer numbers, percentiles from
that year's draft class, HTTP 200 on :8765/draft.html.
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
MERGE = {"m01": "m07", "m03": "m08", "m20": "m10"}


def fail(msg):
    fails.append(msg)


def canon(i):
    return MERGE.get(str(i), str(i))


def pct(val, vals):
    nums = [v for v in vals if v is not None]
    if val is None or len(nums) < 2:
        return None
    below = sum(1 for v in nums if v < val)
    equal = sum(1 for v in nums if v == val)
    return round(100 * (below + 0.5 * (equal - 1)) / (len(nums) - 1))


def main():
    html = (SITE / "draft.html").read_text()
    js = (SITE / "draft.js").read_text()
    css = (SITE / "styles.css").read_text()
    y2025 = json.loads((SITE / "years/2025.json").read_text())
    data = json.loads((SITE / "data.json").read_text())
    bio = json.loads((SITE / "player_bio.json").read_text())

    import re
    dj = re.search(r"draft\.js\?v=(\d+)", html)
    sc = re.search(r"styles\.css\?v=(\d+)", html)
    if not dj or int(dj.group(1)) < 17:
        fail("draft.html did not bump draft.js cache to v>=17")
    if not sc or int(sc.group(1)) < 16:
        fail("draft.html did not bump styles.css cache to v>=16")

    if 'id="draft-guide"' not in html:
        fail("draft.html missing #draft-guide")
    if 'id="guide-grid"' not in html:
        fail("draft.html missing #guide-grid")
    if 'id="guide-modal"' not in html:
        fail("draft.html missing #guide-modal")
    if 'id="guide-card"' not in html:
        fail("draft.html missing #guide-card")
    if 'id="guide-search"' not in html:
        fail("draft.html missing #guide-search")
    if "Draft Guide" not in html:
        fail("draft.html missing Draft Guide heading")

    for needle in ("The Board", "Draft Lab", "id=\"the-board\"", "id=\"fg-stacks\""):
        if needle not in html:
            fail(f"existing draft section missing: {needle}")

    if "function renderGuide" not in js:
        fail("draft.js missing renderGuide")
    if "function guideOpen" not in js:
        fail("draft.js missing guideOpen")
    if "function guideClose" not in js:
        fail("draft.js missing guideClose")
    if "function guidePct" not in js:
        fail("draft.js missing guidePct")
    if "function guideClass" not in js:
        fail("draft.js missing guideClass")
    if "function guideWriteURL" not in js:
        fail("draft.js missing guideWriteURL")
    if "renderGuide();" not in js:
        fail("pick() never calls renderGuide")
    if 'searchParams.set("pid"' not in js:
        fail("URL pid wiring missing searchParams.set pid")
    if "searchParams.delete(\"pid\")" not in js and "searchParams.delete('pid')" not in js:
        fail("close does not strip pid from URL")
    if "history.replaceState" not in js:
        fail("guide does not write URL via replaceState")
    if "guideSlug" not in js and "player" not in js:
        fail("name slug missing")
    if 'searchParams.set("player"' not in js:
        fail("URL name slug param (player) missing")
    if "A.headshotHTML" not in js:
        fail("guide does not use A.headshotHTML")
    if "A.playerLink" not in js:
        fail("guide does not use A.playerLink")
    if "A.franchiseName" not in js and "franchiseName" not in js:
        fail("landing franchise not via franchise helpers")
    if "samePos.length >= 5" not in js and "length >= 5" not in js:
        fail("class does not use same-pos when n>=5")
    if "GUIDE_SKILL" not in js:
        fail("skill-class fallback missing")
    if "board-pos-chips" not in js:
        fail("existing position chips not referenced")
    if "renderGuide();" not in js.split("function bindPosChips", 1)[-1][:400]:
        fail("Board position chips do not refresh the guide grid")

    banned = ("Mendoza", "Sumer", "Bullseye", "Hot Shot", "dropback", "RAS", "forty", "40-yard")
    for bad in banned:
        if bad in js:
            fail(f"draft.js must not contain {bad!r}")
    if re.search(r"TOP 25", js, re.I):
        fail("draft.js invents TOP 25 badges")
    for ln in js.splitlines():
        if re.search(r"film grade|combine grade", ln, re.I) and not re.search(r"no |not |missing|only", ln, re.I):
            fail(f"draft.js invents film/combine grades: {ln.strip()}")

    if ".guide-grid" not in css or ".guide-modal" not in css or ".guide-tile-v" not in css:
        fail("styles.css missing .guide- grid/modal/tile rules")
    if "Tittsburgh" in html or "Tittsburgh" in js:
        fail("Tittsburgh leaked onto the draft page")

    board = (y2025.get("draft") or {}).get("board") or []
    par = (y2025.get("draftValue") or {}).get("parByOverall") or {}
    bijan = next((p for p in board if p.get("pid") == 4430807), None)
    if not bijan:
        fail("2025 board missing Bijan Robinson (pid 4430807)")
    else:
        rbs = [p for p in board if p.get("pos") == "RB"]
        if len(rbs) < 5:
            fail(f"2025 RB class too small for pos split: {len(rbs)}")
        pts = [p.get("pts") for p in rbs if p.get("pts") is not None]
        pars = [par.get(str(p["overall"])) for p in rbs if par.get(str(p["overall"])) is not None]
        pts_pct = pct(bijan.get("pts"), pts)
        par_pct = pct(par.get(str(bijan["overall"])), pars)
        print(f"class_check Bijan 2025 RB n={len(rbs)} pts={bijan.get('pts')} pts_pct={pts_pct} par={par.get(str(bijan['overall']))} par_pct={par_pct}")
        if pts_pct is None or par_pct is None:
            fail("could not compute class percentiles for Bijan from year JSON")
        if "guidePct" not in js or "pts" not in js:
            fail("JS percentile helper not wired to season pts")

    owners = {t["id"]: canon(t["owner"]) for t in data["seasons"]["2025"]["teams"]}
    franch = {canon(f["owner"]): f for f in data.get("franchises") or []}
    if bijan:
        oid = owners.get(bijan["tid"])
        name = (franch.get(oid) or {}).get("currentName")
        if name != "Tijuana Sanchitos":
            fail(f"Bijan 2025 landing expected Tijuana Sanchitos, got {name}")
        if "Tittsburgh" in str(name):
            fail("landing used retired name")
        rec = bio.get("4430807") or {}
        if not rec.get("college"):
            fail("Bijan bio college missing — fixture changed")

    if "m01" not in js and "MERGE" not in js:
        # franchise names go through A.franchiseName / ownerKey which apply MERGE
        if "A.franchiseName" not in js and "ownerKey" not in js:
            fail("no MERGE/franchiseName path for landing names")

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/draft.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"draft.html HTTP {code}")
        else:
            print("draft.html HTTP 200")
        body = r.read().decode("utf-8", "replace")
        if 'id="draft-guide"' not in body:
            fail("served draft.html missing #draft-guide")
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
