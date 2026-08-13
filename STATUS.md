# AFFL Analytics — Status

This file tracks what's built, what's planned, and the architectural decisions that guide the project.

## Assembly Decision (Aug 2026)

**Product**: This repository. Live site at https://rdsciv.github.io/affl-analytics/

**Stack**: SQLite → static JSON → GitHub Pages. Zero runtime dependencies.

### The Two-Database Architecture

The warehouse is split into **two SQLite files** plus join views:

1. **`affl.db`** — League truth only:
   - `dim_season`, `dim_member`, `dim_team`, `dim_player`, `dim_scoring`
   - `fact_roster_week`, `fact_matchup`, `fact_draft_pick`, `fact_transaction`, `fact_trade`, `fact_trade_item`
   - AFFL-only views: `v_team_week`, `v_power`, `v_luck`, `v_player_season`, `v_draft_value`, etc.

2. **`nfl.db`** — NFL/player truth only:
   - `fact_nfl_week` (nflverse weekly stats)
   - `fact_contract` (Over The Cap via nflverse)
   - `fact_cap_hit` (Spotrac cap tables)
   - `player_season` (NFL club membership)

3. **Warehouse views** (created via `ATTACH DATABASE 'nfl.db' AS nfl`):
   - `v_player_cap` — deduplicated cap hits per player-season
   - `v_team_nfl_cap` — NFL salary cap cost of each AFFL roster
   - `v_started_vs_nfl` — started fantasy points joined to NFL EPA, air yards, cap hit

**Join key**: `dim_player.gsis_id` (nflverse identifier) connects AFFL rosters to NFL stats and cap data.

**Why this split?**

Ryan asked for "1 AFFL database, 1 NFL database, joined relationally" to keep league facts separate from NFL facts. This makes the boundary explicit:
- AFFL data is our league's history (rosters, matchups, drafts, trades)
- NFL data is external truth (stats, contracts, cap hits) that applies to any fantasy league
- Charts and analysis query the join

### Rejected Paths

This is the **assembly** of existing AFFL work, not another greenfield attempt. Earlier AFFL projects stalled on:
- Cloudflare D1 / Sourcebook D1
- Drizzle ORM + Postgres
- Next.js + hosted runtime
- Moving to Supabase

Those paths introduced:
- Hosted services to maintain
- Runtime dependencies that can be down
- Deploy complexity beyond `git push`

The current stack (SQLite → JSON → GitHub Pages) has been **live and working** since the project started. It deploys in ~27 seconds with zero services to maintain.

**TanStack Charts** is the chosen charting path forward (proven in [dienasty-history](https://github.com/rdsciv/dienasty-history)). Chart.js stays for the existing five static pages; migration is not in this PR's scope.

## What's Built (Verified)

### Data Pipeline
- ✅ `fetch.py` / `fetch.sh` — pulls ESPN league data + nflverse CSVs
- ✅ `fetch_spotrac.py` — scrapes NFL cap tables (politely, with cache)
- ✅ `build_db.py` — builds both SQLite databases + warehouse views
- ✅ `validate_scoring.py` — **96–99.8% exact** reproduction of ESPN points from raw stats (2018–2025)
- ✅ `export_site.py` — exports metrics to static JSON for the site
- ✅ `process_seasons.py` — assembles per-season structural data

### Warehouse Coverage
- **12 seasons** (2014–2025): standings, matchups, drafts
- **8 seasons** (2018–2025): weekly lineups, transactions, trades
- **4 seasons** (2014–2017): team-level scores only (no weekly lineups — ESPN doesn't keep them)
- **24,762** roster-weeks
- **2,220** matchup sides
- **140,747** NFL player-weeks (nflverse, back to 1999 but filtered to AFFL-relevant)
- **30,611** cap hit rows (Spotrac 2018–2025)

### Scoring Engine
The league's exact non-PPR scoring rules are in `dim_scoring` (19 rules 2014–2019, 20 from 2020, 25 in 2025). Two quirks are load-bearing:
1. **Yardage was bucketed through 2018, fractional from 2019.** Proven empirically; stored as `dim_season.yardage_mode`.
2. **50-yard FGs score less (3) than 40–49 (4).** That's the actual league config, so it stays.

Validation proves the engine trustworthy: recomputed points match ESPN at 96–99.8% exact across all seasons with lineups.

### Metrics
- ✅ Draft value: **PAR per dollar** (points above replacement, positionally fair)
- ✅ Power rankings: all-play win%
- ✅ Luck: FantasyGenius-style lucky wins / unlucky losses
- ✅ NFL cap: total salary cost of each AFFL roster (the headline join-based metric)
- ✅ Replacement level: computed per season (10-team 2014–2016, 12-team 2017+)

### Site (Live)
Five static pages, Chart.js:
- `index.html` — dashboard with weekly scoring, KPIs, standings
- `scoreboard.html` — matchup results
- `players.html` — player stats
- `draft.html` — auction board with PAR
- `trades.html` — trade log

Plus one new **TanStack Charts lab page** (this PR) proving the AFFL ⋈ NFL join.

## What's Planned (Not Built Yet)

### Phase 2 — Advanced Metrics (database hooks exist, data not loaded)
- `fact_pbp_agg` — per player-week EPA, air yards, aDOT, red-zone/goal-line opportunity counts (nflverse PBP)
- `fact_ngs` — Next Gen Stats weekly (2016+): separation, cushion, YAC above expected
- `v_receiving_usage` — aDOT, RACR, target share, WOPR
- `v_xtd` — opportunity-based expected TDs (the "is he for real" table)

### Phase 3 — FantasyGenius Surface
- Rankings: tiers, superlatives, streaks
- History: champions, finishes heatmap, all-time records
- Stats: sortable leaderboards and splits
- Teams: per-franchise profiles
- Wrapped: season-in-review

### Phase 4 — Pre-2018 Reconstruction (experimental)
Lineup inference: solve for the 9-man lineup that produces the known team score from plausible rosters. Gate: validate on 2018–2025 first. If accurate, publish pre-2018 player-level history (clearly labelled as inferred). If not, those years stay team-level only.

### Phase 5 — Extras
- DuckDB-WASM public query console
- Auction Lab import (1,804 bids)
- Leeger aggregates
- Mini-games, rivalry pages

## Data Availability (Verified per Season)

| Data | 2014–2016 | 2017 | 2018–2025 | Source |
| --- | --- | --- | --- | --- |
| Standings, schedule, **weekly team scores** | ✅ | ✅ | ✅ | ESPN `mMatchup` |
| Draft (auction $) | ✅ | ✅ | ✅ | ESPN `mDraftDetail` |
| **Final-season roster + acquisition** | ✅ | ✅ | ✅ | ESPN `mRoster` |
| Weekly lineups (who started) | ❌ | ❌ | ✅ | ESPN `mMatchup` + `scoringPeriodId` |
| Transaction feed (adds/drops/trades) | ❌ | ❌ | ✅ | ESPN `mTransactions2` |
| **NFL weekly player stats** | ✅ | ✅ | ✅ | nflverse (back to 1999) |
| Play-by-play (EPA, air yards, CPOE) | ✅ | ✅ | ✅ | nflverse PBP (back to 1999) |
| Next Gen Stats (separation, cushion, YAC±) | ❌ (2016+) | ✅ | ✅ | nflverse NGS (2016+) |
| NFL cap hits | — | — | ✅ | Spotrac |
| Contracts (APY, guarantees) | ✅ | ✅ | ⚠️ to 2022 | Over The Cap via nflverse |

**Teams were 10 in 2014–2016, 12 from 2017.** Replacement level and all-play denominators adjust per season.

## How to Build

```bash
# Fetch data (requires .env with ESPN cookies)
./fetch.sh

# Build both databases + warehouse views
python3 build_db.py

# Verify scoring engine
python3 validate_scoring.py

# Export metrics to site JSON
python3 export_site.py

# Site is live at site/index.html (open locally or deploy via GitHub Pages)
```

## Next Work

1. Load PBP aggregates and NGS into `nfl.db`
2. Build advanced receiving views (`v_receiving_usage`, `v_xtd`)
3. Migrate TanStack Charts lab patterns to the main Stats/Leaderboard pages
4. Add FantasyGenius surface (Rankings, History)

The path forward is **assembly and completion**, not another rewrite.
