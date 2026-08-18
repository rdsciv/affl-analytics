# CHI-76 — Visualization tooling plan (plan only, no install)

**Date:** 2026-08-17  
**Branch:** `AFFL_Hermy_Baton`  
**Status:** Planning artifact for Ryan — **zero package installs** in this task.

## Ticketed problem

Need an approved direction before any chart-library change. Grok-era thrash risked installing TanStack / OpenChart / etc. mid-loop.

## Current inventory (live site/)

| Fact | Detail |
|------|--------|
| Library | Bundled `site/chart.umd.min.js` (Chart.js UMD) |
| Call sites | ~25+ `new Chart(...)` across `app.js`, `players.js`, `teams.js`, `draft.js`, `history.js`, `roto.js`, `trades.js`, `score-trend.js` |
| Helpers | `mkChart` / destroy-on-rerender patterns already local |
| Recent ship | Elo sparkline, team activity **scatter**, roto radars — all Chart.js |
| Heatmaps | Team **activity grid** is pure CSS/HTML table (Wave T) — no chart lib |

## Options considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **A. Stay Chart.js** | Already everywhere; no build step; static Pages friendly; agents know it | Weak on shared cross-page state; annotations plugin not loaded; limited grammar | **Default** |
| B. TanStack Charts / Charts | Modern React grammar | **Not this stack** — site is vanilla static HTML/JS | Reject for AFFL archive |
| C. Flint / OpenChart MCP | Nice for agent-hosted panes | Not shippable into Cloudflare Pages static `site/` without a separate host | Keep for Hermes dashboards **outside** this repo |
| D. D3 from scratch | Max control | Huge rewrite; eval surface explodes | Reject unless one-off SVG |
| E. Observable Plot | Nice grammar | Another dependency + learning curve | Defer |

## Recommendation

1. **Default: stay on Chart.js** until a concrete pain is proven (shared brush across Stats pages, or impossible chart type).
2. **Heatmaps / calendars / grids** → CSS/HTML tables first (Wave T pattern). Do not wait on CHI-76 for those.
3. **No new npm packages** on the Pages static site without an explicit Ryan approve + deploy plan.
4. If Chart.js needs annotations (median lines, etc.), prefer a **tiny local plugin** (as Wave T median line) over pulling `chartjs-plugin-annotation`.
5. Hermes-side charting (Flint MCP) is fine for **agent research panes**; do not couple to `export_site.py` or `site/`.

## What would justify leaving Chart.js later

- A Stats page that needs linked brushing across 4+ charts with shared filters, **and** Chart.js hacks become unmaintainable.
- Need for server-rendered SVG digests in `preview/` (still not a browser library change).

## Explicit non-goals (this ticket)

- No install, no CDN swap, no React migration.
- No redesign of Awards / Notables (CHI-80/81).
- Does **not** block Wave T team activity (already shipped CSS + Chart.js scatter).

## Acceptance for “In QA” as planning

- [x] This document exists under `research/`
- [x] Recommendation is stay Chart.js
- [x] Zero `package.json` / lockfile changes
- [ ] Ryan reads and agrees or overrides

## Eval

None (docs). Adjacent regression: existing chart pages still HTTP 200 (verify matrix).
