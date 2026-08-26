#!/usr/bin/env python3
"""Extract ESPN transactionCounter from data/league_YYYY.json.

teams[].transactionCounter.acquisitions is ESPN's ACQ / MOVES column
(verified against the 2014 standings screenshot and 2019 Feelers).

Writes site/moves.json keyed by year then team id:
  {
    "2014": {
      "7": {
        "moves": 27,
        "drops": 26,
        "trades": 3,
        "moveToActive": 88,
        "ir": 0,
        "misc": 0,
        "byWeek": {"1": 0, "2": 1, ...}
      }
    }
  }

byWeek is matchupAcquisitionTotals (weekly add volume, no player names).
ir is moveToIR. Do not include LOSS (matchup losses) or ENTRY (buy-in).

Re-run this script; do not hand-edit the JSON.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
YEARS = list(range(2014, 2026))


def load_json(path):
    with open(path) as f:
        return json.load(f)


def extract_year(year):
    path = os.path.join(DATA, f"league_{year}.json")
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}")
    league = load_json(path)
    out = {}
    for t in league.get("teams") or []:
        tid = t.get("id")
        if tid is None:
            continue
        tc = t.get("transactionCounter") or {}
        mat = tc.get("matchupAcquisitionTotals") or {}
        by_week = {str(k): int(v or 0) for k, v in mat.items()}
        rec = {
            "moves": int(tc.get("acquisitions") or 0),
            "drops": int(tc.get("drops") or 0),
            "trades": int(tc.get("trades") or 0),
            "moveToActive": int(tc.get("moveToActive") or 0),
            "ir": int(tc.get("moveToIR") or 0),
            "misc": int(tc.get("misc") or 0),
            "byWeek": by_week,
        }
        out[str(int(tid))] = rec
    return out


def extract():
    bag = {}
    for year in YEARS:
        bag[str(year)] = extract_year(year)
    dest = os.path.join(SITE, "moves.json")
    with open(dest, "w") as f:
        json.dump(bag, f, indent=2)
        f.write("\n")
    return bag, dest


def main():
    bag, dest = extract()
    y2014 = bag["2014"]
    y2019 = bag["2019"]
    print(f"wrote {dest}")
    print(f"years={len(bag)} teams_2014={len(y2014)}")
    print(
        f"2014 tid 7 Feelers moves={y2014['7']['moves']} drops={y2014['7']['drops']} "
        f"trades={y2014['7']['trades']} moveToActive={y2014['7']['moveToActive']}"
    )
    print(
        f"2019 tid 7 Feelers moves={y2019['7']['moves']} drops={y2019['7']['drops']} "
        f"trades={y2019['7']['trades']} moveToActive={y2019['7']['moveToActive']} "
        f"ir={y2019['7']['ir']} misc={y2019['7']['misc']}"
    )
    print(f"2014 tid 4 Thunder moves={y2014['4']['moves']}")
    print(f"2014 tid 10 Horndogs moves={y2014['10']['moves']}")


if __name__ == "__main__":
    main()
