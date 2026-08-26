# Deep research prompt: running models and cumulative NGS change (AFFL side project)

Copy everything below the line into a deep-research model (Grok, ChatGPT, Gemini, Claude). Do not treat this file as implementation. It is a research brief only.

---

You are doing deep research for a side project, not a build. The product is a 12-team ESPN fantasy league (AFFL) that has run since 2014. Scoring is ESPN standard (not PPR). Draft is auction from 2016 on (snake 2014-15). Waivers are traditional order, no FAAB. Keepers are unused (`keeperCount: 0`). Franchise identity is the current team name; owners merge over time.

I already have a warehouse and a site. I do **not** want another recap of public fantasy blogs. I want a research memo that tells me whether a **running / online model** (updated every week as new NGS, snap, and box data land) can beat a static preseason model for (a) weekly start/sit, (b) waiver adds, and (c) in-season trade value. I also want the **cumulative-change** view: how a player's tracking profile is drifting week to week, and whether those drifts predict fantasy outcomes better than season-to-date averages.

## What I already have (do not recommend I go collect these)

- ESPN box scores, lineups, transactions, drafts, settings for this league (2018+ weekly lineups; 2014+ standings/draft).
- nflverse weekly player stats 2014-2025 (`stats_player_week_*.csv`) including EPA, CPOE, WOPR, target share, air yards, standard `fantasy_points`.
- nflverse play-by-play 2014-2025.
- Spotrac cap hits and OTC contracts.
- College / draft capital (breakout age and dominator are still empty).
- ESPN weekly **projected** `appliedTotal` for this league's scoring, 2018-2025 (W17 missing 2018-2020).
- Next Gen Stats weekly passing / receiving / rushing via nflverse (2016+, attempt-minimums apply). Official NGS field charts (pass / route / carry / qb-grid) exist on nextgenstats.nfl.com but CDN filenames are timestamped.
- AFFL-specific derived: lineup IQ, positional PAR/$, auction DNA vs a Cates-style curve, schedule vs roster luck, week-1 roster vs acquired, All-League / Bush, RB career miles from 2014+ touches.

## What I do not have (call this out if a method needs it)

- Dated rest-of-season projections at the moment a trade happened (blocks "trade alpha").
- Full injury report history wired into the site.
- College team-season stats (so breakout age / dominator stay null).
- FAAB (this league does not use it).
- Player tracking coordinates (NGS public tables are aggregates, not x/y).

## Questions the memo must answer

1. **Running vs static.** Survey online learning, weekly retrain, and Bayesian updating as used in sports forecasting (Elo / Glicko, Kalman / state-space, exponential decay, weekly gradient updates, rolling-window XGBoost). For weekly fantasy points in a standard-scoring 12-team league, which class actually wins on out-of-time tests in the published literature or in reproducible public notebooks? Cite papers, blog methods with code, and nflverse-based work. Separate "sounds smart" from "beat a naive rolling mean + ESPN proj."

2. **What should update every week.** Propose a small feature set that can be refreshed Monday night from data I already have: NGS weekly (separation, cushion, xYAC, CPOE, TTT, RYOE, 8-man box), nflverse weekly (WOPR, target share, air yards, EPA), ESPN proj, snap/route participation if available in my pbp or weekly files, age, miles, cap. Rank features by published incremental value for next-week FP. Flag anything that leaks future information.

3. **Cumulative change, not levels.** I care about **deltas and slopes**: 3-week change in separation, WOPR, CPOE, RYOE, target share; "broke out" vs "being phased out." What windows (3, 4, 6, EWMA) show up in research? How do you avoid noise on low-volume players (NGS attempt minimums, backup RBs)? What is the right way to chart this on a player page (z-score vs own baseline vs position baseline)?

4. **Baselines I must beat.** Define a serious evaluation protocol:
   - Unit: player-week, regular season only, 2018-2025, AFFL-standard points.
   - Split: walk-forward by week (train through week t-1, predict week t). No random row split.
   - Baselines: (i) ESPN weekly proj, (ii) trailing 4-game average, (iii) seasonal average, (iv) a simple position-week regression on WOPR / carries / attempts.
   - Metrics: MAE and rank correlation overall and by position; hit rate on "start the right guy" in a 2-player pair; waiver: did the model rank the actual add higher than the median rostered bench?
   - Report sample sizes. Do not hide that NGS is missing for many player-weeks.

5. **AFFL-specific constraints.** Auction values and PAR/$ are seasonal. In-season the decision is start/sit, waiver, and trade. Traditional waivers mean priority, not bid. A running model that outputs a single "rest of season points" number is less useful than one that outputs (next week mean, remaining-season mean, uncertainty). How should those three numbers be produced without a dated ROS product?

6. **NGS charts vs NGS tables.** Official NFL charts are images. nflverse NGS is tabular. For a player game log, what is actually predictive (the table) vs decorative (the field drawing)? If I later add a running model, which NGS fields are worth a sparkline on every week row?

7. **Failure modes.** List where running models quietly lie: small samples, injury return weeks, scheme changes after a trade/coach firing, garbage-time WOPR, DST/K, players below NGS thresholds, double-counting ESPN proj that already includes the same news.

## Deliverable

A research memo, not a build plan:

- 1-page verdict: is a running model worth a side project for this league, or do ESPN proj + trailing averages already capture it?
- A recommended model class and update cadence, with citations.
- A feature list (keep / try / skip) tied to files I already have.
- The exact walk-forward eval recipe, including how to treat missing NGS.
- A "cumulative change" chart spec (what to plot, what window, what baseline) that a later build could implement on a player page.
- An annotated bibliography (papers, nflverse notebooks, open GitHub). Prefer primary sources over listicles.
- Explicit "do not build yet" items if the evidence is weak.

Do not invent AFFL standings, player stats, or paper results. If a citation is behind a paywall and you only have the abstract, say so. If the literature is thin, say the literature is thin and recommend the smallest experiment that would settle it.
