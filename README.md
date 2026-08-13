# AFFL Analytics

Five joined static pages for a 12-team ESPN fantasy football league (est. 2014), built from the
ESPN Fantasy API and joined to real NFL data via [nflverse](https://github.com/nflverse/nflverse-data).

**Live:** https://rdsciv.github.io/affl-analytics/

| Page | What's on it |
| --- | --- |
| **Dashboard** (`index.html`) | Season KPIs, weekly scoring waves, standings, schedule-luck index, Next Gen Lab (lineup IQ, draft ROI, position DNA, starter EPA), Fantasy Genius report cards, all-time records back to 2014 |
| **Scoreboard** (`scoreboard.html`) | Every matchup of **every season**, week by week, with complete lineups — slot, player, NFL team, points, collapsible bench. Every player name links into the profiler |
| **Players** (`players.html`) | Per-player hero card, weekly production chart, AFFL journey, and a full game log joining fantasy scoring to real NFL box scores (yards, TDs, targets, EPA) — for any season |
| **Draft** (`draft.html`) | Every draft since 2014. Auction or snake auto-detected; position spend allocation, points-per-dollar efficiency, steals/busts, and the full searchable board |
| **Front Office** (`trades.html`) | Trade blotter showing both sides of every completed trade, waiver/free-agent log, and per-manager wire activity |

All five pages share a season picker and lazy-load one bundle per year.

## Data availability

ESPN's retention differs by data type, so the site adapts per season rather than
pretending the gaps aren't there:

| Data | Seasons | Notes |
| --- | --- | --- |
| Standings, schedules, scores | 2014–2025 | full history |
| Drafts | 2014–2025 | snake in 2014–15, auction from 2016 |
| Weekly lineups (who started whom) | 2018–2025 | ESPN does not retain rosters before 2018 |
| Transactions & trades | 2018–2025 | waivers, free agents, trades, vetoes |
| NFL advanced stats (nflverse) | 2018–2025 | joined `espn_id` → `gsis_id` |

Years with partial data are marked `*` in the season pickers and the affected
panels explain what's missing instead of rendering empty.

## Notable metrics

- **Lineup IQ** — points started vs. the mathematically optimal lineup each week (exact optimum for 1QB/2RB/2WR/1TE/1FLEX/1DST/1K), surfacing points left on the bench.
- **Luck Index** — actual wins minus all-play expected wins, separating scoring from schedule.
- **Draft ROI** — auction points-per-dollar, producing steals and busts.
- **Starter EPA / WOPR / target share** — real NFL advanced stats attributed to whoever started the player, joined `espn_id → gsis_id` at a 99–100% match rate.
- **What-If Machine** — final standings if every manager had started a perfect lineup every week.
- **Manager Report Card** — A+–F grades on the three true skills (draft, lineups, waivers), with luck graded separately.

## Docs

- **[STATUS.md](STATUS.md)** — what's built vs planned, the two-database architecture decision, and assembly status
- **[SPEC.md](SPEC.md)** — verified data availability per season, field inventory, metric formulas, and what is genuinely not obtainable
- **[ROADMAP.md](ROADMAP.md)** — phased plan and the stack decision
- **[METRICS.md](METRICS.md)** — metric catalog benchmarked against FantasyGenius

## Architecture

The warehouse is split into **two SQLite files** plus join views:
- **`affl.db`** — league truth (rosters, matchups, drafts, trades, scoring rules)
- **`nfl.db`** — NFL truth (weekly stats, contracts, cap hits)
- Warehouse views created via `ATTACH DATABASE 'nfl.db' AS nfl`

Join key: `dim_player.gsis_id` (nflverse identifier) connects AFFL rosters to NFL data.

This keeps league facts separate from NFL facts, making the boundary explicit and enabling analysis that joins fantasy performance to real NFL stats and salary cap data.

### TanStack Lab

`lab/` contains a proof-of-concept demonstrating the join: a scatter chart and sortable table of **started fantasy points vs NFL EPA** (2018–2025), built with Vite + D3 + TanStack Table. Live at `site/lab/` after build.

This pattern (TanStack Charts + TanStack Table with Vite static build) is the charting path forward. The existing five pages use Chart.js and will migrate as Stats/Leaderboard features are added.

## Rebuilding the data

Credentials are read from a gitignored `.env` — never committed.

```bash
cp .env.example .env    # then fill in ESPN_SWID and ESPN_S2 from your browser cookies
./fetch.sh
```

`fetch.py` pulls every season — league core, drafts, weekly boxscores, transactions, and the
nflverse weekly stats + rosters. Raw boxscores are ~2.5 MB each, so it reduces every week to
`(playerId, slot, points)` while fetching; a full season of lineups lands in ~250 KB instead of ~42 MB.

Then two processors run:

- `process.py` → league / franchise / all-time analytics, plus ESPN member GUID anonymization
  → `site/data.json` (small; loaded by every page)
- `process_seasons.py` → one self-contained bundle per season in `site/years/{year}.json`, plus the
  `site/index_years.json` manifest the front end reads first

Then the warehouse and its exports:

```bash
python3 build_db.py           # load everything into affl.db + nfl.db, with integrity checks
python3 validate_scoring.py   # gate: reproduce ESPN's points from raw NFL stats
python3 export_site.py        # write SQL-computed metrics into the site bundles
python3 export_lab.py         # export join data for TanStack lab page
```

To build the lab page:

```bash
cd lab
npm install
npm run build   # builds to ../site/lab/
```

Every season-specific panel on every page reads its year's bundle, so switching the season picker
updates the whole page rather than just the standings.

The site is fully static — no build step and no external requests at runtime (Chart.js and every
team logo are vendored locally; only NFL headshots are remote, and they fall back to initials).

### Reconstructing trades

ESPN records the players on a `TRADE_PROPOSAL` and emits `TRADE_ACCEPT` as a bare status event
pointing back via `relatedTransactionId` — which frequently references a superseded counter-offer.
`process_seasons.py` resolves each accept through its own items, then its related proposal, then the
nearest earlier proposal involving that team, and finally dedupes by the exact set of players moved
so one trade can't be counted twice.

## Local preview

```bash
python3 -m http.server 8788 --directory site
```
