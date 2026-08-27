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

2014–2017: matchups, standings, draft are verified.

ESPN deleted most pre-2018 league history in early 2025. What survives in `data/box_raw`
has been recovered, and the grains are not all the same tier. Do not collapse them.

| Grain | Tier | Detail |
| --- | --- | --- |
| Matchups, standings, draft | Verified | Unchanged. |
| **Weekly starters** | **Verified, partial** | 5,530 rows in `fact_roster_week`, all `started = 1`. A team-week loads only if its lineup is legal and cannot outscore the team. `lineup_complete = 1` means the starters sum exactly to ESPN's score; `= 0` means ESPN dropped entries, so the surviving starters are real but the set is short. 8 team-weeks are excluded outright — ESPN's own entries sum to *more* than the team scored. |
| Starter **slot** | Verified position, arbitrary FLEX | `lineupSlotId` is zeroed in every leagueHistory response, so slot comes from `defaultPositionId`. Position is exact (validated against 2018 truth; every disagreement was a FLEX/same-position swap, none cross-position). Which of two same-position starters ESPN labelled FLEX is not recoverable and is an arbitrary tiebreak. `slot_source` records which case a row is. |
| **Weekly bench** | Unavailable | `rosterForMatchupPeriod` holds starters only. There is no weekly bench and none can be inferred from the archive. |
| **Late-season roster snapshot** | Verified | `teams[].roster` carries one full roster per team — bench included, with real `lineupSlotId` — repeated identically in every weekly file. It dates to a late-season week and is datable for only some teams. Lives in `fact_roster_snapshot_pre2018`, never in `fact_roster_week`. |
| Acquisition type | Unavailable | `acquisitionType` is `None` league-wide before 2018. |
| Transaction feed | Unavailable | No source. `dim_season.has_tx = 0`. |
| Season player totals | Reconstructed | Computed from nflverse under that year's scoring rules. |

`dim_season.has_rosters` stays **0** for 2014–2017. It means *full rosters including
bench*, and it gates roto season rows (`compute_roto.py`) and the scoring validator. There
is no pre-2018 bench, so the flag is correct as-is. Recovered starters are not a reason to
flip it.

**Lineup IQ before 2018** may be published only for a team-week whose snapshot is dated,
and must be labelled: the *actual* starter points are ESPN's own and exact, but the
*optimal* depends on bench points our engine computed. Verified roster, computed optimal.
Never on awards.

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
