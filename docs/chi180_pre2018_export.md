# CHI-180 — corrected pre-2018 starts export

**Date:** 2026-09-04 CT  
**Grain:** `fact_roster_week.started=1`, AFFL NON_PPR points

## Prefer for leaders

`site/affl_career_starts.json` — pid-keyed `{starts, stPts, bySeason}` for 2014–2025.  
Do **not** blind-sum week JSON for career leaders.

## Also corrected

`site/pre2018_starts.json` rebuilt from `started=1` only (same shape `year → pid → week → {pts,slot,tid}`).  
Old overcount backed up as `site/pre2018_starts.json.bak_overcount`.

### Wilson check
| Season | Old JSON | Warehouse / new |
|--------|---------:|----------------:|
| 2014 | 11 | **9** |
| 2015 | 14 | **11** |
| 2016 | 12 | **10** |
| 2017 | 13 | **13** |
| Career | 110 / 2198.8 (with 2018+) | **103 / 1996.8** |

Mahomes 111/2414.8 · Allen 100/2330.0 unchanged (no 2014–17).
