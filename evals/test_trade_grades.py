#!/usr/bin/env python3
"""CHI-66 / AFFL-043: trade grades from weekly tid + trade log. No invented pre-2018."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PREVIEW = ROOT / "preview"
fails = []
fail = lambda m: fails.append(m)

BURROW_PID = 3915511
BIJAN_PID = 4430807
ACHANE_PID = 4429160
FAT_CATS = 2
SANCHITOS = 9


def after_start(player, tid, after_wk):
    pts = starts = 0
    weeks = []
    for row in player.get("wk") or []:
        if not row:
            continue
        week, fp, started, own = row[0], row[1] or 0, int(row[2] or 0), row[3]
        if week > after_wk and own == tid and started:
            pts += fp
            starts += 1
            weeks.append(week)
    return pts, starts, weeks


def grade_trades(yd, year):
    if year < 2018:
        return []
    players = {p["pid"]: p for p in (yd.get("players") or []) if p.get("pid") is not None}
    bases = {b["position"]: b["baseline"] for b in ((yd.get("draftValue") or {}).get("baselines") or []) if b.get("baseline") is not None}
    out = []
    for i, tr in enumerate(yd.get("trades") or []):
        wk = tr.get("wk")
        sides = []
        for s in tr.get("sides") or []:
            got, pts, par = [], 0.0, 0.0
            for g in s.get("got") or []:
                p = players.get(g.get("pid"))
                rec_pts, starts, _ = after_start(p, s.get("tid"), wk) if p else (0, 0, [])
                base = bases.get(p.get("pos")) if p else None
                weekly = (base / 17.0) if base is not None else 0
                gpar = rec_pts - weekly * starts if starts else 0
                pts += rec_pts
                par += gpar
                got.append({"pid": g.get("pid"), "name": (p or {}).get("name") or g.get("name"), "pts": rec_pts, "from": g.get("from")})
            sides.append({"tid": s.get("tid"), "got": got, "pts": pts, "par": par})
        if len(sides) < 2:
            continue
        total_pts = sum(s["pts"] for s in sides)
        total_par = sum(s["par"] for s in sides)
        for s in sides:
            s["netPts"] = s["pts"] - (total_pts - s["pts"])
            s["netPar"] = s["par"] - (total_par - s["par"])
        worst = min(sides, key=lambda s: s["netPts"])
        best = max(sides, key=lambda s: s["netPts"])
        out.append({"i": i, "wk": wk, "sides": sides, "worst": worst, "best": best})
    return out


def find_burrow_trade(yd):
    for i, tr in enumerate(yd.get("trades") or []):
        names = []
        for s in tr.get("sides") or []:
            for g in s.get("got") or []:
                names.append((s.get("tid"), g.get("pid"), g.get("name"), g.get("from")))
        if any(n[1] == BURROW_PID or (n[2] or "").find("Burrow") >= 0 for n in names):
            return tr, names
    return None, []


def main():
    js = (SITE / "wrapped.js").read_text()
    html = (SITE / "wrapped.html").read_text()
    common = (SITE / "common.js").read_text()
    y2025 = json.loads((SITE / "years" / "2025.json").read_text())
    data = json.loads((SITE / "data.json").read_text())
    teams = {t["id"]: t["name"] for t in ((data.get("seasons") or {}).get("2025") or {}).get("teams") or []}
    players = {p["pid"]: p for p in (y2025.get("players") or [])}

    if "gradeTrades" not in js:
        fail("wrapped.js missing gradeTrades")
    if "afterStart" not in common and "afterStart" not in js:
        fail("after-trade week walk missing")
    if "week >" not in common and "w.week > afterWk" not in common:
        fail("common.js afterStart does not use week > trade week")
    if 'id="wrap-trades-card"' not in html:
        fail("wrapped.html missing trade grades list")
    if "year < 2018" not in js:
        fail("wrapped.js does not gate trade grades at 2018")

    for year in (2014, 2015, 2016, 2017):
        d = json.loads((SITE / "years" / f"{year}.json").read_text())
        if d.get("trades"):
            fail(f"{year} year file invented trades")
        if grade_trades(d, year):
            fail(f"{year} produced trade grades")

    tr, names = find_burrow_trade(y2025)
    if not tr:
        fail("2025 Burrow trade missing from years/2025.json")
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1

    wk = tr.get("wk")
    print(f"Burrow trade week={wk}")
    if wk != 2:
        fail(f"Burrow trade week {wk} != 2 (from file)")

    got_by = {}
    for tid, pid, name, frm in names:
        got_by.setdefault(tid, []).append({"pid": pid, "name": name, "from": frm})
        print(f"  {teams.get(tid, tid)} (tid {tid}) got {name} from {teams.get(frm, frm)} (tid {frm})")

    fat_got = {g["pid"] for g in got_by.get(FAT_CATS, [])}
    san_got = {g["pid"] for g in got_by.get(SANCHITOS, [])}
    if BIJAN_PID not in fat_got:
        fail("Fat Cats did not receive Bijan Robinson in the Burrow trade")
    if BURROW_PID not in san_got:
        fail("Sanchitos did not receive Joe Burrow")
    if ACHANE_PID not in san_got:
        fail("Sanchitos did not receive De'Von Achane")
    if BURROW_PID in fat_got:
        fail("Fat Cats received Burrow — sides flipped")

    burrow = players[BURROW_PID]
    bijan = players[BIJAN_PID]
    achane = players[ACHANE_PID]
    b_pts, b_st, b_wks = after_start(burrow, SANCHITOS, wk)
    j_pts, j_st, j_wks = after_start(bijan, FAT_CATS, wk)
    a_pts, a_st, a_wks = after_start(achane, SANCHITOS, wk)
    print(f"after Wk {wk} started pts: Fat Cats Bijan={j_pts:.1f} wks={j_wks}")
    print(f"after Wk {wk} started pts: Sanchitos Burrow={b_pts:.1f} wks={b_wks}")
    print(f"after Wk {wk} started pts: Sanchitos Achane={a_pts:.1f} wks={a_wks}")

    if abs(j_pts - 35.2) > 0.15:
        fail(f"Bijan after-trade pts {j_pts} != 35.2 from weekly tid walk")
    if abs(b_pts - 0) > 0.05:
        fail(f"Burrow after-trade pts for Sanchitos {b_pts} != 0")
    if abs(a_pts - 224.1) > 0.15:
        fail(f"Achane after-trade pts {a_pts} != 224.1 from weekly tid walk")

    fat_net = j_pts - (b_pts + a_pts)
    san_net = (b_pts + a_pts) - j_pts
    print(f"Fat Cats net {fat_net:.1f} · Sanchitos net {san_net:.1f}")
    if fat_net >= 0:
        fail("Fat Cats net after Burrow trade is not negative")
    if abs(fat_net + 188.9) > 0.2:
        fail(f"Fat Cats net {fat_net} != -188.9")

    grades = grade_trades(y2025, 2025)
    if not grades:
        fail("no 2025 trade grades")
    burrow_g = None
    for g in grades:
        pids = [x["pid"] for s in g["sides"] for x in s["got"]]
        if BURROW_PID in pids:
            burrow_g = g
            break
    if not burrow_g:
        fail("Burrow trade missing from gradeTrades")
    else:
        fat = next(s for s in burrow_g["sides"] if s["tid"] == FAT_CATS)
        if abs(fat["netPts"] - fat_net) > 0.2:
            fail(f"graded Fat Cats net {fat['netPts']} != walk {fat_net}")

    # full-season totals must not be used as the after-trade number
    if abs((burrow.get("stPts") or 0) - b_pts) < 0.2:
        fail("Burrow after-trade pts equals full-season stPts — not a week walk")
    if abs((achane.get("stPts") or 0) - a_pts) < 0.2:
        fail("Achane after-trade pts equals full-season stPts — not a week walk")

    PREVIEW.mkdir(exist_ok=True)
    lines = [
        "# 2025 trade grades", "",
        "CHI-66 / AFFL-043. After-trade starter points = weeks after the deal, weekly tid = receiver, started only.",
        "",
        f"- Burrow trade: **Week {wk}**",
        f"- Fairview Fat Cats sent Joe Burrow + De'Von Achane, received Bijan Robinson",
        f"- Tijuana Sanchitos received Burrow + Achane",
        f"- After Wk {wk} starter pts: Bijan to Fat Cats **{j_pts:.1f}** · Burrow to Sanchitos **{b_pts:.1f}** · Achane to Sanchitos **{a_pts:.1f}**",
        f"- Fat Cats net **{fat_net:.1f}** starter pts",
        "",
        "```", "python3 evals/test_trade_grades.py", "```", "",
    ]
    (PREVIEW / "TRADE_GRADES.md").write_text("\n".join(lines))
    print(PREVIEW / "TRADE_GRADES.md")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-66: Burrow 2025 trade graded from weekly tid; no pre-2018 fiction")
    return 0


if __name__ == "__main__":
    sys.exit(main())
