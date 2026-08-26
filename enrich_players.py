#!/usr/bin/env python3
"""Patch year player payloads with xTD + Spotrac cap, and write player_index.json.

Totals are computed from affl.db. Nothing is hardcoded.
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "affl.db")
YEARS = os.path.join(HERE, "site", "years")
INDEX = os.path.join(HERE, "site", "player_index.json")


def money(n):
    if n is None:
        return None
    return float(n)


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    xtd_week = {}
    for r in con.execute(
        "SELECT season, week, player_id, actual_td, xtd, residual FROM fact_xtd_player_week"
    ):
        xtd_week[(r["season"], r["week"], r["player_id"])] = (
            r["actual_td"], r["xtd"], r["residual"]
        )

    xtd_season = {}
    for r in con.execute(
        "SELECT season, player_id, actual_td, xtd, residual FROM v_xtd_player_season"
    ):
        xtd_season[(r["season"], r["player_id"])] = {
            "td": r["actual_td"], "xtd": r["xtd"], "res": r["residual"]
        }

    # Spotrac annual cap. Prefer ESPN id; fall back to exact name.
    name_to_pid = {r["name"].lower(): r["player_id"]
                   for r in con.execute("SELECT player_id, name FROM dim_player")}
    cap_by_pid = {}
    for r in con.execute(
        """SELECT season, nfl_team, player_name, player_id, position,
                  cap_hit, base_salary, signing_bonus, dead_cap, cap_pct
             FROM fact_cap_hit"""
    ):
        pid = r["player_id"] or name_to_pid.get((r["player_name"] or "").lower())
        if not pid:
            continue
        cap_by_pid.setdefault(pid, []).append({
            "season": r["season"],
            "nfl": r["nfl_team"],
            "hit": money(r["cap_hit"]),
            "base": money(r["base_salary"]),
            "bonus": money(r["signing_bonus"]),
            "dead": money(r["dead_cap"]),
            "pct": money(r["cap_pct"]),
        })
    for pid in cap_by_pid:
        cap_by_pid[pid].sort(key=lambda x: (x["season"], x["nfl"] or ""))

    gsis_of = {r["player_id"]: r["gsis_id"]
               for r in con.execute("SELECT player_id, gsis_id FROM dim_player WHERE gsis_id IS NOT NULL")}
    contracts_by_gsis = {}
    for r in con.execute(
        """SELECT gsis_id, player_name, year_signed, years, value, apy,
                  guaranteed, nfl_team, is_active
             FROM fact_contract WHERE gsis_id IS NOT NULL
             ORDER BY year_signed"""
    ):
        contracts_by_gsis.setdefault(r["gsis_id"], []).append({
            "signed": r["year_signed"],
            "years": r["years"],
            "value": money(r["value"]),
            "apy": money(r["apy"]),
            "gtd": money(r["guaranteed"]),
            "nfl": r["nfl_team"],
            "active": int(r["is_active"] or 0),
        })

    roster_years = {}
    for season, pid in con.execute(
        "SELECT DISTINCT season, player_id FROM fact_roster_week"
    ):
        roster_years.setdefault(pid, []).append(season)
    for pid in roster_years:
        roster_years[pid].sort()

    names = {r["player_id"]: (r["name"], r["position"])
             for r in con.execute("SELECT player_id, name, position FROM dim_player")}

    year_files = sorted(
        f for f in os.listdir(YEARS) if f.endswith(".json") and f[:4].isdigit()
    )
    patched = 0
    for fn in year_files:
        year = int(fn[:4])
        path = os.path.join(YEARS, fn)
        bundle = json.load(open(path))
        players = bundle.get("players") or []
        for p in players:
            pid = p["pid"]
            for w in p.get("wk") or []:
                # keep first 10 columns; append xtd + residual
                key = (year, w[0], pid)
                row = xtd_week.get(key)
                xtd = round(row[1], 2) if row else None
                res = round(row[2], 2) if row else None
                p_wk = list(w[:10])
                while len(p_wk) < 10:
                    p_wk.append(None)
                p_wk.extend([xtd, res])
                w[:] = p_wk
            xs = xtd_season.get((year, pid))
            p["xtd"] = xs["xtd"] if xs else None
            p["xtdRes"] = xs["res"] if xs else None
            p["nflTd"] = xs["td"] if xs else None
            p["cap"] = [c for c in cap_by_pid.get(pid, []) if c["season"] == year]
            p["contracts"] = contracts_by_gsis.get(gsis_of.get(pid), [])
        json.dump(bundle, open(path, "w"), separators=(",", ":"))
        patched += 1
        print(f"  {year}: {len(players)} players")

    index = {}
    pids = set(roster_years)
    for pid in pids:
        name, pos = names.get(pid, (f"#{pid}", "?"))
        xs = {str(s): v for (s, p), v in xtd_season.items() if p == pid}
        index[str(pid)] = {
            "name": name,
            "pos": pos,
            "years": roster_years.get(pid, []),
            "xtd": xs,
            "cap": cap_by_pid.get(pid, []),
            "contracts": contracts_by_gsis.get(gsis_of.get(pid), []),
        }
    json.dump(index, open(INDEX, "w"), separators=(",", ":"))
    print(f"player_index.json: {len(index)} players · {patched} year files")


if __name__ == "__main__":
    main()
