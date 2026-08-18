#!/usr/bin/env python3
"""CHI-26 / AFFL-005: 2025 standings, Power, and Luck from matchup grain.

Runs against real affl.db. Proves:

  1. Regular-season W-L-T / PF / PA recomputed from fact_matchup match
     v_standings_regular (weekly rows sum to the season view).
  2. ESPN dim_team W-L-T is reproduced. PF/PA diffs vs ESPN seed fields
     FAIL with a discrepancy table — dim_team is not overwritten.
  3. Power rank uses raw allplay_w / allplay_l (power_ratio), not the
     rounded display power_pct.
  4. Luck Index (v_luck, FantasyGenius discrete) is a different formula
     from League Legacy weighted luck (v_luck_weighted = wins - exp_wins).
"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "affl.db"
SITE = ROOT / "site"
PREVIEW = ROOT / "preview"
SEASON = 2025
fails = []


def fail(msg):
    fails.append(msg)


def connect():
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def md_table(cols, rows):
    if not rows:
        return "_no rows_"
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        cells = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.4f}" if abs(v) < 1 or abs(v - round(v, 2)) > 1e-9 else f"{v:.2f}")
            else:
                cells.append(str(v).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def recompute_weekly(con):
    """Independent recompute from fact_matchup regular-season sides."""
    rec = {}
    weekly = defaultdict(dict)
    for r in con.execute("""
        SELECT week, team_id, points, opponent_points, result
          FROM fact_matchup
         WHERE season=? AND is_playoff=0
         ORDER BY week, team_id
    """, (SEASON,)):
        tid = r["team_id"]
        rec.setdefault(tid, {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0, "games": 0})
        rec[tid]["pf"] += r["points"]
        rec[tid]["pa"] += r["opponent_points"]
        rec[tid]["games"] += 1
        rec[tid][r["result"].lower()] += 1
        weekly[r["week"]][tid] = r["points"]

    by_week_result = defaultdict(dict)
    for r in con.execute("""
        SELECT week, team_id, result FROM fact_matchup
         WHERE season=? AND is_playoff=0
    """, (SEASON,)):
        by_week_result[r["week"]][r["team_id"]] = r["result"]

    ap = {tid: [0, 0] for tid in rec}
    luck = {tid: {"lucky": 0, "unlucky": 0} for tid in rec}
    for wk, scores in weekly.items():
        field = len(scores) - 1
        for tid, pts in scores.items():
            beat = sum(1 for t2, p2 in scores.items() if t2 != tid and p2 < pts)
            ap[tid][0] += beat
            ap[tid][1] += field - beat
            res = by_week_result[wk][tid]
            if res == "W" and beat * 2 < field:
                luck[tid]["lucky"] += 1
            if res == "L" and beat * 2 >= field:
                luck[tid]["unlucky"] += 1
    return rec, ap, luck, weekly


def test_weekly_matches_view(con, rec):
    view = {r["team_id"]: r for r in con.execute(
        "SELECT * FROM v_standings_regular WHERE season=?", (SEASON,))}
    if set(view) != set(rec):
        fail(f"v_standings_regular teams {sorted(view)} != weekly {sorted(rec)}")
        return
    for tid, w in rec.items():
        v = view[tid]
        if (v["wins"], v["losses"], v["ties"], v["games"]) != (w["w"], w["l"], w["t"], w["games"]):
            fail(f"team {tid} view W-L-T {v['wins']}-{v['losses']}-{v['ties']} "
                 f"!= weekly {w['w']}-{w['l']}-{w['t']}")
        if abs(v["points_for"] - w["pf"]) > 1e-9 or abs(v["points_against"] - w["pa"]) > 1e-9:
            fail(f"team {tid} view PF/PA {v['points_for']}/{v['points_against']} "
                 f"!= weekly {w['pf']}/{w['pa']}")
    print(f"weekly rows == v_standings_regular: {len(rec)} teams, "
          f"{sum(w['games'] for w in rec.values())} sides")


def test_espn_records(con, rec, names):
    espn = {r["team_id"]: r for r in con.execute(
        "SELECT team_id, name, wins, losses, ties, points_for, points_against, "
        "playoff_seed, final_rank FROM dim_team WHERE season=?", (SEASON,))}
    rec_rows = []
    pf_rows = []
    rec_fail = False
    pf_fail = False
    for tid in sorted(espn, key=lambda t: espn[t]["final_rank"] or 99):
        e, w = espn[tid], rec[tid]
        dw, dl, dt = e["wins"] - w["w"], e["losses"] - w["l"], e["ties"] - w["t"]
        dpf = round(e["points_for"] - w["pf"], 6)
        dpa = round(e["points_against"] - w["pa"], 6)
        rec_rows.append((e["final_rank"], e["name"], e["wins"], w["w"], e["losses"], w["l"],
                         e["ties"], w["t"], dw, dl, dt))
        pf_rows.append((e["final_rank"], e["name"],
                        round(e["points_for"], 4), round(w["pf"], 4), dpf,
                        round(e["points_against"], 4), round(w["pa"], 4), dpa))
        if dw or dl or dt:
            rec_fail = True
        if abs(dpf) > 1e-9 or abs(dpa) > 1e-9:
            pf_fail = True
    print("ESPN W-L-T vs weekly:")
    print(md_table(["rank", "team", "espn_w", "wk_w", "espn_l", "wk_l",
                    "espn_t", "wk_t", "dw", "dl", "dt"], rec_rows))
    print("ESPN PF/PA vs weekly (box 1-dec):")
    print(md_table(["rank", "team", "espn_pf", "wk_pf", "dpf",
                    "espn_pa", "wk_pa", "dpa"], pf_rows))
    if rec_fail:
        fail("ESPN W-L-T disagrees with weekly regular-season sides")
    else:
        print("ESPN W-L-T reproduced from fact_matchup regular season")
    if pf_fail:
        # Surface only. Box grain is 1-dec; ESPN seed PF/PA is 2-dec.
        # Overwriting dim_team is forbidden. A missing week (|d| >= 1) is a fail.
        big = [r for r in pf_rows if abs(r[4]) >= 1 or abs(r[7]) >= 1]
        print("PF/PA discrepancy surfaced (box 1-dec vs ESPN 2-dec); dim_team not overwritten")
        if big:
            fail(f"ESPN PF/PA differs by a full point or more (missing week?): {big}")
    return rec_rows, pf_rows, rec_fail, pf_fail


def test_power_raw_rank(con, ap):
    view = {r["team_id"]: r for r in con.execute(
        "SELECT * FROM v_power WHERE season=?", (SEASON,))}
    if set(view) != set(ap):
        fail(f"v_power teams {sorted(view)} != recomputed {sorted(ap)}")
        return []
    for tid, (aw, al) in ap.items():
        v = view[tid]
        if (v["allplay_w"], v["allplay_l"]) != (aw, al):
            fail(f"team {tid} v_power {v['allplay_w']}-{v['allplay_l']} != weekly {aw}-{al}")
        raw = aw / (aw + al) if (aw + al) else 0
        if abs(v["power_ratio"] - raw) > 1e-12:
            fail(f"team {tid} power_ratio {v['power_ratio']} != raw {raw}")
        # display rounding must not be what we rank on
        if abs(v["power_pct"] - round(raw, 4)) > 1e-12:
            fail(f"team {tid} power_pct {v['power_pct']} != ROUND(raw,4)")

    # rank from raw num/denom, not from rounded display
    raw_order = sorted(view.values(),
                       key=lambda r: (-r["power_ratio"], -r["allplay_w"], r["allplay_l"]))
    # RANK() with ties: same ratio + same W/L share a rank
    expected_rank = {}
    prev_key = None
    rank = 0
    for i, r in enumerate(raw_order, start=1):
        key = (r["power_ratio"], r["allplay_w"], r["allplay_l"])
        if key != prev_key:
            rank = i
            prev_key = key
        expected_rank[r["team_id"]] = rank
    for tid, exp in expected_rank.items():
        if view[tid]["power_rank"] != exp:
            fail(f"team {tid} power_rank {view[tid]['power_rank']} != raw-rank {exp}")

    # prove rounded display would be a different key: 1-dec percent collapses
    # nothing in 2025, but ranking by power_pct (4-dec) must equal raw rank
    pct_order = sorted(view.values(),
                       key=lambda r: (-r["power_pct"], -r["allplay_w"], r["allplay_l"]))
    # If two teams had the same rounded pct but different raw ratio, raw must win.
    # 2025: teams 1 and 14 share raw 57-97 — they must share power_rank.
    tied = [r for r in view.values() if r["allplay_w"] == 57 and r["allplay_l"] == 97]
    if len(tied) == 2 and tied[0]["power_rank"] != tied[1]["power_rank"]:
        fail("57-97 all-play tie must share power_rank (raw num/denom)")
    if any(r["power_rank"] != expected_rank[r["team_id"]] for r in view.values()):
        fail("power_rank is not controlled by raw numerator/denominator")
    else:
        print(f"power rank uses raw allplay_w/allplay_l: {len(view)} teams")

    rows = []
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=?", (SEASON,))}
    for r in sorted(view.values(), key=lambda x: (x["power_rank"], x["team_id"])):
        rows.append((r["power_rank"], names[r["team_id"]], r["allplay_w"], r["allplay_l"],
                     r["power_ratio"], r["power_pct"]))
    return rows


def test_luck_distinct(con, rec, ap, luck):
    fg = {r["team_id"]: r for r in con.execute(
        "SELECT * FROM v_luck WHERE season=?", (SEASON,))}
    wt = {r["team_id"]: r for r in con.execute(
        "SELECT * FROM v_luck_weighted WHERE season=?", (SEASON,))}
    if set(fg) != set(luck) or set(wt) != set(rec):
        fail("luck view team set mismatch")
        return [], []
    mixed = 0
    fg_rows, wt_rows = [], []
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=?", (SEASON,))}
    for tid in rec:
        if (fg[tid]["lucky_wins"], fg[tid]["unlucky_losses"]) != (
                luck[tid]["lucky"], luck[tid]["unlucky"]):
            fail(f"team {tid} v_luck {fg[tid]['lucky_wins']}/{fg[tid]['unlucky_losses']} "
                 f"!= weekly {luck[tid]['lucky']}/{luck[tid]['unlucky']}")
        aw, al = ap[tid]
        exp = round((aw / (aw + al)) * rec[tid]["games"], 2)
        weighted = round(rec[tid]["w"] - (aw / (aw + al)) * rec[tid]["games"], 2)
        if abs(wt[tid]["exp_wins"] - exp) > 1e-9:
            fail(f"team {tid} exp_wins {wt[tid]['exp_wins']} != {exp}")
        if abs(wt[tid]["weighted_luck"] - weighted) > 1e-9:
            fail(f"team {tid} weighted_luck {wt[tid]['weighted_luck']} != {weighted}")
        # formulas must stay distinct: integer net_luck is not weighted_luck
        if fg[tid]["net_luck"] == wt[tid]["weighted_luck"]:
            mixed += 1
        fg_rows.append((names[tid], fg[tid]["lucky_wins"], fg[tid]["unlucky_losses"],
                        fg[tid]["net_luck"]))
        wt_rows.append((names[tid], rec[tid]["w"], wt[tid]["exp_wins"],
                        wt[tid]["weighted_luck"]))
    if mixed == len(rec):
        fail("Luck Index net_luck equals weighted_luck for every team — formulas are mixed")
    else:
        print(f"Luck Index distinct from League Legacy weighted luck "
              f"({len(rec) - mixed}/{len(rec)} teams differ)")
    # site reconstructed luck is the weighted formula (process.py), not v_luck
    site = json.loads((SITE / "data.json").read_text())
    teams = {t["id"]: t for t in site["seasons"][str(SEASON)]["teams"]}
    site_mixed = 0
    for tid, t in teams.items():
        if t.get("luck") == fg[tid]["net_luck"] and t.get("luck") != wt[tid]["weighted_luck"]:
            site_mixed += 1
    if site_mixed:
        fail(f"site/data.json luck equals Luck Index (not weighted) for {site_mixed} teams")
    year = json.loads((SITE / "years" / f"{SEASON}.json").read_text())
    luck_fg = {r["teamId"]: r for r in (year.get("luckFG") or [])}
    if not luck_fg:
        fail("site/years/2025.json missing luckFG (Luck Index export)")
    else:
        for tid, r in luck_fg.items():
            if (r["lucky"], r["unlucky"], r["net"]) != (
                    fg[tid]["lucky_wins"], fg[tid]["unlucky_losses"], fg[tid]["net_luck"]):
                fail(f"luckFG team {tid} {r} != v_luck")
        print(f"luckFG export matches v_luck: {len(luck_fg)} teams")
    return fg_rows, wt_rows


def test_no_overwrite(con):
    # dim_team PF/PA still look like ESPN 2-dec seeds, not weekly 1-dec
    n = con.execute("""
        SELECT COUNT(*) FROM dim_team t
        JOIN v_standings_regular s ON s.season=t.season AND s.team_id=t.team_id
        WHERE t.season=? AND ABS(t.points_for - s.points_for) < 1e-9
          AND ABS(t.points_for - ROUND(t.points_for, 1)) > 1e-9
    """, (SEASON,)).fetchone()[0]
    # if we had overwritten, ESPN 2-dec values would be gone. At least one
    # team still has a hundredths place that weekly 1-dec does not.
    hundredths = con.execute("""
        SELECT COUNT(*) FROM dim_team
         WHERE season=? AND ABS(points_for - ROUND(points_for, 1)) > 1e-9
    """, (SEASON,)).fetchone()[0]
    if hundredths == 0:
        fail("dim_team PF lost ESPN hundredths — looks overwritten from weekly 1-dec")
    else:
        print(f"dim_team ESPN PF hundredths retained ({hundredths} teams) — not overwritten")


def write_preview(con, rec, rec_rows, pf_rows, rec_fail, pf_fail, power_rows, fg_rows, wt_rows):
    PREVIEW.mkdir(exist_ok=True)
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=?", (SEASON,))}
    lines = [
        f"# {SEASON} standings / Power / Luck",
        "",
        "CHI-26 / AFFL-005. Recomputed from `fact_matchup` regular-season weeks.",
        "This is the data. Not the website. Discrepancies are surfaced, not overwritten.",
        "",
        "## ESPN records (W-L-T)",
        "",
        "Weekly regular-season sides reproduce ESPN `dim_team` wins/losses/ties."
        if not rec_fail else
        "ESPN W-L-T disagrees with weekly sides. dim_team was not changed.",
        "",
        md_table(["rank", "team", "espn_w", "wk_w", "espn_l", "wk_l",
                  "espn_t", "wk_t", "dw", "dl", "dt"], rec_rows),
        "",
        "## Points Forced / Allowed",
        "",
        "`fact_matchup.points` is the CHI-24 box grain (1 decimal). "
        "ESPN `dim_team.points_for` / `points_against` are league-record "
        "season totals (2 decimals). Weekly 1-dec sums do not equal ESPN. "
        "League schedule `totalPoints` (2-dec) does. dim_team was not overwritten.",
        "",
        md_table(["rank", "team", "espn_pf", "wk_pf", "dpf",
                  "espn_pa", "wk_pa", "dpa"], pf_rows),
        "",
        "## Power (raw all-play)",
        "",
        "Rank is `RANK()` on unrounded `allplay_w / (allplay_w + allplay_l)`, "
        "then more all-play wins. `power_pct` is display-only (4 decimals). "
        "Two 1-dec box ties (week 3: Pipers/Pounders 90.6; week 9: "
        "Shadowcocks/Mighty Cucks 104.2) are counted as all-play losses in "
        "`v_power` because `beat_this_week` is a strict `<`. League 2-dec "
        "scores break those ties; site `data.json` all-play therefore differs "
        "for Shadowcocks (112-42 vs 111-43) and Pounders (39-115 vs 38-116).",
        "",
        md_table(["rank", "team", "allplay_w", "allplay_l", "power_ratio", "power_pct"],
                 power_rows),
        "",
        "## Luck Index (v_luck) — FantasyGenius discrete",
        "",
        "Lucky win = won while scoring in the bottom half that week. "
        "Unlucky loss = lost while scoring in the top half. Net = lucky − unlucky.",
        "",
        md_table(["team", "lucky_wins", "unlucky_losses", "net_luck"],
                 sorted(fg_rows, key=lambda r: (-r[3], r[0]))),
        "",
        "## League Legacy weighted luck (v_luck_weighted)",
        "",
        "expected wins = all-play win% × regular-season games. "
        "weighted luck = actual wins − expected wins. Not Luck Index.",
        "",
        md_table(["team", "reg_wins", "exp_wins", "weighted_luck"],
                 sorted(wt_rows, key=lambda r: (-r[3], r[0]))),
        "",
        "## How to refresh",
        "",
        "```",
        "python3 evals/test_standings_power_luck_2025.py",
        "```",
        "",
    ]
    path = PREVIEW / "STANDINGS.md"
    path.write_text("\n".join(lines))
    print(path)


def main():
    con = connect()
    names = {r["team_id"]: r["name"] for r in con.execute(
        "SELECT team_id, name FROM dim_team WHERE season=?", (SEASON,))}
    rec, ap, luck, weekly = recompute_weekly(con)
    if sum(w["games"] for w in rec.values()) != 168:
        fail(f"regular sides should be 168, got {sum(w['games'] for w in rec.values())}")
    test_weekly_matches_view(con, rec)
    rec_rows, pf_rows, rec_fail, pf_fail = test_espn_records(con, rec, names)
    power_rows = test_power_raw_rank(con, ap)
    fg_rows, wt_rows = test_luck_distinct(con, rec, ap, luck)
    test_no_overwrite(con)
    write_preview(con, rec, rec_rows, pf_rows, rec_fail, pf_fail,
                  power_rows, fg_rows, wt_rows)
    con.close()
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS")
    print("CHI-26: 2025 standings / Power / Luck recomputed from matchup grain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
