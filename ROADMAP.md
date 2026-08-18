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
| **ESPN sports API** (unofficial `site.web.api` / `site.api`) | **Use — cache nightly, never from the browser.** Player news, headshots, bio, injuries, depth charts, rookie college. Same athlete IDs as the fantasy API. Does **not** fill 2014–17 benches or pre-2018 transactions. Unofficial, can vanish. |

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


## Phase 6 — League awards and roster composition (from 2026-08-16 mockups)

Build these on the AFFL site from warehouse grains. Names in the mockups are another league; use current franchise names and logos.

1. **All-League Selections** — count of weekly positional top scorers on each roster. Leader card + rank / team / total / top player.
2. **Bush League Selections** — same shape, weekly positional bottoms. You do not want to lead this board.
3. **Where did your points come from?** — Week 1 roster points vs acquired (trade/waiver) points, with a Draft Day award (highest Week 1 %) and a Moneyball award (highest acquired %). 2018+ only (need lineups + tx).
4. **Injury Report** — impact score from drafted players × expected PPG × weeks missed. Infirmary vs availability cards, plus rank / top injury / impact / weeks missed.
5. **Age is Just a Number** — live age from nflverse birth dates (`player_bio.json`, `ageOn()` vs today). Oldest/youngest squad cards and age vs Power Win % scatter. Age is never a frozen table; it recomputes from birth date and the as-of day.



## Phase 7 — ESPN sports API as NFL context (from 2026-08-17 gist research)

Unofficial ESPN sports APIs (`site.web.api` / `site.api`), not the fantasy `lm-api`. Same athlete IDs we already have. Cache nightly into the warehouse; never hit ESPN from the browser. Does **not** fill 2014–17 weekly benches or pre-2018 transactions. Does not replace nflverse, the fantasy API, or Spotrac. Skip odds, QBR, play-by-play, and NFL transactions.

Linear: [CHI-40](https://linear.app/childressllc/issue/CHI-40/affl-020-espn-sports-api-as-nfl-context-feed) (AFFL-020) is the parent. Children are Backlog.

1. **Player card news, headshot, and bio** — common/v3 athlete overview: news, next game, Rotowire notes, college/draft bio, official headshot, home/away splits. CHI-41 / AFFL-021.
2. **Injury report and depth charts** — sports.core per-team injuries (resolve `$ref`s; skip the 8.9 MB league dump and the empty site stub) + site depthcharts. Gives Phase 6 #4 a real source. CHI-42 / AFFL-022.
3. **Rookie college stats** — same pattern under `college-football`, only when the NFL sample is thin. CHI-43 / AFFL-023.

## Phase 8 — Team composition (from 2026-08-17)

Team comp for **every franchise, every season (2014–2025)**. Starting roster and how the squad was built / changed (draft, trade, waiver, FA).

Linear: [CHI-47](https://linear.app/childressllc/issue/CHI-47/affl-028-team-composition-for-every-franchise-every-season) (AFFL-028). Backlog.

Gaps are known and do not block the page:

- 2014–17 weekly benches are incomplete (snapshot + recovered starters only).
- ESPN has no transaction log before 2018.
- Ship the grid anyway. Label missing weeks honestly (snapshot / not recovered). Never “NFL not rostered” for 2014–17. Fill later.

Also in flight from the same day (not this phase, already ticketed):

- [CHI-44](https://linear.app/childressllc/issue/CHI-44/affl-024-player-journey-diagram-from-weekly-ownership-trades) AFFL-024 player journey diagram
- [CHI-45](https://linear.app/childressllc/issue/CHI-45/affl-025-audit-and-fix-the-trade-database-vs-weekly-ownership) AFFL-025 trade database vs weekly ownership
- [CHI-46](https://linear.app/childressllc/issue/CHI-46/affl-026-cumulative-is-the-default-home-dashboard) AFFL-026 Cumulative default home
- [CHI-48](https://linear.app/childressllc/issue/CHI-48/affl-027-maximum-potential-formatted-like-fantasygenius) AFFL-027 Maximum Potential (FantasyGenius layout)

## Phase 9 — Team-season activity lab (from 2026-08-18 Leagology-style refs)

**Surface:** `teams.html` when a franchise **and** a single season are selected (not career-only). Sit with trades / roster / moves for that year. 2018+ only (ESPN tx timestamps). Pre-2018: honest empty state — no invented activity.

Reference mockups (other league names; use AFFL franchise marks + current names):

1. **Activity grid** — *day of week × week · transaction activity*
   - Rows: W1…W17 (or that season’s regular + playoff weeks that have tx).
   - Columns: Tue → Mon (ESPN fantasy week rhythm; waiver clear Tue).
   - Cell shade = count of roster moves that day (add + drop + trade legs). Light → dark blue scale; empty = no fill.
   - Hover tooltip: `W{n} · {DOW}` then bullet list of moves (`add X`, `drop Y`, trade pair lines). No lineup set/sit events.
   - Caption (verbatim intent): every add, drop, and trade by day of week it was made. Lineup changes are not shown — ESPN does not give a real timestamp for when a lineup was set, only for actual roster moves.
   - Data: `fact_transaction.ts` (+ trade cluster times if needed). Direction ADD/DROP; trades labeled without inventing the other side’s intent.
   - One grid **per team-season** (selected franchise + year). Optional later: league heatmap is out of scope here.

2. **Team activity scatter** — *transactions (X) vs in-season value added (Y)*
   - **X:** count of in-season roster transactions for that team-season (same move definition as the grid; draft day excluded or labeled separately).
   - **Y — value added (pts):** points that **in-season acquired** players put into a **started** lineup, **minus** what the players they replaced would have scored in those same start slots (counterfactual bench/replacement). Positive = moves helped; below solid zero line = churned backward.
   - Solid horizontal rule at **Y = 0**. Dashed horizontal rule at **league median** value-added for that season.
   - One labeled point **per franchise in that season** when viewing a season context; on a single-team page, highlight the selected franchise and ghost the rest for context (or show only selected — product choice at build: default **all teams that season, selected emphasized**).
   - Caption intent: across = how often you moved; up = whether it worked. Zero = break-even. Dashed = league median.
   - Data needs: 2018+ lineups (`fact_roster_week` started) + tx/trade acquisition + weekly fantasy points. Pre-2018 stays unavailable.
   - Do **not** mix Custody PAR into Y; this is start-slot replacement value for in-season moves only (distinct from draft PAR).

**Acceptance (when built):**

- Season picker required; career view does not fake a single-year grid.
- Eval: 2025 sample team has non-empty grid cells matching `fact_transaction` day buckets; scatter value-added reconciles to a documented formula within ε.
- Evidence chips: verified (tx + lineups 2018+). No zeros for missing pre-2018.
- Chart stack: stay on Chart.js / CSS grid until CHI-76 says otherwise — heatmap can be pure CSS/HTML table; scatter can be Chart.js bubble/scatter.

**Suggested Linear (file when ready):** CHI-9x Team-season activity grid + value-added scatter (AFFL-0xx). Depends on CHI-45 trade join honesty and CHI-32 roster weeks.

**Hermy Baton placement:** Gauntlet **Wave T / Task 6** in  
`docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md`  
— after trust bugs + verify pile (and dashboard Elo/milestones), **before** CHI-76 library planning and deploy. Does not block on chart-library choice.

**Not in this phase:** player-level milestone chases, live ESPN pulls from the browser, FAAB (league does not use it).
