# 2025 started-player NFL lines

CHI-27 / AFFL-007. Join is `fact_roster_week` (started) → `dim_player.gsis_id` → `fact_nfl_week`.
Missing stays missing. DST has no nflverse id.

- Started rows: **1818**
- Skill starters missing gsis: **0**
- Scored skill missing nflverse: **0** (Roto gate)
- Zero-point skill DNPs missing nflverse: **5** (not invented)
- DST starts: **202**, gsis=0

## Coverage by position

| position | n | nfl | pct |
| --- | --- | --- | --- |
| DST | 202 | 0 | 0.0 |
| K | 202 | 202 | 100.0 |
| QB | 205 | 205 | 100.0 |
| RB | 492 | 490 | 99.6 |
| TE | 199 | 198 | 99.5 |
| WR | 518 | 516 | 99.6 |

## Zero-point DNPs (no nflverse row)

| week | team_id | player | pos | affl_pts | gsis |
| --- | --- | --- | --- | --- | --- |
| 3 | 10 | CeeDee Lamb | WR | 0.0 | 00-0036358 |
| 8 | 9 | Quentin Johnston | WR | 0.0 | 00-0038544 |
| 11 | 8 | Terrell Jennings | RB | 0.0 | 00-0039757 |
| 15 | 1 | Isaiah Likely | TE | 0.0 | 00-0037838 |
| 17 | 9 | Chris Rodriguez Jr. | RB | 0.0 | 00-0038611 |

## How to refresh

```
python3 evals/test_starter_nfl_2025.py
```
