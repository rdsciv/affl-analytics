#!/usr/bin/env python3
"""CHI-54: AFFL FPpG is season fantasy points / NFL games, never / AFFL starts.

Locks the Tre Tucker regression: ~104.7 season pts with 1 AFFL start must not
display as ~104 FPpG. Denominator is NFL week rows in nfl_weeks.json.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
JS = SITE / "players.js"
NFL = SITE / "nfl_weeks.json"
INDEX = SITE / "player_index.json"
YEAR = SITE / "years" / "2025.json"
fails = []
fail = lambda m: fails.append(m)

TUCKER_PID = "4428718"


def main():
    js = JS.read_text(encoding="utf-8") if JS.is_file() else ""
    if "function woprNextAfflFppg" not in js:
        fail("players.js missing woprNextAfflFppg")
    if "function woprNflGames" not in js:
        fail("players.js missing woprNflGames")
    if not re.search(r"return\s+fp\s*/\s*games", js):
        fail("woprNextAfflFppg must return fp / games")
    if not re.search(r"pts\s*/\s*box\.games", js):
        fail("compare affl_fppg must use pts / box.games")
    # Must not define FPpG from AFFL starts alone
    bad = re.findall(
        r"fppg\s*=\s*[^;\n]*starts",
        js,
        flags=re.I,
    )
    if bad:
        fail(f"FPpG still derived from starts: {bad[:3]}")

    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    tucker = idx.get(TUCKER_PID) or {}
    if tucker.get("name") != "Tre Tucker":
        fail(f"expected Tre Tucker at {TUCKER_PID}, got {tucker.get('name')!r}")

    nfl = json.loads(NFL.read_text(encoding="utf-8"))
    rec = nfl.get(TUCKER_PID) or {}
    y2025 = rec.get("2025") or {}
    weeks = [k for k in y2025 if str(k).isdigit() and isinstance(y2025[k], dict)]
    if len(weeks) < 8:
        fail(f"Tucker 2025 NFL weeks {len(weeks)} < 8")
    pts = 0.0
    for wk in weeks:
        v = y2025[wk].get("pts")
        if v is not None:
            pts += float(v)
    games = len(weeks)
    fppg = pts / games if games else None
    if fppg is None:
        fail(f"Tucker FPpG missing: pts={pts} games={games}")
    elif fppg > 30:
        fail(f"Tucker FPpG absurd: pts={pts} games={games} fppg={fppg}")
    elif fppg < 2 or fppg > 15:
        fail(f"Tucker FPpG out of expected band: {fppg:.2f} (pts={pts}, g={games})")
    # Season total wearing FPpG label was ~104
    elif abs(fppg - pts) < 1e-6:
        fail("FPpG equals season points (denominator missing)")

    yd = json.loads(YEAR.read_text(encoding="utf-8"))
    pl = next((p for p in (yd.get("players") or []) if str(p.get("pid")) == TUCKER_PID), None)
    if not pl:
        fail("Tre Tucker missing from years/2025.json players")
    else:
        starts = pl.get("starts")
        if starts is not None and int(starts) <= 2 and fppg > 40:
            fail("would still look like starts-denominator bug")

    print(
        f"tucker_pid={TUCKER_PID} pts={pts:.1f} nfl_games={games} "
        f"fppg={fppg:.2f} affl_starts={pl.get('starts') if pl else None}"
    )

    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/players.html", timeout=5)
        code = getattr(r, "status", None) or r.getcode()
        if code != 200:
            fail(f"players.html HTTP {code}")
        else:
            print("players.html HTTP 200")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"players.html not reachable: {e}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-54: FPpG = AFFL/NFL pts ÷ NFL games; Tucker ~6.2 not ~104")
    return 0


if __name__ == "__main__":
    sys.exit(main())
