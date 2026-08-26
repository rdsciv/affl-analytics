# Roto warehouse (query results)

Queried from `affl.db` after `python3 compute_roto.py`. These are **query results**, not hardcoded targets.

## Feelers 2025 (team_id 7, owner m18)

From `fact_roto_team_season` / `v_roto_standings`:

| phase | games | total_pts | total_rank | py | ptd | ry | recy | rec |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| championship | 2 | 46 | 1 | 480 | 3 | 404 | 757 | 61 |
| combined | 16 | 90 | 2 | 3932 | 28 | 3249 | 4086 | 399 |
| regular | 14 | 81 | 4 | 3452 | 25 | 2845 | 3329 | 338 |

Weekly `fact_roto_team_week` rows now exist (2,776 across 2018–2025) and sum to the season row for each team/phase (Feelers 2025 regular: 14 weekly rows = 14 regular games).

2014–2017: no `fact_roster_week` lineups, no roto rows.

Site roto page is unchanged. `roto.js` / `roto-math.js` still compute from `site/pillars/boxscores/*.json` at runtime. No weekly-trends hook in `roto.js`, so no weekly JSON export was added.
