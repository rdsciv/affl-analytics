# AFFL Analytics — roadmap

Ordered so that each phase ships something viewable. See `SPEC.md` for verified
data availability and formulas. See `STATUS.md` for what's built vs planned.

---

## Stack decision (FINAL — Aug 2026)

**Keep SQLite → static JSON → GitHub Pages. Do not move to Supabase/Postgres.**

The assembly decision: this repo is the product. The site is **already live** at
`rdsciv.github.io/affl-analytics`, deploys in 27 seconds on `git push`, and has
zero runtime dependencies.

### The Two-Database Architecture

The warehouse is split into **two SQLite files** plus join views:
- `affl.db` — league truth (rosters, matchups, drafts, trades, scoring rules)
- `nfl.db` — NFL truth (weekly stats, contracts, cap hits)
- Warehouse views created via `ATTACH DATABASE 'nfl.db' AS nfl`

Join key: `dim_player.gsis_id` → nflverse identifier.

Ryan asked for "1 AFFL database, 1 NFL database, joined relationally." This honors that literally.

### Rejected Paths

Earlier AFFL attempts (AFFL_Pillars, affl-site, AFFL_ESPN, draftedge-2026, Sourcebook D1) stalled on:
- Cloudflare D1 / Drizzle
- Next.js + hosted runtime
- Supabase / Postgres

Those paths added:
- Services to maintain
- Credentials to rotate
- Deploy complexity beyond `git push`
- Runtime dependencies that can be down

Given the actual requirements — public shared link, **no auth**, read-only, twelve seasons of data that changes once a week at most — a hosted Postgres buys nothing.

**Move to Supabase only if a future feature needs writes** (submit-your-picks game, comments, a poll). That's the trigger, not query complexity.

### Charting Path Forward

**TanStack Charts** is the chosen path, proven in [dienasty-history](https://github.com/rdsciv/dienasty-history). The lab page (this PR) demonstrates TanStack Table + TanStack Charts with Vite static build, judged against this very AFFL site.

`site/` currently uses Chart.js for the five existing pages. **Do not migrate Chart.js everywhere in this PR.** Chart.js is carrying the current dashboard fine; the migration will happen when Stats/Leaderboard pages need sorting + filtering + charting to share state.

### Future: DuckDB-WASM

When ad-hoc querying starts to matter, add **DuckDB-WASM** in the browser against a static `affl.duckdb` or Parquet files. Real SQL, arbitrary joins, zero server, still just a static host. This would make the site genuinely unusual: a public link where anyone can run their own query against the league's whole history.

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
