# AFFL contracts

Binding. If a metric or page disagrees with this file, the file wins and the
metric is wrong. Locked 2026-08-13 against `affl.db` for CHI-21 / CHI-23.

## Identity

Four grains. Do not collapse them.

| Grain | Meaning | Warehouse |
| --- | --- | --- |
| **Owner** | The person. Canonical display name. | `dim_member` after merges below |
| **Franchise** | Same as owner in this league. Redraft, no separate dynasty entity. Career records follow the person, not the ESPN slot. | owner id |
| **Team-season** | One roster in one year. | `dim_team (season, team_id)` |
| **Alias** | Team name that year. Keep every one. | `dim_team.name` |

ESPN `member_id` is not the owner. It splits and leaves orphans.

Merge these into one owner each:

- Jason Kafka: canonical `m07` (site merge m01→m07). `m07` is 2016 Green Bay Glory Holes + 2026 Chupacabras; `m01` is 2017–2023 Chupacabras. Do not map m07→m01.
- Kevin Sliger: `m08` is the real row. `m03` has no team-seasons. Drop `m03` from career math.
- Tanner Dunn: `m10` is the real row. `m20` has no team-seasons. Drop `m20` from career math.

Everyone else is already 1:1. Ryan Childress is `m18`, aliases Tittsburgh Feelers → Grand Teeton Feelers. John Newton is `m05`, San Diego Shadowcocks / Shadowcöcks.

All-time tables group by owner, not by team name and not by `team_id`.

## Phase

From `fact_matchup.tier` and `dim_season.reg_weeks`:

| Phase | Rule |
| --- | --- |
| Regular season | `is_playoff = 0` (weeks 1–`reg_weeks`) |
| Championship playoffs | `is_playoff = 1` and `tier = WINNERS_BRACKET` |
| Consolation | `LOSERS_CONSOLATION_LADDER` or `WINNERS_CONSOLATION_LADDER` |

Championship standings, title credit, and official W/L use regular season plus `WINNERS_BRACKET` only. Consolation games are stored and can be shown, never folded into championship records. `dim_team.final_rank` is ESPN's published finish. We do not re-rank it.

League size is 10 (2014–2016) then 12 (2017–). Replacement level and all-play denominators are per season.

## Evidence and promotion

| Status | Meaning | Where it may appear |
| --- | --- | --- |
| **Verified** | Primary source exists for that grain (ESPN score, ESPN lineup, ESPN draft bid, nflverse stat row). | Awards, standings, career records, primary nav |
| **Reconstructed** | Inferred (pre-2018 lineup solver, computed season totals where ESPN has no lineup). | Explore views, labeled. Never on awards. |
| **Unavailable** | No source. | Omitted. No invented number, no zero fill. |

2014–2017: matchups, standings, draft are verified. Weekly lineups and the transaction feed are unavailable. End-of-season roster + acquisition type is verified. Season player totals computed from nflverse under that year's scoring rules are reconstructed.

2018–2025: weekly lineups, transactions, bids are verified.

A page that needs a verified grain and does not have it stays out of primary nav.

## Sources

| Kind | Source | Notes |
| --- | --- | --- |
| League outcomes | ESPN `mMatchup` / `mDraftDetail` / `mRoster` / `mTransactions2` | Primary for AFFL facts |
| NFL player-weeks | nflverse `stats_player_week` | Fantasy engine |
| Opportunity / xTD | nflverse pbp | Fit per season |
| NGS | nflverse `nextgen_stats` | 2016+ only |
| Cap | Spotrac | Cached |
| Weekly projections | FantasyPros consensus standard stat lines, scored with AFFL rules | Archive going forward. Historical gap stays unavailable. ESPN `projectedPoints` is labeled ESPN, not consensus. |

Inputs (leeger, Auction Lab, Wrapped, ESPN archive sites) are not a second warehouse. They may fill a hole only when the primary source does not exist, and the row is labeled with that source.

## Scoring

AFFL rules in `SPEC.md`. Yardage is `BUCKET` through 2018, `FRACTIONAL` from 2019 (`dim_season.yardage_mode`). 50-yard FG is 3 points. Recompute with the season's rule set. Do not use a vendor's FPTS column.

## GM effectiveness

Starter points grade the lineup. They do not grade the GM.

- **Custody PAR** = weekly PAR for every week a player was rostered, started or not. Split Drafted / Traded in / Waiver / FA.
- **Lineup IQ** = actual starter points ÷ optimal. Start/sit only.
- **Trade Alpha** = incoming consensus ROS − outgoing consensus ROS at the trade. Not added into Custody PAR.

See `METRICS.md`.
