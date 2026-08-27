# Spec: weekly roster reconstruction for AFFL 2014–2017

**Status:** specified, not implemented.
**Hard rule:** this work writes to `affl_reconstruct.db` ONLY. Never to `affl.db`.
`check_integrity.py` enforces it.

---

## 1. Why this exists

Lineup IQ grades start/sit: actual starter points ÷ the best legal lineup the manager
could have fielded. That needs a **bench**, and 2014–2017 does not have one.

What the archive actually holds, all now loaded and verified:

| Grain | Table | Coverage |
| --- | --- | --- |
| Weekly starters | `fact_roster_week` | 5,530 rows, 2014–2017 |
| Late-season roster snapshot, bench included | `fact_roster_snapshot_pre2018` | 659 rows, 41 team-seasons |
| Draft | `fact_draft_pick` | 160/160/160/180 picks |
| Per-week acquisition counts | `fact_transaction_count` | 251 / 340 / 429 / 509 |

Only 19 of those 41 snapshots could be dated against a recovered lineup, so
`export_site.py::export_pre2018_lineup_iq` publishes 18 team-weeks of genuine Lineup IQ
(one is dropped for an unscoreable D/ST). Out of ~500 pre-2018 team-weeks. This spec is
how the rest could be reached — by inference, and labelled as such.

## 2. What is and is not knowable

There is **no pre-2018 transaction feed**. `acquisitionType` is `None` league-wide and
`dim_season.has_tx = 0`. So a roster cannot be rolled forward through adds and drops. The
problem is instead an **assignment problem under pins**: place the players known to have
passed through a team into the 15–16 weekly slots they must have occupied.

Measured pool sizes (starters ∪ dated snapshot ∪ draft) against a 15–16 man roster:

| season | known players per team-season | roster size |
| --- | --- | --- |
| 2014 | 31.6 | 16 |
| 2015 | 34.8 | 16 |
| 2016 | 37.7 | 16 |
| 2017 | 42.4 | 15 |

So roughly twice the roster passed through each team across a season, and the job is
working out when.

## 3. Constraints

**Hard pins — these are facts, never relax them:**

- A player who started for team T in week *w* was on T's roster in week *w*.
  (`fact_roster_week`, 5,530 rows.)
- The 19 dated snapshots pin an entire 15–16 man roster for one specific week.
- A drafted player was on his drafting team in week 1.
- A player is on at most one roster in any week — league-wide exclusivity, the same
  constraint `fhmm_solve.py` repairs for.

**Soft constraint:**

- `fact_transaction_count(season, matchup_period, team_id, acquisitions)` bounds churn.
  Per §3 of `PLAN-FHMM-LINEUP-RECOVERY.md` these counts are **short of declared season
  totals by 9–23**, so they are a *lower bound* on churn. A hard cap rejects correct
  answers. Penalty, not constraint.

**Prior:**

- Reuse `lineup_model.py` (conditional logit) for P(player rostered | features) rather
  than inventing weights. `pct_owned` and `pct_started` from `data/player_pool_YYYY.json`
  are the strongest signals for "was this player rostered at all".

## 4. Shape of the solution

Per (season, team) build a matrix of weeks × known players and solve for occupancy:

- A player's tenure should be an **interval** (or a small number of intervals) — managers
  hold players for stretches. Penalise fragmentation.
- Interval endpoints are what the acquisition counts bound: an interval starting in week
  *w* consumes one of team T's week-*w* acquisitions.
- Exactly 15–16 players occupy each team-week.

Viterbi over per-player state chains with a global exclusivity repair pass is the natural
fit and is already implemented for the analogous problem in `fhmm_solve.py` — read it
before writing anything new.

**Report the range, not just a point estimate.** King (1997)'s method of bounds is listed
as outstanding item 4 in `PLAN-FHMM-LINEUP-RECOVERY.md`; a roster reconstruction is where
it earns its keep, because "these 4 players are consistent with the bench that week" is a
more honest output than one guess.

## 5. Gates

| Gate | Threshold |
| --- | --- |
| Ablation on 2018–2025 (hide the tx feed, reconstruct, compare to truth) | report per-season precision/recall on roster membership |
| The 19 dated snapshots, held out | must be reproduced from starts + draft + churn alone |
| Exclusivity | zero players on two rosters in one week |
| `affl.db` | checksum identical before and after |
| `check_integrity.py` | exits 0 — no `*_reconstructed` table in main |

Hold out the dated snapshots. They are the only pre-2018 ground truth for a *full* roster
that exists, so using them to fit and then to validate proves nothing.

## 6. What the output may and may not be used for

Lineup IQ computed over a reconstructed roster is an **upper bound on the manager**: the
real bench held at least as many options as the reconstruction found, so the true optimal
is at least as high and the true efficiency at least as low. Present it as a bound, label
it Reconstructed per `CONTRACTS.md`, and keep it off awards. It must never be pooled with
either the 2018+ season `lineupIQ` or the 18 verified `lineupIQPre2018` team-weeks.

If the reconstruction does not beat a trivial baseline (hold the drafted roster all
season, swap only where a start forces it), **say so and stop**. That is a legitimate
result, and §6 of `PLAN-FHMM-LINEUP-RECOVERY.md` already establishes the precedent for
reporting one.

## 7. Reference

- `PLAN-FHMM-LINEUP-RECOVERY.md` — the same problem shape for starters, with measured
  results and its five outstanding items.
- `load_pre2018_bench.py` — how the snapshot is loaded and dated.
- `fhmm_solve.py` — Viterbi + exclusivity repair, already written.
- Kolter & Jaakkola (2012), *Approximate Inference in Additive Factorial HMMs* —
  https://proceedings.mlr.press/v22/zico12.html
- King (1997), *A Solution to the Ecological Inference Problem* — method of bounds.
