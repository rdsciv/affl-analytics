# AFFL Analytics — ready for your review

**Live:** https://rdsciv.github.io/affl-analytics/ (deploys on push to `main`)
**Branch:** `main` (the old `AFFL_Hermy_Baton` branch is gone — `main` is the only branch now)
**Local:** `python3 -m http.server 8765 --directory site` → http://127.0.0.1:8765/

## Eval gate
`python3 evals/test_*.py` (109 scripts): **94 pass, 15 fail.** All 15 pre-exist tonight's work
(verified via `git stash` — identical failure list on clean `HEAD`). Not something to chase in
this pass: `_fix_draft_div`, `gauntlet_hermy_baton`, `test_awards_pos`, `test_chi114_bind`,
`test_chi129`, `test_chi136`, `test_chi139`, `test_chi144`, `test_dictionary`,
`test_league_stays_league`, `test_nav_gates`, `test_savant`, `test_site_git_complete`,
`test_teams_page`, `test_yoff_and_leaders`.

## ⚠️ Not yet pushed — 11 files modified, uncommitted
This review doc was stale since 2026-08-25 (last commit `698c4df`) through ~190 commits of
shipped work — see below. Since then, tonight's session found and fixed a real, root-cause
chart bug (details under "What shipped tonight"). None of it is committed or on Pages yet.

## What shipped since the last review (2026-08-25 → now, ~190 commits)
| Area | What |
|------|------|
| AFFL Savant | Shipped: nflsavant-style scatter explorer, hover tooltips, auction $ bind, franchise colors (CHI-127/129/131/133) |
| Pre-2018 lineups | Weekly starters/bench reconstructed into the warehouse where they reconcile to the official score (CHI-130/133/135) |
| History / Archive | Restored full 2014-2025 year wall + archive book pages; career All-Play fixed to span all years, not just 2025 (CHI-119/120/147) |
| Controls | Draft/Teams/Savant Season+Team pickers consolidated to one control row each, no more duplicate year chips (CHI-140/141/142) |
| Trades | Activity-by-manager accounting fixed (proposed vs pending vs canceled), 2018 sentinel waivers recovered (CHI-112/145) |
| Data binding | ~15 players missing ESPN ids bound in (Rice, Boykin, Young, Tannehill, Blackshear, others) so they stop rendering as "Player N" (CHI-121/124/125) |
| Players/Awards | Landing defaults fixed (Players opens QB/all-time, Awards opens Cumulative) (CHI-137/138) |

## What shipped tonight (uncommitted)
Ran a real dataviz audit against a colorblind-safety validator (OKLCH lightness/chroma/CVD
delta-E checks), not a cosmetic pass:
- **Root-cause fix:** `site/common.js`'s shared color object (`AFFL.C`) — used by every chart
  on Players/Teams/Draft/History/Trades/Roto/score-trend, i.e. almost the whole site — had
  drifted from the CSS brand tokens years ago. QB/RB/WR/etc. rendered a *different* blue/green
  on the dashboard than everywhere else. Fixed at the source plus every stray duplicate hex
  across 9 files.
- **Real accessibility bug fixed:** the franchise-owner color palette (`FG_PALETTE` in
  `players.js`) had two colors effectively identical under red-green colorblindness (ΔE 0.4,
  should be ≥6). Computed a replacement 6-color set that passes every check; verified there's no
  passing 8- or 12-color version in this palette's dark-mode band (tried, confirmed via
  20k+ computed candidates).
- **Fixed both dual-axis (two-y-scale) charts on the site** — the #1 chart anti-pattern:
  `draft.js`'s "Spend vs Return" chart split into two aligned single-axis charts. The other one
  (`chi114.js` weekly NFL chart) is locked by `test_chi114_bind.py`'s three-canvas contract —
  flagged, not touched, needs a ticket to restructure.
- Verified: all 9(+3 more tonight) files parse, full eval suite re-run before/after with
  identical results, zero regressions.

## Intentionally NOT done (need you / design)
- **CHI-80** Scoreboard Notables redesign — backlog
- **CHI-81** Awards redesign — backlog
- **CHI-72** full sidecar warehouse load — honesty only; no casual export
- `chi114.js` dual-axis chart restructure — needs a CHI-114 ticket amendment first
- `players.js` `FG_PALETTE`-adjacent `POS_COLORS` (QB/RB/WR/TE/K/DST) still fails the
  lightness/chroma checks — that's the brand's own neon tokens, not a bug; would need you to
  approve deviating from the documented CSS palette to fully fix

## Check these URLs (once pushed)
1. https://rdsciv.github.io/affl-analytics/
2. https://rdsciv.github.io/affl-analytics/draft.html — scroll to "Spend vs Return"
3. https://rdsciv.github.io/affl-analytics/teams.html
4. https://rdsciv.github.io/affl-analytics/players.html

## Rules held
No Done marks without you. Nothing pushed to `main`/Pages tonight — sitting in the working tree
for you to look at first.
