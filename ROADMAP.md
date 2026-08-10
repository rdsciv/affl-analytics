# AFFL Analytics — roadmap

Ordered so that each phase ships something viewable. See `SPEC.md` for verified
data availability and formulas.

---

## Stack decision

**Recommendation: keep SQLite → static JSON → GitHub Pages. Do not move to
Supabase/Postgres.**

You said you've started this five times and never landed a complete deployed
site. That's the problem worth solving, and the cause is almost never the
database — it's that a server, a hosted DB and an auth layer are three things
that can each break a deploy. Right now the site is **already live** at
`rdsciv.github.io/affl-analytics`, deploys in 27 seconds on `git push`, and has
no runtime dependencies at all.

Given your actual requirements — public shared link, **no auth**, read-only,
twelve seasons of data that changes once a week at most — a hosted Postgres buys
nothing and adds a service to maintain, credentials to rotate, and a cold-start
failure mode.

What I'd add instead, when ad-hoc querying starts to matter:

- **DuckDB-WASM** in the browser against a static `affl.duckdb` or Parquet files.
  Real SQL, arbitrary joins, zero server, still just a static host. This is the
  thing that would make the site genuinely unusual: a public link where anyone
  can run their own query against the league's whole history.

Move to Supabase only if a future feature needs **writes** (a submit-your-picks
game, comments, a poll). That's the trigger, not query complexity.

## Charting

`site/` currently uses Chart.js. For the next phase I'd evaluate:

- **TanStack Charts** — headless, composes with the table/virtual libraries, good
  for the dense sortable leaderboards this project keeps needing.
- **Microsoft flint-chart** — worth a look for the small-multiple and
  distribution work (score distributions, per-team sparkline grids).

Neither is urgent. Chart.js is carrying the current pages fine; the deciding
factor will be the Stats/Leaderboard pages where sorting + filtering + charting
need to share state.

---

## Phase 1 — Database MVP  ← current priority

The warehouse exists (`affl.db`, `schema.sql`, `build_db.py`) with 24,762
roster-weeks, 2,220 matchup sides, 140,747 NFL player-weeks and 30,611 cap rows.
To close out MVP:

1. **`dim_scoring`** — load the league's actual scoring rules per season from
   `mSettings`, so fantasy points can be recomputed from raw stats rather than
   trusted blindly. This is the prerequisite for everything pre-2018.
2. **`fact_pbp_agg`** — per player-week aggregates from nflverse pbp: air yards,
   aDOT inputs, EPA, CPOE, red-zone and goal-line opportunity counts.
3. **`fact_ngs`** — Next Gen Stats weekly (2016+): separation, cushion,
   YAC-above-expectation, intended air yards share.
4. **`fact_roster_final`** — pre-2018 end-of-season rosters with
   `acquisition_type`/`acquisition_date` from `view=mRoster` (newly discovered).
5. **Verify the scoring engine**: recompute 2018–2025 fantasy points from
   nflverse under `dim_scoring` and diff against ESPN's own `points`. If that
   matches within rounding, the engine is trustworthy for pre-2018.

Gate: step 5 must pass before any pre-2018 player-level work.

**Done in Phase 1 beyond the original plan:** `fact_player_season_points` gives
every player a season total for all 12 seasons — ESPN's own where lineups exist,
computed from NFL stats where they don't — which unlocked draft value and PAR for
2014–2017. Materialised as a table rather than a view, because the correlated
subquery version pushed the site export from 1.3s to over two minutes.

## Phase 2 — Advanced receiving + TD luck

6. `v_receiving_usage`: aDOT, RACR, target share, air-yards share, WOPR per
   player-week and player-season.
7. `v_xtd`: opportunity-based expected TDs from pbp, and TD luck (actual − xTD),
   at player and team level. The "is he for real" table.
8. Team-level roll-ups: air-yards market share, separation index, xTD portfolio.

## Phase 3 — The FantasyGenius surface

9. **Rankings** — power %, luck, superlatives (all 12 seasons).
10. **History** — champions, finishes heatmap, all-time records, streaks.
11. **Stats** — sortable leaderboards and splits over the whole warehouse.
12. **Teams** — per-franchise profiles.
13. **Wrapped** — season-in-review, last because it's presentation over metrics.

## Phase 4 — Pre-2018 reconstruction (experimental)

14. Build the lineup solver (see `SPEC.md` §3).
15. **Validate on 2018–2025 where truth is known.** Report accuracy honestly.
16. If accurate: publish pre-2018 player-level history, clearly labelled as
    inferred, in its own table with confidence scores. If not: ship those years
    team-level only and document why.

## Data sources — decided, so it stops being an open question

| Source | Verdict |
| --- | --- |
| **nflverse** (nflfastR's data releases) | **Use — already in.** Free, redistributable, back to 1999, and it updates within about a day of games, so "not a live API" is not a practical limit for a weekly league site. |
| **Spotrac** | **Use — already in.** Cap hits 2018–2025, crawled politely per robots.txt. |
| **Over The Cap** (via nflverse) | Use for contract value/APY, but the bulk release stops at 2022. |
| **Sportradar / Genius Sports** | **No.** Enterprise licensing. The only thing they add over nflverse is player tracking, and the price is not remotely justified by a no-revenue league dashboard. |
| **SportsDataIO** | **No.** Same reasoning at a smaller price. Its projections would be the draw, not its stats, and we care about what happened rather than what was projected. |
| **Amazon QuickSight / Amazon Q** | **No, and actively wrong for this project.** It needs an AWS account, IAM, capacity or per-seat licensing, and embedding a QuickSight dashboard publicly means auth and cost. That directly contradicts the requirement: a plain shared link, no auth. It also adds exactly the kind of hosted dependency that has sunk previous attempts. |
| **NFL Next Gen Stats internals** (the NFL IQ data) | Not accessible, as expected. `nflverse` already republishes the public NGS aggregates (separation, cushion, YAC over expected) from 2016. Raw tracking and mph are not obtainable. |

## Ideas borrowed from NFL IQ (worth building)

NFL IQ's real mechanic is not prettier charts, it is *modelling the market instead
of picking an expert* — aggregating thousands of mock drafts into probability
distributions. The AFFL analogue is stronger, because the league has something no
public tool has: **twelve years of its own auction prices**, which are revealed
preference from the same twelve managers.

- **Market arbitrage map** (`v_market_tier`, built): PAR returned per dollar by
  position and price tier. Early read — mid-tier RBs are where the league's money
  dies (\$25–49 RBs average **−16 PAR** while \$25–49 WRs return **+14**), while
  \$10–24 QBs are the best value bucket in the league.
- **Manager edge vs the league's own market** (`v_manager_market`, built): each
  pick scored against what the league typically got at that position and price.
- **Season simulation** — Monte Carlo from each team's score distribution to give
  playoff odds by week, so History can say "you were 12% in week 10 and still made
  it" rather than only reporting the outcome.
- **Ripple / counterfactual** — recompute the standings without a given trade. All
  lineups exist from 2018, so trade impact on wins is directly computable.

## Phase 5 — Extras / backlog

- DuckDB-WASM public query console
- Reception-Perception-style route/coverage approximation from NGS + pbp
  (explicitly an approximation — the real thing is manual charting)
- Player speed / mph — needs an nfl.com NGS scrape; not promised
- Mini-games, weekly recap generation, rivalry pages
- AFFL logo favicon (blocked: needs the file at `site/logos/affl.png`)

---

## Why the previous five attempts stalled (best guess, and how this avoids it)

Looking at `AFFLleeger`, `draftedge-2026`, `dienasty-gm-report`: each one starts
with a framework and a data layer at the same time. This project inverted that —
data first, verified at every step, with a static site that was deployable from
day one. The rule that's kept it moving: **never let the site depend on
something that can be down.**
