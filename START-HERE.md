# START HERE — AFFL Analytics handoff

**Mandatory entrypoint. Read this file before touching code, data, UI, or tickets.**

## 1. Project coordinates

- Local repository: `/Users/chilly/Projects/ccDesktopAFFL`
- GitHub: `rdsciv/affl-analytics`
- Remote: `https://github.com/rdsciv/affl-analytics.git`
- Current branch: `verify/full-audit`
- Current worktree: `/Users/chilly/Projects/ccDesktopAFFL`
- Current HEAD when this handoff was written: `58176a905b40acc649234d3de63e8778f1f6a11b`
- Relative to local `main`: 4 commits ahead, 0 behind when checked.
- The tree is heavily modified and has many untracked files. Preserve unrelated work.
- ESPN league ID: `51418`
- Production GitHub Pages: https://rdsciv.github.io/affl-analytics/
- Production deploys from `main`; the local branch/tree is ahead of production.
- Linear project: [AFFL Sourcebook v1](https://linear.app/childressllc/project/affl-sourcebook-v1-88ad883cc233)
- Linear team/workspace: `Childressllc`

Never guess branch, worktree, status, or ticket state from this snapshot. Re-query them at the start of a task.

## 2. Required read order

Read only what the task needs, in this order:

1. `START-HERE.md`
2. `STATUS.md` — its counts and branch notes are stale; verify against `affl.db` and git.
3. `CONTRACTS.md`, then `FACTORY.md`, then `schema.sql` for the affected grain.
4. Current Linear **In Dev** and **In QA** issues in AFFL Sourcebook v1.
5. The relevant `site/*.html`, `site/*.js`, `site/styles.css`, and named `evals/test_*.py` files.

Also consult `design.md` for UI work and `ROADMAP.md` for sequencing, not current status.
`preview/SUMMARY.md` says it was generated 2026-08-16 14:34 CT and is stale.
`preview/WAREHOUSE.md` is also stale and describes the now-rejected 2026 stub.

Do not bulk-load an Obsidian vault. This repository and Linear are canonical. Use a vault only when a ticket explicitly points to one missing research artifact.

## 3. Sources of truth and evidence gates

### Canonical layers

1. `affl.db` is the analytical warehouse and canonical data source.
2. `schema.sql` is the intended warehouse schema, but may be ahead of the current DB.
3. `site/` is a static frontend. It is not a database.
4. Site JSON should be exported build artifacts, but current sidecars and drift mean some JSON exists only in `site/`.
5. `preview/` is generated inspection output, not canonical data.

Do not assume schema and DB match. Inspect both read-only before changing either.

### Current read-only audit snapshot

The database was queried directly after this handoff was written. Verified current facts:

- `dim_season` for season 2026: 0 rows.
- `dim_team` for season 2026: 0 rows.
- `player_season` for season 2026: 1,948 rows; these are NFL roster identity only, not an AFFL season.
- `integrity_check`: `ok`.
- Backup `affl.db.pre-remove-2026.bak` exists.
- `fact_nfl_week`: 208,168 rows.
- `fact_roster_week`: 24,762 rows, covering 2018–2025.
- `fact_matchup`: 2,220 sides.
- `fact_draft_pick`: 2,124 rows.
- `fact_transaction`: 15,815 rows.
- `fact_trade`: 392 rows in the current DB; older docs say 181 and are stale.
- `fact_contract`: 31,893 rows.
- `fact_cap_hit`: 30,611 rows.
- `dim_player`: 5,107 rows; older docs say 4,854 and are stale.

The current DB does **not** contain these sidecar tables even though `schema.sql` defines them:

- `fact_ngs`
- `dim_player_bio`
- `fact_injury`
- `fact_depthchart`
- `fact_college`
- `fact_player_overview`

Therefore CHI-72 sidecar table loading is not complete in the current warehouse. Do not claim it is.

### Historical limits

- AFFL seasons with completed league facts are 2014–2025 only.
- 2014–2017 have verified matchups, standings, and draft facts.
- ESPN does not retain 2014–2017 weekly lineups/benches or transaction logs.
- End-of-season roster/acquisition snapshots may be used only at their stated grain.
- Computed early player totals are reconstructed and must be labeled.
- Never invent missing benches, weekly ownership, transactions, starts, or zeros.
- 2018–2025 weekly ownership has 24,762 player-roster-week rows.
- NFL production has 208,168 player-week rows.

### 2026 correction — binding

**There is no AFFL 2026 season before the draft.**

The 2026 AFFL has not drafted. It must not exist in `dim_season` or `dim_team` before the draft. Confirmed 2026 membership is navigation/planning data only, never a completed or stub AFFL season. NFL 2026 roster/player context is a different grain and does not authorize an AFFL season row. CHI-75 is the correction ticket.

## 4. Identity contract

Owner, franchise/person, team-season, and alias are separate grains. Follow `CONTRACTS.md`.

- Jason Kafka / Chupacabras canonical owner is `m07`.
- Site and warehouse direction is `m01 → m07`; never reverse it.
- Kevin Sliger merge: `m03 → m08`.
- Tanner Dunn merge: `m20 → m10`.
- Career math groups by canonical owner, not alias, ESPN slot, or `team_id`.
- Gabagooners are new owner `m22` with no AFFL history.
- Pounders (`m19`) and Pollywogs (`m14`) remain historic franchises/owners.

2026 planning membership is the 2025 twelve minus Pounders and Pollywogs, plus Chupacabras and Gabagooners. This is planning/navigation only until the AFFL draft.

Never guess an owner from a team name. Preserve all historical aliases.

## 5. Pipeline commands and mutations

Run from `/Users/chilly/Projects/ccDesktopAFFL`.

### Fetch cached sources

```bash
python3 fetch.py all
python3 fetch.py league
python3 fetch.py draft
python3 fetch.py box
python3 fetch.py tx
python3 fetch.py nflverse
```

`fetch.py` reads `.env`, calls ESPN/nflverse, and overwrites files under `data/`. It does not rebuild `affl.db`.

`./fetch.sh [all|box|tx|process]` also exists, but it continues into `process.py` and `process_seasons.py` and overwrites `site/data.json` and `site/years/*.json`. Do not use it when the intent is fetch-only.

### Warehouse checks and builds

```bash
python3 build_db.py --check
python3 build_db.py
python3 build_db.py --import-matchups 2025
```

- `--check` runs warehouse integrity queries.
- Plain `build_db.py` initializes, wipes, and rebuilds warehouse tables in `affl.db`; it is destructive to current warehouse contents.
- `--import-matchups 2025` mutates matchup facts and import provenance for that season.
- The file advertises `--sidecars`, but current argument handling does not implement a separate sidecar-only path. Do not rely on that flag.
- Current plain build code also calls `load_2026_stub`; do not rebuild until CHI-75 removes that behavior.

Before any warehouse mutation:

```bash
python3 build_db.py --check
cp -p affl.db "affl.db.backup-$(date +%Y%m%d-%H%M%S)"
```

Then state exactly why mutation is needed, run the narrowest command, rerun checks/evals, and compare counts. Backups mutate only a timestamped backup file; do not replace the live DB casually.

### Inspect warehouse

```bash
python3 inspect_data.py --season 2025
```

This opens `affl.db` read-only, but rewrites `preview/SUMMARY.md`, `preview/MATCHUP_IMPORT.md`, and preview CSV outputs.

### Export site metrics

```bash
python3 export_site.py
```

This reads `affl.db` and patches every season bundle found in `dim_season`, then writes `site/years/*.json`, `site/roto_career.json`, `site/player_bio.json`, and `site/miles.json`.

**Do not run `export_site.py` casually.** Sidecar tables are not loaded in the current DB and local sidecar JSON contains state not yet represented in warehouse tables. An export can overwrite or wipe current local site state. Make sidecars warehouse-backed and diff outputs first.

### Serve the static site

The existing process is:

```bash
cd /Users/chilly/Projects/ccDesktopAFFL/site && python3 -m http.server 8765
```

Local base URL: http://localhost:8765/

A server was already running on port 8765 when this handoff was written. Check before starting another.

### Run evals

Evals are standalone Python scripts, not a pytest suite:

```bash
python3 evals/test_handoff.py
python3 evals/test_<relevant_feature>.py
```

Run the named task eval plus directly adjacent regression evals. Some evals read `affl.db`; inspect each file before running it. Never equate a passing eval with production review.

## 6. Local review loop

1. Check that the existing port-8765 process serves this repository's `site/` directory.
2. Implement the smallest ticketed change locally.
3. Verify data and behavior yourself with the relevant eval and actual page URL.
4. Give Ryan the exact checked `http://localhost:8765/...` URL.
5. Ryan reviews in his own Chrome, refreshes, and critiques.
6. Restate the requested fix first, implement it, verify it, then ask him to refresh.
7. Repeat until Ryan explicitly approves.

Never give an unchecked URL. Never substitute screenshots for a working local page. Screenshots may support review, but screenshot-only review is not acceptance.

## 7. Linear and status rules

Every ask becomes or maps to a Linear issue as work starts. Link implementation and verification to that issue.

- **In Dev**: actively building in the local tree.
- **In QA**: implemented locally and waiting for Ryan's local review.
- **In Deploy**: Ryan reviewed it; waiting for merge/deploy to `main`.
- **Done**: Ryan reviewed it and it is live on production Pages.

Never mark Done because an eval passes, a warehouse row exists, preview files exist, or localhost works.

Current handoff queue, to be re-queried in Linear before work:

- CHI-72 — warehouse foundation; In Dev per the handoff request.
- CHI-75 — remove premature 2026 AFFL season; the current DB has 0 season-2026 rows in `dim_season` and `dim_team`.
- CHI-76 — visualization tooling plan; planning work, not permission to install a chart library first.
- CHI-80 — Scoreboard Notables redesign; Backlog.
- CHI-81 — Awards is broken; Backlog. Do not redesign or fix without an approved system.
- CHI-82 — this handoff. Move to In QA only after `evals/test_handoff.py` passes; never Done here.

If Linear is unavailable, report that and leave status unchanged. Do not infer ticket completion from files.

## 8. Brand and design rules

- Existing AFFL chrome-burst marks: `site/logos/affl-mark.png` and `site/logos/affl-banner.png`.
- Use real franchise artwork in `site/logos/`; do not invent letter tiles or substitute the AFFL mark.
- Follow `design.md`: loud mark, quiet archive body, tables first, progressive disclosure.
- No raw debug tables, internal owner keys, member IDs, or implementation jargon in user-facing UI.
- No isolated CSS patches. Fix components/tokens only under an approved design-system task.
- CHI-81 Awards is known broken and waits for approved design direction.
- CHI-80 Scoreboard Notables redesign is Backlog and also waits.
- Current research pivot is data first. Keep the existing static site up while warehouse contracts are corrected.
- No redesign or Awards fix is part of this handoff.

## 9. Current work and blockers

Do not claim completion from this list; query Linear and inspect the live tree.

- CHI-72 warehouse foundation is In Dev.
- CHI-75 correction is reflected in the current DB: 0 season-2026 rows in `dim_season` and `dim_team`.
- CHI-76 should produce a tooling plan before library adoption.
- CHI-80 and CHI-81 remain backlog design work.
- CHI-82 is documentation/handoff work only.
- Sidecar schemas exist in `schema.sql`, but the current DB lacks all six sidecar tables listed above.
- `STATUS.md`, `preview/SUMMARY.md`, and `preview/WAREHOUSE.md` contain stale counts or stale 2026 claims.
- The working tree has extensive pre-existing changes. Do not clean, reset, stage, or overwrite unrelated work.
- The local site is ahead of production Pages.

## 10. Copy/paste task handoff template

```text
Work in /Users/chilly/Projects/ccDesktopAFFL.
Read START-HERE.md first and follow its read order exactly.
Pick Linear issue CHI-___ in AFFL Sourcebook v1 and confirm its current status/acceptance criteria before editing.
Stay on the current verify/full-audit worktree; do not clone, create a new worktree, or redesign unrelated pages.
State the ticketed problem and intended verification before implementation.
Preserve unrelated modified/untracked files. Treat affl.db as canonical and inspect it read-only unless the ticket explicitly requires a warehouse mutation.
There is no AFFL 2026 season before the draft: do not add 2026 to dim_season/dim_team; membership is planning/navigation only.
Follow CONTRACTS.md identity/evidence rules and do not invent 2014–2017 weekly benches or transactions.
Do not run export_site.py unless the task explicitly requires it and you have proved sidecar JSON will not be lost.
Serve the existing site on port 8765, verify the exact page URL yourself, and give Ryan that checked localhost URL for Chrome review.
Run python3 evals/test_<relevant>.py plus adjacent regressions and report exact results.
Move the issue to In QA only when the local implementation and evals are ready for Ryan; In Deploy only after his review; Done only after his review and production Pages deployment.
Do not commit, push, open a PR, or mark Done unless explicitly asked and the status rules are satisfied.
Report files changed, commands/evals run, data mutations (if any), remaining risks, and the checked review URL.
```

## 11. Do not do these things

- Do not clone the repository or create another worktree.
- Do not create a new site.
- Do not rewrite the static site in React or another framework.
- Do not install or choose a chart library before CHI-76 is approved.
- Do not redesign or patch Awards under this handoff.
- Do not apply isolated CSS patches to Awards or Scoreboard Notables.
- Do not invent 2014–2017 benches, weekly ownership, starts, transactions, or zeroes.
- Do not create a fake/stub AFFL 2026 season before the draft.
- Do not overwrite site JSON blindly.
- Do not run exports casually.
- Do not mutate `affl.db` without a ticket, backup, checks, and explicit need.
- Do not guess owner identity from names or reverse canonical merges.
- Do not expose internal keys/debug tables in the UI.
- Do not bulk-load Obsidian.
- Do not mark work Done early.
- Do not commit, push, or open a PR unless Ryan explicitly asks.
