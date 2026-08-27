# Franchise-year lock Design

Date: 2026-08-26
Status: In Spec (Linear stays In Spec; never Done until Ryan reviews live)
Live site: https://rdsciv.github.io/affl-analytics/
Repo files in scope: `site/history.js`, `site/common.js`, evals under `site/evals/` (or `/tmp/affl-data-plan/evals/` while drafting)
Out of scope: `site/data.json` rewrite, new viz stack, PRs, Chrome driving, 2026 season, 2014–2017 benches

## 1. Problem

`data.json` `franchise.years` is already correct. The History book still lies because **JS binders ignore that array**.

CHI-128 already shipped the Age scatter All path:

- Age scatter All uses the as-of date's year (not a hardcoded 2025).
- Drop owners whose `franchise.years` omit that season.
- `squadYears` empty stays empty (`site/common.js`).

Leftover: every other History **All** widget still binds to 2025 via `latestFinished()` when there is no as-of date. `applySeasonYear(null)` does `seasonYear = latestFinished()`, then Transaction Counter, Adds-by-week, Waiver Report, Transaction Log, Waiver Value, Custody PAR, and The Race all render as if the user picked 2025.

Career rollups (`rollFranchises`, `careerStandRows`, Owners Tenure `firstYear`/`lastYear`) walk `DATA.seasons` instead of intersecting with `franchise.years`. That is the second class of binder leak: presence in a season file is treated as membership.

This is not a warehouse mess. Do not rewrite `data.json`.

## 2. Locked facts (do not invent, do not "fix" the JSON)

| owner | name | `franchise.years` |
|-------|------|-------------------|
| m22 | Gabagooners | `[]` |
| m19 | Pounders | 2021–2025 |
| m14 | Pollywogs | 2021–2025 |
| m18 | Feelers | 2014–2025 |
| m07 | Chupacabras | 2016–2023 |
| m06 | Fat Cats | 2015–2025 |
| m05 | Shadowcöcks | 2019–2025 |
| m21 | Pipers | 2024–2025 |

2014 teams only (exactly these ten):

m11 Skinners, m09 Patriots, m08 Gringos, m16 Thunder, m12 Mad Dawgs, m02 Mighty Cucks, m18 Feelers, m15 Warlords, m17 Sanchitos, m13 Horndogs.

Also locked:

- AFFL is non-PPR.
- No 2026 season before draft.
- Never invent 2014–2017 benches.
- Chart.js stays. Do not adopt D3 or Plotly.
- Ryan: evals first, ship to `main`, no PRs, Linear In Spec now, never Done until he reviews live.

## 3. Approaches considered

### A. Rewrite `data.json` (rejected)

Re-derive `franchise.years` from season files, merges, or ESPN slots. Rejected because the years array is already correct. Rewriting it reopens Gabagooners-as-2014, Pounders-as-founders, and invented 2014–17 benches.

### B. New D3 / Plotly / Vega-Lite viz stack (rejected)

Rebuilding History widgets on a new chart library does not fix membership. Chart.js stays (`site/chart.umd.min.js`). oaustegard `charting` / `charting-vega-lite` are reference-only.

### C. Slot-based history (rejected)

Treat ESPN team slots (`t.id`) as identity across years. AFFL identity is **owner**. Merges already exist (`m01→m07`, `m03→m08`, `m20→m10`). Slot history would re-attach departed owners to current names and invent tenure.

### D. Evals + surgical binder fixes (chosen)

Keep `data.json` frozen. Lift membership helpers onto `window.AFFL` in `site/common.js`. Write failing evals first against locked fixtures. Then change only the History binders that still ignore `franchise.years` or fall back to `latestFinished()` on All.

## 4. Chosen architecture

One source of truth: `DATA.franchises[].years`.

```
DATA.franchises[].years
        │
        ▼
AFFL.franchiseYears(id)          → number[]  (empty stays empty)
AFFL.franchisePlayedSeason(id,y) → boolean
AFFL.ownersForSeason(y)          → owner ids whose years include y
AFFL.seasonScope(pickedYear)     → { mode: "all"|"season", year: number|null }
        │
        ├── All + as-of date (Age scatter only) → as-of year, then filter owners
        ├── All + no as-of (other seasonal widgets) → year is null; do not call latestFinished()
        └── Explicit year chip → that year, filter owners
```

Rules:

1. `years === []` means **no seasons**. Never coerce to "all years" or to the requested year.
2. All without an as-of date is **career / pick-a-season**, never a silent 2025.
3. Seasonal widgets (txn, waivers, tx log, waiver value, custody PAR, race) render a select-season empty state when `seasonScope.year === null`.
4. Career widgets (Franchise Records, Scoring Book, PPD, Finishes heat, Titles, H2H, streaks, Owners Tenure) intersect every season walk with `franchisePlayedSeason`.
5. `firstYear` / `lastYear` / `seasons` count come from `franchise.years`, not from min/max of season-file presence.
6. 2014 owner set is the ten locked ids. Gabagooners never appear in 2014–2025. Pounders / Pollywogs never appear in 2014–2020.

## 5. Files

| File | Role |
|------|------|
| `site/common.js` | Export `franchiseYears`, `franchisePlayedSeason`, `ownersForSeason`, `seasonScope`. Keep `squadYears` empty-stays-empty. Fix `clampYear` so empty years does not fall back to the requested year. |
| `site/history.js` | Stop `applySeasonYear(null)` from assigning `latestFinished()`. Filter seasonal and career binders. Keep Age scatter All = as-of year (CHI-128). |
| `site/evals/franchise-year-lock.test.mjs` | Node evals. Failing first. Fixtures copy the locked years table. |
| `/tmp/affl-data-plan/EVAL-OUTLINE.md` | Case list the eval file must cover. |
| `site/history.html` | Cache-bust `common.js` / `history.js` query params after the binder ship. No markup redesign. |

Do not touch `site/data.json`. Do not add D3/Plotly. Do not open a PR.

## 6. CHI-128 already done (do not regress)

Shipped: `history.js` v18 + `common.js` v25.

- `ageScatterSeason()`: All uses `ageAsOf.getFullYear()`, not `latestFinished()`, except as a last-resort when as-of is missing.
- `seasonAgeRows` filters with `franchisePlayedSeason`.
- `squadYears`: `if (!f || !f.years || !f.years.length) return []`.

Keep those. The leftover is every other All widget.

## 7. Leftover binder list (must change)

In `site/history.js`, `applySeasonYear` currently:

```
pickedYear = y;
seasonYear = y == null ? latestFinished() : y;
```

Then these call `seasonYear` as if All were 2025:

- `renderTxnAndWeeks` / `seasonTxnRows(seasonYear)`
- `renderWaiverReport` (`claimsForYear(seasonYear)`, `teamFromTid(seasonYear, …)`)
- `renderTxLog` / `seasonTxRows(seasonYear)`
- `renderWaiverValue` / `waiverValueRows(seasonYear)`
- `renderCustodyPar` / `custodyParRows(seasonYear)`
- `renderRace` (`DATA.seasons[String(seasonYear)]`)

Career leaks (season-file presence, not `franchise.years`):

- `rollFranchises` firstYear/lastYear/seasons
- `careerStandRows` 2014–2025 walk with no years check
- `rollPPD` / `rollIQ` / `rollTrophies` / `computeWeeklyStreaks` / `computeHof`
- `renderOwnersTenure` first/last from rolled season presence
- `renderHeat` draws a cell for any year the owner appears in `f.finishes`

`clampYear` in `common.js` still does `ys[0] || year` when `years` is empty — a leftover fallback. Empty must stay empty.

## 8. Process

- Linear: **In Spec** now. Never move to Done until Ryan reviews the live GitHub Pages site.
- Evals first. Ship failing evals, then the minimal binder fix, then re-run evals.
- Ship to `main`. No PRs.
- Do not drive Ryan's Chrome. Live review is his.

## 9. Success

On https://rdsciv.github.io/affl-analytics/history.html?year=all (and `?year=2014`):

- 2014 shows only the ten locked owners.
- Feelers appear on 2014.
- Gabagooners appear on no 2014–2025 seasonal widget and have empty career tenure.
- Pounders / Pollywogs never appear on 2014–2020.
- Chupacabras appear 2016–2023 only.
- Fat Cats skip 2014. Shadowcöcks skip 2014–2018. Pipers only 2024–2025.
- All + no as-of: txn / waiver / race / custody PAR do **not** paint 2025.
- Age scatter All still uses the as-of year and drops non-members.
- Chart.js still draws Age scatter, Race, HOF scatter.

## 10. Spec self-review

- No TBD / TODO.
- Approach D is the only implementation path.
- Rejected A/B/C stay rejected even if an eval is annoying to write.
- Identity is owner, not ESPN slot.
