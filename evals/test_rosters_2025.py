#!/usr/bin/env python3
"""CHI-32 / AFFL-012: weekly rosters, lineups, eligibility. 2018+ only."""
import sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"affl.db"; PREVIEW=ROOT/"preview"
fails=[]; fail=lambda m: fails.append(m)

def main():
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
    n2025=con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=2025").fetchone()[0]
    started=con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=2025 AND started=1").fetchone()[0]
    print(f"2025 roster-weeks={n2025} started={started}")
    if n2025<3000: fail(f"2025 roster weeks {n2025} too low")
    # 2014-2017 hold recovered STARTERS. A bench row here means something loaded a
    # roster ESPN never returned, or the snapshot leaked out of
    # fact_roster_snapshot_pre2018 - either way the grain is wrong. See CONTRACTS.md.
    pre=0
    for y in range(2014,2018):
        n=con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=?", (y,)).fetchone()[0]
        bench=con.execute("SELECT COUNT(*) FROM fact_roster_week WHERE season=? AND started=0", (y,)).fetchone()[0]
        if not n: fail(f"{y} has no roster weeks — the recovered starters were lost")
        if bench: fail(f"{y} has {bench} bench row(s) — pre-2018 is starters-only")
        pre+=n
    print(f"2014-2017 recovered starters={pre} (starters-only)")
    # every 2025 regular matchup side has starters
    miss=con.execute("""
        SELECT COUNT(*) FROM fact_matchup m
        WHERE m.season=2025 AND m.is_playoff=0
          AND NOT EXISTS (SELECT 1 FROM fact_roster_week r
                           WHERE r.season=m.season AND r.week=m.week
                             AND r.team_id=m.team_id AND r.started=1)
    """).fetchone()[0]
    if miss: fail(f"{miss} regular sides have no starters")
    slots=list(con.execute("SELECT slot, started, COUNT(*) n FROM fact_roster_week WHERE season=2025 GROUP BY slot, started ORDER BY 1,2"))
    PREVIEW.mkdir(exist_ok=True)
    lines=["# 2025 weekly rosters","", "CHI-32 / AFFL-012. `fact_roster_week` 2018–2025 full rosters; 2014–2017 recovered starters only.","",
           f"- 2025 rows: **{n2025}**","- Started: **{started}**","- Regular sides missing starters: **{miss}**","",
           "| slot | started | n |","| --- | --- | --- |"]
    for r in slots:
        lines.append(f"| {r['slot']} | {r['started']} | {r['n']} |")
    lines += ["","```","python3 evals/test_rosters_2025.py","```",""]
    (PREVIEW/"ROSTERS.md").write_text("\n".join(lines))
    print(PREVIEW/"ROSTERS.md")
    if fails:
        print("FAIL"); [print(" -",f) for f in fails]; return 1
    print("PASS"); print("CHI-32: 2025 lineups present; 2014-2017 starters-only"); return 0
if __name__=="__main__":
    sys.exit(main())
