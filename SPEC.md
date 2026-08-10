# AFFL Analytics — data spec

Everything below is **verified against the live APIs**, not assumed. Where a thing
is not available I say so rather than leaving it to be discovered later.

---

## 1. League facts

Pulled from `view=mSettings` (2025), not from memory:

| Setting | Value |
| --- | --- |
| Format | Redraft, **auction**, $200 budget |
| Scoring | **Non-PPR** (`rec` = 0), H2H points |
| Waivers | `WAIVERS_TRADITIONAL`, 24-hour — **no FAAB**, so every bid is $0 |
| Keepers | ESPN reports `keeperCount: 0` for 2025 — **needs confirming** (see open questions) |
| Regular season | 14 weeks · 6 playoff teams |
| Teams | **10 (2014–2016) → 12 (2017 on)** |
| Starters | QB1 · RB2 · WR2 · TE1 · FLEX1 · D/ST1 · K1 = 9 |
| Bench / IR | 7 bench + 1 IR (17 total) |

### Scoring rules (exact, for recomputing history)

```
passing:   0.04/yd (1 per 25)   4/TD    -2/INT   2/2pt
rushing:   0.10/yd (1 per 10)   6/TD             2/2pt
receiving: 0.10/yd (1 per 10)   6/TD             2/2pt   0/reception
fumbles:   -2 lost
kicking:   XP +1 · FG 40-49 +4 · FG 50+ **+3** · miss -1
returns:   KR TD +6 · PR TD +6 · fumble-ret TD +6 · int-ret TD +6
defense:   TD +6 · plus tiered points-allowed buckets
```

Note the oddity: **a 50-yard FG scores less (3) than a 40–49 (4)**. That is what
the league is actually configured with, so it stays.

### Two scoring quirks found by validation, both load-bearing

1. **Yardage was bucketed through 2018, fractional from 2019.** Through 2018 ESPN
   floored yardage to whole points (`floor(passYds/25)`, `floor(rushYds/10)`,
   `floor(recYds/10)`); from 2019 it awards fractional points per yard. Proven
   empirically: on 2018 player-weeks, bucketed scoring is **96.2% exact** vs
   **6.6%** for fractional, and 2019 is the exact reverse. Getting this wrong
   costs ~0.5 points per player-week, which compounds across a 9-man lineup.
   Stored as `dim_season.yardage_mode`.
2. **ESPN's stored 2018 settings omit the yardage rules entirely** (statIds
   3/24/42 are simply absent from `scoringItems`). Backfilled from the nearest
   season that has them; the validation gate is what proves the backfill correct.

Scoring is **not constant** across league history — 19 rules 2014–2019, 20 from
2020, 25 in 2025 — so every recomputation joins on season.

---

## 2. Data availability — verified per season

This is the single most important table in the project. It stops us building on
data that isn't there.

| Data | 2014–2016 | 2017 | 2018–2025 | Source |
| --- | --- | --- | --- | --- |
| Standings, schedule, **weekly team scores** | ✅ | ✅ | ✅ | ESPN `mMatchup` |
| Draft (auction $) | ✅ | ✅ | ✅ | ESPN `mDraftDetail` |
| **Final-season roster + acquisition type/date** | ✅ | ✅ | ✅ | ESPN `mRoster` |
| Weekly lineups (who started) | ❌ | ❌ | ✅ | ESPN `mMatchup` + `scoringPeriodId` |
| Transaction feed (adds/drops/trades) | ❌ | ❌ | ✅ | ESPN `mTransactions2` |
| **NFL weekly player stats** | ✅ | ✅ | ✅ | nflverse `stats_player_week` (back to 1999) |
| Play-by-play (EPA, air yards, CPOE) | ✅ | ✅ | ✅ | nflverse `pbp` (back to 1999) |
| Next Gen Stats (separation, cushion, YAC±) | ❌ (2016+) | ✅ | ✅ | nflverse `nextgen_stats` (2016+) |
| NFL cap hits | — | — | ✅ | Spotrac |
| Contracts (APY, guarantees) | ✅ | ✅ | ⚠️ to 2022 | Over The Cap via nflverse |

Teams were **10** in 2014–2016 and **12** from 2017, which changes replacement
level and every all-play denominator. Already handled per season.

---

## 3. Can we rebuild 2014–2017? Honest answer

Your hypothesis was: no scoreboard data, but draft + transactions could rebuild
weekly rosters, then apply NFL stats to recompute matchups.

Two corrections, one of them good news:

1. **We already have the weekly team scores** for 2014–2017 — they're in the
   schedule (`totalPoints` per side). Nothing needs recomputing. The scoreboard
   for those years is live on the site now.
2. **The transaction feed does not exist before 2018.** I probed every ESPN view;
   `mTransactions2` returns zero records for 2014–2017. So rosters cannot be
   rolled forward week by week from transactions.

What we *do* newly have (this was the find): `view=mRoster` on `leagueHistory`
returns, for every pre-2018 season, each team's **final roster** with
`acquisitionType` and `acquisitionDate` per player, plus season point totals.

So the honest state per pre-2018 season is:

- ✅ weekly team scores, standings, full auction board
- ✅ end-of-season rosters, and how/when each surviving player was acquired
- ❌ weekly lineups, drops, and mid-season trades

### The one route to player-level pre-2018 history: lineup inference

Because we know (a) each team's exact score every week, and (b) every NFL
player's exact fantasy points that week — computable from nflverse under the
scoring rules above — we can *solve* for the lineup:

> Of all legal lineups (QB1/RB2/WR2/TE1/FLEX1/DST1/K1) drawable from a team's
> plausible roster that week, which sum to the known team score?

With 9 slots and an exact float target, most weeks will have **exactly one**
solution. This is genuine inference, not fact, so it must be:

- stored in a separate table with a `confidence` column and a `solutions_found`
  count, never mixed into `fact_roster_week`
- labelled in the UI as reconstructed
- validated on 2018–2025, where the true lineup is known — measure the accuracy
  before trusting a single pre-2018 number

That validation step is the gate, and **the first half of it now passes**:
`validate_scoring.py` reproduces ESPN's own fantasy points from raw nflverse
stats at **96–99.8% exact across all eight seasons where lineups exist**. So the
scoring engine is trustworthy. What remains unproven is the lineup *solver*
itself, which is Phase 4.

---

## 4. Field inventory

### From ESPN
`season, week, team_id, member_id, player_id, lineup_slot, points, started,
opponent_id, is_playoff, tier, draft_overall/round/pick/bid/keeper,
acquisition_type, acquisition_date, tx_type, bid, playoff_seed, final_rank`

### From nflverse `stats_player_week` (the fantasy engine)
`completions, attempts, passing_yards, passing_tds, interceptions, sacks,
sack_yards, passing_air_yards, passing_yards_after_catch, passing_epa, pacr,
dakota, carries, rushing_yards, rushing_tds, rushing_fumbles_lost, rushing_epa,
receptions, targets, receiving_yards, receiving_tds, receiving_air_yards,
receiving_yards_after_catch, receiving_epa, racr, target_share,
air_yards_share, wopr, special_teams_tds`

### From nflverse `pbp` (deeper, play grain)
`ep, epa, wp, wpa, cp, cpoe, air_yards, yardline_100, xyac_mean_yardage,
xyac_epa, success, series_success, drive, down, ydstogo, pass_location,
run_location, shotgun, no_huddle, qb_hit, sack, penalty`

### From nflverse `nextgen_stats` (2016+, weekly)
- receiving: `avg_cushion, avg_separation, avg_intended_air_yards,
  percent_share_of_intended_air_yards, catch_percentage, avg_yac,
  avg_expected_yac, avg_yac_above_expectation`
- passing: `avg_time_to_throw, avg_completed_air_yards, aggressiveness,
  max_completed_air_distance, expected_completion_percentage,
  completion_percentage_above_expectation`
- rushing: `efficiency, percent_attempts_gte_eight_defenders,
  avg_time_to_los, rush_yards_over_expected, rush_pct_over_expected`

### Money
Spotrac: `cap_hit, cap_pct, dead_cap, base_salary, signing_bonus`
OTC: `value, apy, guaranteed, apy_cap_pct, years, year_signed`

---

## 5. Metric formulas

### Receiving usage (what you asked for)
```
aDOT            = receiving_air_yards / targets
RACR            = receiving_yards / receiving_air_yards
target_share    = targets / team_targets
air_yards_share = receiving_air_yards / team_air_yards
WOPR            = 1.5 x target_share + 0.7 x air_yards_share
YAC over exp    = avg_yac - avg_expected_yac          (NGS, 2016+)
separation edge = avg_separation - position/season mean
```

### Expected vs actual TD
```
xTD (opportunity-based)
  = SUM over targets/carries of P(TD | yardline_100, down, ydstogo, play_type)
    where P is fit from that season's pbp
TD luck = actual_TD - xTD
```
Positive TD luck flags a player whose fantasy year outran his opportunity — the
regression candidate. This is the single most useful "is he for real" metric.

### Fantasy-specific
```
points          = SUM(stat x league scoring rule)          -- table in section 1
optimal_lineup  = max points from a legal slot assignment
management %    = actual / optimal                          (FG "Management Score")
PAR             = player_points - replacement_points
replacement     = MAX(Nth-best at position, best undrafted at position)
                  N = teams x starters required
PAR per dollar  = PAR / MAX(auction_bid, 1)
power %         = all-play wins / all-play games            (FG "Power Rankings")
lucky win       = W while scoring in the bottom half that week
unlucky loss    = L while scoring in the top half
CDR             = correct start/sit decisions / total decisions
ideal start %   = weeks in optimal lineup / weeks rostered
```

### League-unique ideas (not on FantasyGenius)
```
roster payroll     = SUM(NFL cap_hit) of your roster        -- built
value per $M cap   = fantasy points / (NFL cap $M)          -- "cheap production"
air-yards market   = share of league-wide air yards your WRs commanded
xTD portfolio      = team actual TD - team xTD, i.e. league-wide TD luck table
separation index   = cap-weighted avg separation of your WRs
opportunity cost   = points scored by players you dropped, after you dropped them
draft-day inflation= your $ spent vs league median $ at that position
```

---

## 6. Open questions for you

1. **Keepers.** ESPN says `keeperCount: 0` for 2025. Do you run keepers as a
   house rule outside ESPN's keeper feature, and in which seasons? This changes
   how draft value should be judged (a kept player has no auction price).
2. **50-yard FGs scoring less than 40–49** — intentional, or a settings slip
   worth knowing about?
3. Pre-2018 lineup inference: worth building if validation shows high accuracy,
   or would you rather those seasons stay team-level only?

## 7. Not available — stated plainly

- **Player speed / mph.** Not in nflverse. NFL's Next Gen Stats site has it but
  does not publish a bulk feed. "Average mph of my WRs" would need a separate
  scrape of nfl.com and is not something I'd promise. `avg_separation` and
  `avg_cushion` are the defensible substitutes, and they answer a similar
  question (who gets open) better than raw speed does.
- **Reception Perception** is proprietary manual charting (Matt Harmon). It
  cannot be derived from public data. NGS separation/cushion + aDOT + target
  share by route depth is the closest public approximation.
- Weekly lineups and transactions before 2018 — see section 3.
