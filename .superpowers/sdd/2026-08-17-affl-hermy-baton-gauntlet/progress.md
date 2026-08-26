# SDD ledger — plan: docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md

Branch: AFFL_Hermy_Baton @ 58176a905b40acc649234d3de63e8778f1f6a11b
Worktree: /Users/chilly/Projects/ccDesktopAFFL (same as verify/full-audit; no new worktree)
Server: http://127.0.0.1:8765/ cwd=/Users/chilly/Projects/ccDesktopAFFL/site → HTTP 200
Linear API: unavailable this bootstrap (no LINEAR_API_KEY; Composio Linear failed)
Dirty tree: preserved (extensive M + ?? files untouched)

## Baseline evals (2026-08-17 Hermy bootstrap)

- `python3 evals/test_handoff.py` → **PASS** (START-HERE 293 lines)
- `python3 evals/test_warehouse_2026.py` → **FAIL**
  - dim_season missing 2026
  - 2026 team count 0 != 12
  - Gabagooners / Kafka m07 not in 2026 teams
  - Interpretation: FAIL is **correct under CHI-75**; eval still encodes rejected CHI-72 Phase A stub

## Warehouse snapshot (read-only)

- dim_season: 2014–2025 only (12)
- dim_team 2026: 0
- fact_trade: 392
- Sidecars missing: fact_ngs, dim_player_bio, fact_injury, fact_depthchart, fact_college, fact_player_overview

## Artifacts written this bootstrap

- research/2026-08-17_hermy-baton-deep-research.md
- docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md
- skill: affl-hermy-baton (/affl-gauntlet)

## Task status

- Task 0 bootstrap: complete
- Task 1 CHI-75: complete
- Task 2 CHI-72 honesty: complete
- Task 3 CHI-54 FPpG: **complete** (2026-08-17)
  - Code already used NFL games; locked with evals/test_fppg.py
  - Tucker 4428718: 104.7 pts / 17 NFL games = 6.16 FPpG (1 AFFL start)
  - PASS test_fppg, test_player_fg, test_player_charts
  - URL http://127.0.0.1:8765/players.html 200
- Task 4 CHI-45 trade join: **complete** (verify)
  - test_trade_builder_join PASS; Fitz/Bernard two-sided; test_trades_2025 PASS; test_trade_grid PASS (309 deals, feelers_skinners 20)
  - URL http://127.0.0.1:8765/trades.html 200
- Wave C verify fixes:
  - styles.css .site-nav first rule now includes flex-wrap (dictionary eval)
  - eval floors for history/draft cache pins
  - nav_gates franchises >=19 + m22/m07
- Task 5 Wave C: partial (mechanical eval greens)
- Task CHI-89 Elo + Milestones: **complete** (local)
  - scripts/compute_milestones_elo.py → site/elo.json + site/milestones.json
  - Dashboard cum-pane: League Rating + Milestones (Leagology pattern, AFFL data)
  - evals/test_milestones_elo.py PASS
  - Top Elo: John Newton 1712; Fastest 25 wins: Tyler Sanchez 40g
  - URL: http://127.0.0.1:8765/index.html (Cumulative / All-Time)
  - No commit; no DB mutation
- Task 6 Wave T team-season activity: **complete** (local 2026-08-17)
  - scripts/compute_team_activity.py → site/team_activity.json (2018–2025)
  - teams.html season view: Activity grid + Team activity scatter
  - Career view hides activity block; pre-2018 honest empty
  - evals/test_team_activity.py PASS
  - Feelers 2025: tx=174 VA=1179.2 gridMoves=274
  - URL: http://127.0.0.1:8765/teams.html?squad=m18&year=2025
  - No commit; no DB mutation; no export_site
- Task 7 CHI-76 plan: **complete** (docs)
  - research/CHI-76_viz_tooling_plan.md — stay Chart.js; zero installs
  - evals/test_chi76_plan.py PASS
- Task 8 STATUS hygiene: **complete**
  - STATUS.md refreshed; trades 392; Hermy banner; no 2026 season lie
- Wave C verify matrix (2026-08-17 re-run): **23/23 PASS** + all listed pages HTTP 200
- Task 9 deploy: pending / Ryan only

## Ryan optional Chrome (not blocking agent loop)

| What | URL |
|------|-----|
| Elo + milestones | http://127.0.0.1:8765/index.html (Cumulative) |
| Team activity | http://127.0.0.1:8765/teams.html?squad=m18&year=2025 |
| FPpG | http://127.0.0.1:8765/players.html |
| Trades | http://127.0.0.1:8765/trades.html |

## Eval matrix snapshot

PASS: handoff, warehouse_2026, sidecars_status, fppg, trade_builder_join, trades_2025, trade_grid, milestones_elo, team_activity, record_book, dictionary, draft_guide, nav_gates, max_potential, titles_combined, player_charts, player_fg, awards_pos, w1_awards, logo_home, logo_strip, dashboard_cum, historical_gates, chi76_plan

## Master plan pointer

Wave order of record:  
`docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md` § Wave order  
Skill: `affl-hermy-baton` (`/affl-gauntlet`)


## Files changed this churn (no commit)

- build_db.py (CHI-75 earlier)
- evals/test_warehouse_2026.py, test_sidecars_status.py, test_fppg.py
- evals/test_record_book.py, test_draft_guide.py, test_nav_gates.py
- site/styles.css (.site-nav flex-wrap)


## Grok Bot notes absorbed

- Do not 90-day roadmap mid-loop
- Do not leave repo for SumerSports/Supabase
- Do not ask Ryan to sign in / run homework
- Do not mark Done without Ryan + Pages
- Re-verify all “In QA” claims with evals + curl
