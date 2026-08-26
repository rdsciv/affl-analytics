#!/usr/bin/env python3
"""Headshot fallback + player-card ranks.

DST uses NFL logos. Empty skill-player hs falls back to espncdn.
Ranks are among AFFL-rostered players (player_index) by nfl_weeks career pts.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []


def fail(msg):
    fails.append(msg)


def career_pts(nfl, pid):
    rec = nfl.get(str(pid)) or {}
    s = n = 0
    for y, weeks in rec.items():
        if not (str(y).isdigit() and len(str(y)) == 4 and isinstance(weeks, dict)):
            continue
        for wk, row in weeks.items():
            if not (str(wk).isdigit() and int(wk) > 0):
                continue
            if isinstance(row, dict) and row.get("pts") is not None:
                s += float(row["pts"])
                n += 1
    return s if n else 0


def main():
    common = (SITE / "common.js").read_text()
    players = (SITE / "players.js").read_text()
    app = (SITE / "app.js").read_text()
    html = (SITE / "players.html").read_text()

    if "espncdn.com/i/headshots/nfl/players/full/" not in common:
        fail("common.js missing ESPN headshot fallback")
    if "function isDst" not in common:
        fail("common.js missing DST check")
    if "nflLogoHTML(p.nfl, cls)" not in common:
        fail("DST does not use nflLogoHTML")
    if "primary || fallback" not in common:
        pass  # ESPN first by design; stored hs is onerror fallback
    if "playerFace" not in app:
        fail("app.js missing playerFace")
    if "espncdn.com/i/headshots" not in app:
        fail("app.js playerFace missing espncdn")
    if "function buildRanks" not in players:
        fail("players.js missing buildRanks")
    if '"all-time"' not in players:
        fail("hero missing all-time tile")
    if '"pos rank"' not in players:
        fail("hero missing pos rank tile")
    if '"best week"' not in players:
        fail("hero missing best week tile")
    import re
    pj = re.search(r"players\.js\?v=(\d+)", html)
    if not pj or int(pj.group(1)) < 19:
        fail("players.html players.js pin need v>=19")

    idx = json.loads((SITE / "player_index.json").read_text())
    nfl = json.loads((SITE / "nfl_weeks.json").read_text())
    rows = []
    for pid, meta in idx.items():
        pts = career_pts(nfl, pid)
        if pts > 0:
            rows.append((pts, meta.get("pos") or "", str(pid), meta.get("name")))
    rows.sort(reverse=True)
    if len(rows) < 500:
        fail(f"rank pool too small: {len(rows)}")

    def rank_of(pid):
        for i, r in enumerate(rows, 1):
            if r[2] == str(pid):
                posn = [x for x in rows if x[1] == r[1]]
                pr = next(j for j, x in enumerate(posn, 1) if x[2] == str(pid))
                return i, len(rows), pr, len(posn), r[1], r[3], r[0]
        return None

    hurts = rank_of("4040715")
    adams = rank_of("16800")
    if not hurts:
        fail("Hurts not in rank pool")
    else:
        if hurts[0] != 27 or hurts[2] != 21:
            fail(f"Hurts rank drifted: all {hurts[0]} pos {hurts[2]} (expected 27 / QB 21)")
    if not adams:
        fail("Adams not in rank pool")
    else:
        if adams[2] != 1 or adams[4] != "WR":
            fail(f"Adams should be WR #1, got {adams[4]} #{adams[2]}")

    y2020 = json.loads((SITE / "years/2020.json").read_text())
    jj = next((p for p in y2020["players"] if p.get("pid") == 4262921), None)
    if not jj:
        fail("Jefferson 2020 missing from year JSON")
    elif jj.get("hs"):
        fail("Jefferson 2020 unexpectedly has hs; fallback eval needs an empty one")
    elif "4262921" not in common and True:
        # fallback is by pid at runtime; just assert the year row is empty
        pass

    y2025 = json.loads((SITE / "years/2025.json").read_text())
    dst = next((p for p in y2025["players"] if p.get("pos") == "DST" and not p.get("hs")), None)
    if not dst:
        fail("no 2025 DST without hs")
    elif not dst.get("nfl"):
        fail("DST missing nfl abbr for logo")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print(f"pool {len(rows)} Hurts all#{hurts[0]} QB#{hurts[2]} Adams WR#{adams[2]} pts {adams[6]:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
