# Where this project is

Living status file. Prefer live warehouse reads over this table when they disagree.

> **Stale-risk banner (Hermy Baton 2026-08-17):** Counts below were refreshed from
> `affl.db` read-only on this date. Branch of record for agent work:
> `AFFL_Hermy_Baton` (same worktree as verify/full-audit). Law: `START-HERE.md`,
> `CONTRACTS.md`. **No AFFL 2026 season in dim_season/dim_team before the draft.**
> Sidecar tables may be schema-only — do not casual `export_site.py`.
> Gauntlet plan: `docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md`.

**Location** `~/Projects/ccDesktopAFFL`  
**Live** https://rdsciv.github.io/affl-analytics/ (public, no auth, deploys on push to `main`)  
**Repo** https://github.com/rdsciv/affl-analytics  
**Local review** http://127.0.0.1:8765/ (serve `site/`)

Read `START-HERE.md` first. Then `CONTRACTS.md`, `ROADMAP.md`, `FACTORY.md` as needed.

---

## What works today

**Warehouse** — `affl.db` canonical. Seasons **2014–2025 only** (12). Inspect read-only unless a ticket mutates.

| table | rows (2026-08-17) |
| --- | --- |
| seasons / members / franchise-seasons | 12 / 22 / 138 |
| players (5,075 with gsis_id) | 5,107 |
| roster-weeks | 24,762 |
| matchup sides | 2,220 |
| draft picks | 2,124 |
| transactions | 15,815 |
| trades | **392** (was wrongly 181 in older STATUS) |
| NFL player-weeks | see `fact_nfl_week` |
| scoring / player-season points | present |

**Site pages (local)** — Dashboard · Scoreboard · Players · Draft · Trades · Roto · Teams · History · Awards · Dictionary · Wrapped  

**Recent Hermy Baton local ships (not necessarily on Pages yet)**  
- CHI-75 no fake 2026 season · CHI-54 FPpG lock · trade join verify  
- CHI-89 Elo + manager milestones on dashboard Cumulative  
- Wave T team-season activity grid + value-added scatter on Teams  

**Proven, not assumed**  
- Scoring validation gate for pre-2018 work still applies (`validate_scoring.py`).  
- Draft value is **PAR per dollar**, not raw pts/$.  
- Trades reconstructed from roster movement where commissioner feed lied.  
- Eval suite: `python3 evals/test_*.py` (standalone scripts).

---

## Pipeline

```bash
./fetch.sh                  # refresh from ESPN + nflverse (+ fetch_spotrac.py for cap)
python3 build_db.py         # load affl.db, run integrity checks
python3 validate_scoring.py # gate: can we reproduce ESPN's points?
# export_site.py — ONLY when ticket requires it AND sidecar JSON loss is disproved
python3 -m http.server 8765 --directory site
```

Side JSON rebuilds (safe, no full export):  
`python3 scripts/compute_milestones_elo.py`  
`python3 scripts/compute_team_activity.py`

---

## Open / blocked

1. **Production Pages lag** — live site trails local Hermy work until Ryan approves deploy.  
2. **CHI-72 sidecars** — schema may exist; tables often empty; JSON may live only under `site/`. Honesty eval: `evals/test_sidecars_status.py`.  
3. **CHI-76** — stay Chart.js; plan in `research/CHI-76_viz_tooling_plan.md`. No library install without Ryan.  
4. **CHI-80/81** Awards/Notables redesign — backlog; do not thrash mid-gauntlet.  
5. **Keepers** — ESPN `keeperCount: 0` all seasons; house rule?  
6. **50-yard FGs score 3, 40–49 score 4** — intentional?  

## Factory

See `FACTORY.md`. After warehouse mutation run integrity; prefer evals + localhost over vibes. Tickets: Linear AFFL Sourcebook when API live; else ledger under `.superpowers/sdd/`.

## Next up (gauntlet)

- Ryan Chrome on In-QA URLs (see ledger)  
- Deploy only after explicit Ryan approve  
- Optional: tighten value-added pairing; player-level milestone chases later  

## Findings worth remembering

- League overpays mid-tier RBs historically (PAR buckets).  
- ESPN **bucketed yardage through 2018**, fractional 2019+.  
- ESPN keeps **no weekly lineups and no transactions before 2018** — label gaps honestly.  
- FPpG = fantasy points ÷ **NFL games**, never ÷ AFFL starts only.  
