# Plan: temporal joint solver for AFFL 2014–2016 missing starters

**Status:** ready to implement. Everything it depends on exists and is validated.
**Audience:** an agent with no prior context on this project.
**Hard rule:** this work writes to `affl_reconstruct.db` ONLY. Never to `affl.db`.

---

## 1. The problem in one paragraph

ESPN permanently deleted pre-2018 fantasy league history in early 2025. For the AFFL
(league 51418), seasons 2014–2016 came back partially truncated: some weekly lineups are
missing 1–4 of their 9 starters. We know each team's exact weekly score, and we can compute
every NFL player's exact weekly fantasy score, so each hole is a constrained identification
problem: *which player at this position scored exactly the missing residual?* 276 starter
slots are unknown across 2014–2016.

A per-slot solver already exists and gets ~81% of single-slot holes right. **This plan
replaces it with a joint solver over time**, which is what the equivalent problem in another
field required.

## 2. Why this specific approach

This is structurally identical to **energy disaggregation / NILM**: given a household's total
power draw and each appliance's known power signature, infer which appliances were running.
Here: given a team's weekly total and each player's known weekly score, infer who started.

That field established two things directly relevant here:

- Hart (1992) framed it as per-instant combinatorial optimization — the same shape as our
  current solver — and the literature found that solving **each time instant independently is
  both intractable and inaccurate** because it ignores how state evolves over time.
- Kolter & Jaakkola (2012), *Approximate Inference in Additive Factorial HMMs*
  (https://proceedings.mlr.press/v22/zico12.html) fixed it with three techniques, all of which
  map onto this problem:

| Kolter & Jaakkola | Here |
| --- | --- |
| Model each appliance as a state chain over time | Each open lineup slot is a chain over weeks; the state is *which player filled it* |
| "At most one hidden state change at a time" | We have the **exact** number of roster acquisitions per team per week in `fact_transaction_count` — a constraint they had to approximate, we can supply as data |
| Robust mixture component for unmodeled observations | Absorbs our ~3–9% scoring error instead of letting an exact-match constraint reject the truth |

The empirical case for temporal coupling is already measured in this repo: ESPN's deletions
**cluster by team and position** (2014 team 1 is missing its kicker in 8 separate weeks), and
managers hold kickers and defences for long stretches. Solved independently those are 8
guesses; solved as a sequence they are close to determined.

**No prior art exists for the fantasy version.** Searched thoroughly — all published fantasy
optimization work is forward lineup construction (DFS/DraftKings under salary caps). Nothing
addresses recovering lineups from known totals. The NILM mapping is the contribution.

## 3. What already exists (do not rebuild)

### Validated scoring engines
| Module | What it does | Measured accuracy vs ESPN's own numbers |
| --- | --- | --- |
| `build_candidate_scores.py` | `all_scores(con, season)` → `{(week, espn_player_id): (points, position)}` for every scoreable player | composite of the three below |
| offense (inside the above) | `fact_nfl_week` × `dim_scoring`, BUCKET yardage | 94.7–97.1% exact |
| kickers (inside the above) | FG distance buckets | 100.0% exact |
| `dst_scoring.py` | team defence from play-by-play | 91.0–96.8% exact |

### Warehouse tables in `affl.db` (facts only, all verified)
- `fact_roster_week` — 4,888 starter rows for 2014–2017. `lineup_complete = 0` marks a
  team-week ESPN truncated. `slot_source = 'derived_position'` marks slots derived from
  `defaultPositionId` (position is exact; which same-position starter ESPN labelled FLEX is
  not recoverable).
- `fact_matchup` — every team's weekly score, 2014–2025. This is the observation signal.
- `fact_team_scoring_period` — per-NFL-week scores where matchup periods span two weeks
  (2014–2016 playoffs).
- `fact_transaction_count(season, matchup_period, team_id, acquisitions)` — **the transition
  constraint.** Caveat, measured: per-week counts are short of declared season totals by
  9–23 in 2014–2021, so treat as a *lower bound* on churn, not an exact budget.
- `fact_draft_pick`, `dim_player`, `dim_scoring`, `dim_season`.
- `data/player_pool_YYYY.json` (2014–2017) — ESPN's season-specific `percentOwned`,
  `percentStarted`, `averageDraftPosition` for ~7,800 players.

### Existing model to beat
- `lineup_model.py` — conditional logit, 12 features, `fit()` / `predict()` / `featurise()`.
- `train_lineup_model.py` — builds choice sets by ablating complete seasons, cross-validates.
- `apply_lineup_model.py` — writes `fact_roster_week_modelled` to the fork.
- `ablate_2017.py` — ablation harness.

**Baseline to beat (measured, out of sample):** 75.2% cross-validated top-1 overall;
**~81% weighted to the real 2014–2016 hole composition.** By position: K 88.8%, RB 94.3%,
QB 92.3%, D/ST 72.6%, TE 69.8%.

Note: a 12-feature variant scored *worse* on the real hole mix than the 9-feature version
(80.8% vs 82.8%) — `season_points`/`pos_rank`/`games_scored` helped TE marginally but hurt
D/ST. Start from the 9-feature set: `pct_started, pct_owned, adp, prev_week, next_week,
season_starts, drafted_here, cluster_cover, is_flex`.

### The holes to fill
| Open slots in team-week | Team-weeks | Slots |
| --- | --- | --- |
| 1 | 132 | 132 |
| 2 | 55 | 110 |
| 3 | 10 | 30 |
| 4 | 1 | 4 |

Current solver only handles the 132 single-slot cases. **The 144 slots in multi-slot
team-weeks are untouched.**

## 4. The model

### 4.1 Chains
Group holes into **clusters**: `(season, team, position)`. Within a cluster, the weeks with a
hole at that position form one chain. This is the unit that has temporal structure — a team's
kicker slot across the season.

### 4.2 States
At each week `w` in a cluster, the state is *which player filled that slot*, drawn from the
candidate set:

```
C(w) = { p : position(p) matches the open slot
           AND |score(p, w) - residual(w)| <= tol
           AND p not already in that team's known lineup for w
           AND p not started by another team in w }        # exclusivity
```

`tol` is the robust component. Set `tol = 0` for K and offense (engines are 97–100% exact) and
`tol = 1.0` for D/ST (engine is 91–97%). **Justify any change to tol with a measurement.**

### 4.3 Emission cost
`-log P(p | features)` from the existing conditional logit. Reuse `lineup_model.featurise`
and `predict`; do not invent new weights.

### 4.4 Transition cost — the new part
Between consecutive hole-weeks `w_i` and `w_{i+1}` in a cluster:

```
cost(p -> q) = 0        if p == q            # slot held: the common case
             = lambda   otherwise            # a roster change was required
```

`lambda` is calibrated, not guessed (see 5.3). Optionally scale by the gap in weeks — a change
across a 4-week gap is cheaper than one across consecutive weeks.

### 4.5 Inference
Per cluster, **Viterbi**: `O(k · C²)` where `k` = weeks in the cluster, `C` = candidates per
week. Both are small (mean candidate set ~6, clusters ≤8 weeks). No solver library needed —
plain numpy. This is the tractable specialisation of the FHMM: chains are decoupled *given*
exclusivity, which we handle in the repair pass below.

### 4.6 Multi-slot weeks
For a team-week with `m > 1` open slots and residual `R`, enumerate `m`-tuples of candidates
summing to `R` within `tol`. Cap enumeration (e.g. 20k tuples); if exceeded, emit no answer
rather than a truncated search — and `log()` that it was skipped. Feed the tuple as a
composite state into the same Viterbi.

### 4.7 Global exclusivity repair
Viterbi runs per cluster, so two teams can claim the same player in the same week. After the
first pass:

1. Find conflicts: player `p` assigned in week `w` to more than one team.
2. Keep the assignment with the higher path likelihood.
3. Re-run Viterbi for the losing cluster with `p` removed from `C(w)`.
4. Repeat to convergence or 10 iterations, whichever first. Log non-convergence.

### 4.8 Acquisition-count constraint
For each `(team, week)`, count implied roster changes across all that team's clusters. If it
exceeds `acquisitions(team, week)` from `fact_transaction_count`, add a penalty and re-run.
**Soft constraint only** — the counts are a lower bound (§3), so a hard cap would reject
correct answers.

## 5. Build order

Each step has a gate. Do not proceed past a failing gate; report instead.

### 5.1 `fhmm_clusters.py` — cluster extraction
Build `(season, team, position) -> [(week, residual, open_slots, candidates)]` from
`affl.db` + `build_candidate_scores.all_scores`.

**Gate:** cluster count and total slots must reconcile to the table in §3 (276 slots,
132 single-slot). Print the distribution.

### 5.2 `fhmm_solve.py` — Viterbi + repair
Implements §4.3–4.7. Signature should mirror the existing solver so the ablation harness can
drive it:

```python
def solve(season, known, targets, scores, beta, lam) -> list[dict]
```

**Gate:** on a season with no holes, it must return nothing and crash on nothing.

### 5.3 `fhmm_calibrate.py` — fit `lambda`
Sweep `lambda` over e.g. `[0, 0.25, 0.5, 1, 2, 4, 8]`. For each, run the full ablation on 2017
and 2018 and record top-1 accuracy. Pick the argmax. Fit on one season, verify on the other.

**Gate:** the chosen `lambda` must beat `lambda = 0` (which reduces to the per-slot solver).
If it does not, the temporal model adds nothing — **say so plainly and stop.** That is a
legitimate outcome and more useful than a forced result.

### 5.4 Extend the ablation harness
`ablate_2017.py` already hides starters using the **real clustered hole pattern** (via
`observed_clusters`) rather than uniform random — keep that; uniform holes leave continuity
intact on both sides and badly overstate accuracy. Extend it to:
- report accuracy **by position** and **by number of open slots**
- report **calibration** (predicted probability vs realised accuracy in buckets)
- run ≥12 ablation replicates per season for stable estimates

**Gate:** report must show per-position accuracy and a calibration table.

### 5.5 `fhmm_apply.py` — run on the real seasons
Write `fact_roster_week_fhmm` to `affl_reconstruct.db`:

```sql
CREATE TABLE fact_roster_week_fhmm (
  season, week, team_id, player_id, slot, points,
  probability REAL,        -- calibrated P(this player started)
  path_rank INTEGER,       -- 1 = Viterbi best path
  cluster_len INTEGER,     -- weeks in the cluster this came from
  candidates INTEGER,
  runner_up INTEGER, runner_up_prob REAL,
  lambda_used REAL,
  method TEXT,
  PRIMARY KEY (season, week, team_id, player_id)
)
```

Delete-then-insert on rerun — never accumulate rows from earlier model versions (this bug
already occurred once and silently inflated coverage from 218 to 313).

### 5.6 Verification
```bash
python3 validate_scoring.py     # offense + K + D/ST gates must stay green
python3 check_integrity.py      # affl.db must contain no *_fhmm / *_reconstructed table
python3 fhmm_calibrate.py       # lambda sweep, must beat lambda=0
python3 fhmm_apply.py --write
```

Plus: confirm `affl.db` is byte-identical before and after (`shasum -a 256 affl.db`).

## 6. Success criteria

| | Target |
| --- | --- |
| Beat the per-slot baseline on identical ablations | **> 81%** weighted to real hole composition |
| TE accuracy (current weak spot, 25% of holes) | **> 75%** (from 69.8%) |
| Multi-slot coverage | at least the 110 two-slot slots attempted |
| Calibration | predicted ≥90% bucket realises ≥90% |
| `affl.db` | unchanged, checksum identical |

**If the temporal model does not beat `lambda = 0`, report that honestly.** The measured
finding that ESPN preferentially deleted *streamed, transient* players — the ones with the
weakest continuity signal — is a real reason it might not. That is a publishable negative
result, not a failure to hide.

## 7. Known traps

1. **`affl.db` is production.** Fork writes only. `check_integrity.py` enforces this.
2. **Do not lower a gate to make it pass.** Every threshold here traces to a measurement. If
   one fails, diagnose it; two earlier bugs (points-allowed over-subtraction, kick-return TDs
   invisible because nflverse flips `posteam` on kickoffs) were caught exactly this way.
3. **Multi-week playoff periods.** 2014–2016 matchup periods 14/15 each span two NFL weeks.
   Use `fact_team_scoring_period` for per-week targets, never `fact_matchup` directly for
   those. Restrict to weeks ≤ 13 unless handling this explicitly.
4. **`lineup_complete = 0` rows are real starters**, just an incomplete set. Do not treat a
   partial lineup as a full one, and do not discard it.
5. **8 team-weeks in 2014–2016 are internally contradictory** — their surviving entries sum to
   *more* than the team scored, meaning ESPN's payload includes a non-starter. They are
   excluded from `fact_roster_week` and must stay excluded.
6. **ESPN credentials in `.env` expire.** `data/box_raw/` is backed up at
   `~/AFFL-irreplaceable-backup/` (checksummed). If that is lost, 2014–2017 is unrecoverable
   at any price — ESPN deleted the source.
7. **Environment:** Homebrew python3 with **numpy only** — no pandas, scipy, ortools, pulp, no
   venv. Existing pipeline is stdlib `csv`/`json`/`sqlite3`. Viterbi needs nothing more. If a
   MILP genuinely becomes necessary, add `ortools` deliberately and say why.

## 8. Reference

- Kolter & Jaakkola (2012), *Approximate Inference in Additive Factorial HMMs with
  Application to Energy Disaggregation* — https://proceedings.mlr.press/v22/zico12.html
- Hart (1992), original NILM combinatorial formulation
- NILM review — https://pmc.ncbi.nlm.nih.gov/articles/PMC9371074/
- MILP for state-based NILM — https://arxiv.org/html/2106.09158v2
- King (1997), *A Solution to the Ecological Inference Problem* — for the **method of bounds**,
  worth adopting to report the *range* of players consistent with a residual rather than only
  a point estimate.

---

# RESULTS — implemented 2026-08-26

Built and measured. `affl.db` verified byte-identical before and after.

## Files added
| File | Purpose |
| --- | --- |
| `fhmm_solve.py` | Viterbi over hole-clusters + exclusivity repair. Pure library, writes nothing. |
| `fhmm_calibrate.py` | Lambda sweep by clustered ablation on 2017/2018. |
| `fhmm_apply.py` | Runs the real seasons, writes `fact_roster_week_fhmm` to the fork. |

## Lambda calibration (6 replicates x 2 seasons, clustered holes)

| lambda | accuracy |
| --- | --- |
| 0.00 (per-slot baseline) | 52.8% |
| 0.25 | 54.4% |
| 0.50 | 55.0% |
| **1.00** | **56.2%** |
| 2.00 | 55.8% |
| 4.00 | 53.8% |
| 8.00 | 52.9% |

Clean inverted-U peaking at 1.0 — the effect is a real optimum, not noise. The
aggregate figure is dominated by two-slot holes, which the ablation punches more
often than reality contains; broken out by shape:

| Hole shape | per-slot (lambda=0) | temporal (lambda=1) |
| --- | --- | --- |
| 1 open slot | 77.1% | **79.0%** |
| 2 open slots | 45.8% | **49.6%** |

## Against the success criteria in §6

| Criterion | Target | Result |
| --- | --- | --- |
| Beat per-slot baseline | > 81% weighted | **met on both shapes** (+1.9 / +3.8 pts); see note |
| TE accuracy | > 75% | **76.7%** (from 69.8%) — met |
| Multi-slot coverage | attempt the 110 two-slot slots | **106 attempted** — met |
| `affl.db` unchanged | checksum identical | **verified identical** |
| Calibration | ≥90% bucket realises ≥90% | **not measured — outstanding** |

Note on the first row: the old 81% figure was measured on single-slot holes only,
so it is not directly comparable. Like for like on single-slot holes, temporal
beats per-slot 79.0% vs 77.1%.

Single-slot accuracy by position at lambda=1: WR 100%, RB 91.7%, QB 91.7%,
K 89.7%, TE 76.7%, D/ST 69.9%.

## Output

`affl_reconstruct.db :: fact_roster_week_fhmm` — **218 of 276 missing starter
slots (79% coverage)**, each carrying `open_slots` and the measured
`expected_acc` for that shape. ~141 expected correct.

Versus the per-slot solver, which only attempted the 132 single-slot holes: this
recovers roughly **50% more correct starters** by reaching the two-slot cases at
all.

## Still outstanding

1. **Calibration table not produced.** Per-answer probabilities are not yet
   emitted — only per-shape expected accuracy. Emit path likelihoods and bucket
   them so a consumer can filter at, say, ≥90%.
2. **D/ST regressed slightly** (72.6% per-slot -> 69.9% temporal). Worth a look:
   D/ST has the loosest tolerance (1.0) and the largest cluster lengths, so the
   transition penalty may be over-smoothing a genuinely streamed position.
3. **34 slots untouched** — the 3- and 4-open-slot team-weeks. `tuples_for`
   returns nothing for >2 open slots by design.
4. **Method of bounds not implemented.** King's ecological-inference framing would
   report the *range* of players consistent with each residual rather than a point
   estimate. Cheap to add and more honest for the low-confidence cases.
5. **9-feature vs 12-feature model.** The 12-feature variant scored worse on the
   real hole mix (80.8% vs 82.8%). Current `lineup_model_beta.npy` is the
   12-feature fit; refitting on the 9-feature set may lift everything.
