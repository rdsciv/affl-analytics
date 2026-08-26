# Playoff odds

Concrete spec. Grounded in `affl.db` as of 2026-08-17 and the contracts in
`CONTRACTS.md` / `SPEC.md`. If a number below is not from the warehouse, it is
not a number.

This is the AFFL version of Sportradar's Day-3 read: after the auction and three
scored weeks, say who is actually good, who is lucky, and who is in trouble —
with a why, and without inventing a deep-learning stack the sample cannot hold.

---

## 1. Decision

**v1 is a schedule-aware Monte Carlo, not a 50-feature LTV model.**

Roadmap already named this ("playoff odds by week from each team's score
distribution"). This file locks the grain, the features, the baseline it must
beat, and the evidence rules.

A learned model is allowed only as a *residual* on top of the simulation, and
only if leave-one-season-out beats the lookup table in §3. Until then the
lookup table and the simulation *are* the product.

---

## 2. What the warehouse can actually see at Week 3

| Grain | 2014–2017 | 2018–2025 | Notes |
| --- | --- | --- | --- |
| Weekly team scores, W/L, PF, schedule | verified | verified | `fact_matchup` |
| Auction bids, position spend | verified | verified | `fact_draft_pick` |
| All-play / power through week 3 | verified | verified | `v_team_week.beat_this_week` |
| Discrete luck through week 3 | verified | verified | `v_luck` definition, week-filtered |
| Weekly lineups, bench points | unavailable | verified | `fact_roster_week` |
| Adds / drops / trades | unavailable | verified | `fact_transaction`, `fact_trade` |
| Weekly PAR / custody so far | unavailable | verified | `fact_player_week_par` |
| Season-end PAR, final rank, playoff seed | outcome | outcome | **targets, never features** |
| FantasyPros consensus projections | unavailable historically | sparse / going forward | do not fake a backfill |
| FAAB | n/a | n/a | traditional waivers, every bid is $0 |
| "Did not set lineup" | unavailable | unavailable | ESPN auto-starts; do not invent churn |

League shape (from `dim_season`, do not hardcode):

- 10 teams / 4 playoff spots / 13 reg weeks: 2014–2016
- 12 teams / 6 playoff spots / 13 reg weeks: 2017–2020
- 12 teams / 6 playoff spots / 14 reg weeks: 2021–2025
- Scoring: `BUCKET` through 2018, `FRACTIONAL` from 2019

Sample for a *team-level* model (scores + draft only): **138 team-seasons**.
Sample for a *lineup/waiver* model: **96 team-seasons** (2018–2025).
That is ~10 features, not 50. The 10×-parameters rule from the papers is the
constraint, not a suggestion.

---

## 3. Baseline the model must beat

Computed 2026-08-17 against `affl.db`. Playoff = `playoff_seed <= playoff_teams`.
Every 2018–2025 seed and rank is populated (96/96). Base rate is exactly 0.500
(6 of 12).

**Week-3 record → later made playoffs, 2018–2025**

| After 3 games | n | P(playoff) |
| --- | --- | --- |
| 3–0 | 11 | **0.818** |
| 2–1 | 35 | **0.629** |
| 1–2 | 41 | **0.366** |
| 0–3 | 9 | **0.222** |

2014–2017, same table, is weaker (3–0 → 0.571 on n=7; 0–3 → 0.400 on n=5).
Use those years in the team-level simulation. Do not use them to sell lineup
skill.

**Week-3 all-play and PF rank are noisier than record in this sample.**
All-play ≥ 0.65 → 0.667 playoff (n=21). PF ranks 1–3 → 0.667; ranks 7–9 → 0.625;
ranks 4–6 → 0.458. That inversion is why v1 does not rank on PF.

**Week-3 bench/start ratio barely moves the needle** (0.51 / 0.50 / 0.46).
Lineup waste is an *explanation* and a GM grade, not a playoff feature, until
a residual model proves otherwise.

If a fancier model cannot beat the 3–0 / 2–1 / 1–2 / 0–3 lookup on
leave-one-season-out Brier score, it does not ship.

---

## 4. Targets (what we predict)

One row per `(season, team_id)` as of a cutoff week `W` (v1: `W = 3`).

| Output | Definition | Evidence |
| --- | --- | --- |
| `p_playoff` | P(playoff_seed ≤ playoff_teams) | verified for all 12 seasons |
| `p_bye` | P(playoff_seed ≤ 2) — only when `playoff_teams >= 6` | verified 2017+ |
| `p_title` | P(final_rank = 1) | verified |
| `exp_pf` | Expected regular-season points for | verified |
| `exp_wins` | Expected regular-season wins | verified |
| `exp_final_rank` | Expected ESPN final_rank | verified |
| `skill_vs_luck` | week-3 all-play expected wins − actual wins (sign flipped from `v_luck_weighted`) | verified |
| `why` | feature contributions, see §7 | derived |

Not in v1: manager churn / "stopped setting lineups." We cannot see it.

---

## 5. Features allowed at week W

Only things known at the end of week W. Season-end PAR, final rank, remaining
player-season totals, and "how the draft aged" are leaks. Do not use them.

### Always (2014–2025)

From `fact_matchup` weeks 1..W, regular season only:

- wins, losses, PF, PA, PF rank, PA rank
- all-play win% and all-play rank (`v_team_week` week-filtered)
- discrete luck (`v_luck` week-filtered)
- remaining opponents' week-1..W PF (schedule strength so far)
- remaining weeks = `dim_season.reg_weeks - W`

From `fact_draft_pick` (known week 0):

- dollars by position (QB / RB / WR / TE / DST / K)
- max bid, n of $1 players, n of $30+ players
- not season-end PAR, not "steals," not `v_draft_value.par`

### 2018+ only

- starter PF vs bench PF through W (not optimal-lineup IQ until that view exists
  as a verified weekly grain)
- waiver adds / drops through W
- trades through W (count, not Trade Realized — that needs the rest of the year)
- custody PAR *so far* from `fact_player_week_par` weeks 1..W, split
  Drafted / Waived / Traded in

### Never

- FantasyPros / ESPN projections as if they were historical consensus
- NGS / xTD as playoff features in v1 (use them later in the *why* for a player,
  not to move `p_playoff`)
- Identity (owner name, "Ryan always starts slow")
- Personas ("zero-RB guy") as a static tag
- Any sportsbook / RG / liability metric

---

## 6. v1 method

### 6.1 Lookup (ships first, in `preview/`)

Materialize §3 as `v_week3_baseline`: for each era (10-team / 12-team) and
week-3 record, the historical P(playoff), P(title), mean final_rank.
Leave-one-season-out: when scoring 2023, drop 2023 from the lookup.

This is the number on the page until 6.2 beats it.

### 6.2 Schedule-aware Monte Carlo

For each team-season, cutoff W:

1. Observed: weeks 1..W are facts. Do not resample them.
2. Each team's remaining-week score is drawn from a distribution fit on *that
   team's* weeks 1..W, shrunk toward the league week-1..W mean. With only 3
   observations, shrinkage is mandatory. Suggested: team mean = (3 * team +
   3 * league) / 6, team sd = league sd until W ≥ 6.
3. Replay the *actual remaining schedule* (`fact_matchup` opponent_id for weeks
   W+1..reg_weeks). Each remaining game: draw both sides independently, assign
   W/L.
4. After each of N sims (N = 2000 is enough at this size), compute wins, PF,
   playoff seed (top `playoff_teams` by wins, then PF — document if ESPN used a
   different tiebreak; if unknown, wins then PF, and chip it).
5. `p_playoff` = fraction of sims that land in the playoff set.
6. Store sim quantiles (p10 / p50 / p90 PF and wins), not just the mean.

Do not simulate consolation. Championship standings use regular season only
(`CONTRACTS.md`). Title odds can continue through the winners bracket only if
we also simulate playoff games; that is v1.1, not v1. v1 title odds may be
"P(finish regular season as the 1-seed)" plus a footnote, or omitted.

### 6.3 Residual model (only if it wins)

Logistic on `made_playoff`, features from §5, **≤ 8 coefficients**, L2
regularized, leave-one-season-out. Candidate features, in order:

1. week-3 wins
2. week-3 all-play %
3. week-3 PF (z-scored within season)
4. remaining SOS (opponents' week-3 PF rank)
5. week-3 net luck
6. RB auction $ share (known week 0; league overpays mid-tier RBs)
7. waiver adds through W (2018+)
8. custody PAR so far (2018+)

If Brier(residual) ≥ Brier(lookup) or Brier(sim), delete it. Do not keep it
because it looks like AI.

---

## 7. Explainability (required)

Every row produces a short why, UFDS-style, from things we actually computed:

- "3–0 historically makes the playoffs 82% of the time in the 12-team era
  (9 of 11 since 2018)."
- "All-play is only .41 — two of the wins were bottom-half scores."
- "You spent $X at RB; this league's $25–49 RBs average −16 PAR. That is
  context, not a week-3 prediction."
- Simulation: "your remaining schedule is 2nd-hardest; that is why sim
  p_playoff is below the 2–1 lookup."

Store contributions in `fact_week3_why (season, team_id, as_of_week, key, value,
direction, text)`. The page reads that table. No black-box "the model says 71%."

---

## 8. Warehouse shape

New, not mixed into existing views:

```
fact_week3_snapshot     -- one row per season, team_id, as_of_week
                        -- features + targets + p_* + method ('lookup'|'sim'|'residual')
fact_week3_why          -- explanation rows
v_week3_baseline        -- era × record lookup, recomputed excluding the scored season
```

`as_of_week` is a column from day one (3 now; 4..reg_weeks later) so we do not
rebuild the table when we walk the season forward.

Promotion rules (`CONTRACTS.md`):

- 2018–2025 snapshots: **verified** inputs, **reconstructed** probabilities
  (they are a model). May appear in Explore / History. Not an award. Not a
  standings column on home.
- 2014–2017: same, but lineup/waiver fields stay **unavailable** (omit, do not
  zero-fill).
- Never put `p_playoff` on an award or a career record.

---

## 9. Validation gate (must pass before the site sees it)

Leave-one-season-out on 2018–2025 (8 folds × 12 teams).

| Check | Pass |
| --- | --- |
| Lookup Brier vs 0.5-prior Brier | lookup wins |
| Sim Brier vs lookup Brier | sim must win to replace lookup on the page |
| Calibration | in 10% buckets, |predicted − actual| ≤ 0.15 on buckets with n ≥ 8 |
| 3–0 / 0–3 sanity | predicted means sit on the right side of 0.5 |
| No leakage | snapshot built with a query that cannot see week > W facts |
| 2014–2017 | reported separately; a miss there does not block 2018+ |

Write the fold table to `preview/week3/SUMMARY.md` and CSVs. Per `FACTORY.md`,
Ryan reads preview, not the website, first.

A page that needs this grain and fails the gate stays out of primary nav.

---

## 10. Where it lives in the product

Per `design.md`: home is "who won this season, and how." This is not home.

v1 surface: a **History / Race** block already on the roadmap — "you were 18%
in week 3 and still made it" — plus a lab table in `preview/` and, after the
gate, a section below the fold on home or on Scoreboard's season strip.

Not v1: start/sit recs, waiver recs, one-tap lineups, a personalized homepage,
Sunday 12:55 inference. Those need this snapshot as a *shared input* later.
Do not build them on a disagreeing second valuation.

Seasonal IA: this page is a regular-season object. In June it is an archive
("week-3 odds vs what happened"), not a live rec.

---

## 11. What we are not building

- A Sportradar-style 50-input deep LTV net. n=96 cannot hold it.
- Manager personas. Style, if we add it, is a weekly vector, v2.
- Canonical ID graph rewrite. Use `dim_player.gsis_id` as it stands.
- An API layer. Static JSON export, same as everything else.
- Auto-set lineups.
- Anything that needs projections we do not have.
- Linear/Notion ticket spam. One ticket, this spec, then preview.

---

## 12. Build order

1. SQL for `v_week3_baseline` + `fact_week3_snapshot` at `as_of_week=3`
   (lookup method only). `inspect_data.py` slice → `preview/week3/`.
2. Print the §3 table from the warehouse (must match this file, leave-one-out
   aside) so the spec cannot drift.
3. Monte Carlo in a small Python script, write sim columns, run the gate.
4. `fact_week3_why` for the lookup + sim drivers.
5. Residual logistic only if step 3's Brier loses to a ≤8-feature model.
6. Site section after Ryan signs off on `preview/week3/SUMMARY.md`.

Work stays on `verify/full-audit`. Warehouse evals are not Done.

---

## 13. Honest limits

- n=11 for 3–0 and n=9 for 0–3. Those percentages will move. Show n.
- Week-3 PF rank inverted in the middle terciles. Do not overfit PF.
- Shrinkage in the sim is a choice; document the weights in `preview/`.
- Playoff tiebreak assumed wins then PF. Confirm against ESPN if a season
  disagrees, then lock it in this file.
- 2025 is in the warehouse as a complete season. Next live week-3 is 2026,
  which this model will not have seen. That is the first real test, not a
  backtest fold.
