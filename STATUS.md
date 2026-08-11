# Where this project is

Living status file. Regenerate the numbers with `python3 build_db.py --check`.

**Location** `~/Projects/ccDesktopAFFL`
**Live** https://rdsciv.github.io/affl-analytics/ (public, no auth, deploys on push to `main`)
**Repo** https://github.com/rdsciv/affl-analytics

Read `SPEC.md` for what data exists, `ROADMAP.md` for the plan, `METRICS.md` for the
FantasyGenius benchmark.

---

## What works today

**Warehouse** — `affl.db`, rebuilt from cached sources in ~7s, 4 integrity checks passing.

| table | rows |
| --- | --- |
| seasons / members / franchise-seasons | 12 / 21 / 138 |
| players (4,821 with an nflverse id) | 4,854 |
| roster-weeks | 24,762 |
| matchup sides | 2,220 |
| draft picks | 2,124 |
| transactions | 15,815 |
| trades | 181 |
| NFL player-weeks | 208,168 |
| contracts / cap hits | 31,893 / 30,611 |
| scoring rules / player-seasons | 254 / 7,251 |

**Site** — 5 pages, all 12 seasons, zero console errors:
Dashboard · Scoreboard · Players · Draft · Front Office (trades)

**Proven, not assumed**
- `validate_scoring.py` reproduces ESPN's own fantasy points from raw NFL stats at
  **96–99.8% exact** across all 8 seasons that have lineups. This is the gate for
  any pre-2018 work.
- Draft value is **points above replacement per dollar**, not raw points/$, so a
  cheap QB no longer grades as an infinite steal.
- Trades are derived from **roster movement**, not ESPN's transaction feed, because
  the commissioner executes trades for other managers and the feed credited them
  to his team.

---

## Pipeline

```bash
./fetch.sh                  # refresh from ESPN + nflverse (+ fetch_spotrac.py for cap)
python3 build_db.py         # load affl.db, run integrity checks
python3 validate_scoring.py # gate: can we reproduce ESPN's points?
python3 export_site.py      # write SQL-computed metrics into site/years/*.json
python3 -m http.server 8788 --directory site
```

---

## Open / blocked

1. **`verify/full-audit` is 2 commits ahead of `main` and unpushed.** The live site
   does *not* yet have pre-2018 draft value or the auction-market views. Merge when
   you've looked at the diff.
2. **AFFL logo** — needs to land at `site/logos/affl.png`, then the favicon and
   header mark wire up. Pasted images don't reach the filesystem.
3. **Keepers** — ESPN reports `keeperCount: 0` in *all 12 seasons*, so the keeper
   feature was never used. Is it a house rule, and which years?
4. **50-yard FGs score 3, 40–49 score 4** — intentional, or a settings slip?
5. Stray git worktree at `../ccDesktopAFFL.worktrees/executive-summary-...` on
   branch `agents/executive-summary-...`, identical to `verify/full-audit`. Not
   created by this work; safe to remove with
   `git worktree remove ../ccDesktopAFFL.worktrees/executive-summary-league-legacy-is-not-merely-di`.

## Next up

- **#8** pbp aggregates + Next Gen Stats → unlocks aDOT / RACR / WOPR and expected TD
- **#9** receiving-usage and xTD views
- **#5** the FantasyGenius surface: Rankings, History, Stats, Teams, Wrapped
- **#11** pre-2018 lineup solver (experimental, must be validated before publishing)

## Findings worth remembering

- The league **overpays mid-tier RBs**: $25–49 RBs average **−16 PAR** while $25–49
  WRs return **+14**; $10–24 RBs are **−52**. $10–24 QBs are the best value bucket.
- Manager draft edge vs the league's own market spans **+1,451 to −1,446** over 12
  seasons.
- ESPN **bucketed yardage to whole points through 2018** and went fractional in 2019.
  Getting that wrong costs ~0.5 pts per player-week.
- ESPN keeps **no weekly lineups and no transactions before 2018** — but season
  totals are computable from NFL stats, which is how 2014–17 draft value works.
