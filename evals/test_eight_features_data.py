#!/usr/bin/env python3
"""Eight-feature JSON contract: keys, Feelers 2025, 2014 nulls, WOPR bounds."""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DB = ROOT / "affl.db"
fails = []
fail = lambda m: fails.append(m)

YEAR_KEYS = ("receivingUsage", "trophies", "luckCard", "auctionDna", "awards", "w1Acquired")
TROPHY_KEYS = ("h2hChampionTid", "medianChampionTid", "allPlayChampionTid", "rotoChampionTid")
LUCK_KEYS = ("tid", "actualW", "actualL", "pf", "allPlayW", "allPlayL", "allPlayPct",
             "medianW", "medianL", "expectedWins", "scheduleLuckWins")
USAGE_KEYS = ("pid", "name", "pos", "nfl", "tgtShare", "airYardsShare", "wopr",
              "adot", "racr", "xfp", "fp", "xtd", "td")


def main():
    y25 = json.loads((SITE / "years/2025.json").read_text())
    y14 = json.loads((SITE / "years/2014.json").read_text())
    bio = json.loads((SITE / "player_bio.json").read_text())
    miles = json.loads((SITE / "miles.json").read_text()) if (SITE / "miles.json").exists() else {}

    for k in YEAR_KEYS:
        if k not in y25:
            fail(f"2025 missing {k}")

    trophies = y25.get("trophies") or {}
    for k in TROPHY_KEYS:
        if k not in trophies:
            fail(f"2025 trophies missing {k}")

    luck = y25.get("luckCard") or []
    feel = next((r for r in luck if r.get("tid") == 7), None)
    if not feel:
        fail("Feelers tid 7 missing from 2025 luckCard")
    elif any(k not in feel for k in LUCK_KEYS):
        fail(f"Feelers luckCard missing keys { [k for k in LUCK_KEYS if k not in feel] }")

    dna = y25.get("auctionDna") or []
    if not any(r.get("tid") == 7 for r in dna):
        fail("Feelers tid 7 missing from 2025 auctionDna")

    awards = y25.get("awards") or {}
    for side in ("allLeague", "bushLeague"):
        rows = awards.get(side) or []
        if not any(r.get("tid") == 7 for r in rows):
            fail(f"Feelers tid 7 missing from 2025 awards.{side}")

    w1 = y25.get("w1Acquired") or []
    if not any(r.get("tid") == 7 for r in w1):
        fail("Feelers tid 7 missing from 2025 w1Acquired")

    usage = y25.get("receivingUsage") or y25.get("opportunity") or []
    if not usage:
        fail("2025 receivingUsage/opportunity empty")
    for row in usage:
        for k in USAGE_KEYS:
            if k not in row:
                fail(f"usage row missing {k}")
                break
        w = row.get("wopr")
        if w is not None and not (0 <= w <= 2.5):
            fail(f"WOPR out of range {row.get('name')} {w}")

    # 2014: no weekly custody / w1 / awards; snake so no auction DNA
    if y14.get("custody") is not None:
        fail("2014 custody should be null/absent")
    if y14.get("w1Acquired") not in (None, []):
        fail("2014 w1Acquired should be null or absent")
    if y14.get("awards") not in (None, {}):
        fail("2014 awards should be null or absent")
    if y14.get("auctionDna") is not None:
        fail("2014 auctionDna should be null")
    if y14.get("receivingUsage") not in (None, []):
        fail("2014 receivingUsage should be null or absent")

    # no Unknown acquisition
    c25 = y25.get("custody") or {}
    for t in c25.get("teams") or []:
        if (t.get("ptsUnknown") or 0) != 0:
            fail(f"Unknown pts on tid {t.get('tid')}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    unk = con.execute("""
        SELECT COUNT(*) FROM fact_player_week_par
         WHERE season BETWEEN 2018 AND 2025
           AND acquisition NOT IN ('Drafted','Traded in','Waiver','FA')""").fetchone()[0]
    if unk:
        fail(f"{unk} residual unknown player-weeks")

    josh = bio.get("3918298") or {}
    if josh.get("college") != "Wyoming":
        fail(f"Josh Allen college {josh.get('college')}")
    if josh.get("draftPick") != 7 or josh.get("draftRound") != 1:
        fail(f"Josh Allen draft {josh.get('draftRound')}/{josh.get('draftPick')}")
    if josh.get("draftTeam") != "BUF" or josh.get("draftYear") != 2018:
        fail(f"Josh Allen draft team/year {josh.get('draftTeam')} {josh.get('draftYear')}")
    if "breakoutAge" not in josh:
        fail("player_bio missing breakoutAge key")

    if not miles:
        fail("site/miles.json missing")

    print("FAIL" if fails else "PASS")
    for f in fails:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
