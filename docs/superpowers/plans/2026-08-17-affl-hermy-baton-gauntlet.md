# AFFL Hermy Baton — Subagent Gauntlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Slash entry:** `/affl-gauntlet` (skill `affl-hermy-baton`) or `/goal` with the Goal block in §Slash command goal.
>
> **Research companion:** `research/2026-08-17_hermy-baton-deep-research.md`

**Goal:** Drive `ccDesktopAFFL` on branch `AFFL_Hermy_Baton` through a ticketed, eval-gated, Ryan-reviewed loop until warehouse contracts and the static site are trustworthy — without inventing 2026, without casual export, without redesigning backlog pages.

**Architecture:** Controller (Hermes) owns Linear status honesty, ledger, and review gates. One fresh implementer subagent per ticket (or per verify-only wave). Task reviewer after each implement. Whole-branch review only before a deploy wave. Data visibility via `preview/` and `affl.db` read-only before site chrome.

**Tech Stack:** Python 3 warehouse (`affl.db`, `build_db.py`, `evals/test_*.py`), static `site/` (HTML/JS/CSS, Chart.js), local `python3 -m http.server 8765`, Linear Sourcebook statuses, git branch `AFFL_Hermy_Baton` on existing worktree.

## Global Constraints

- Work only in `/Users/chilly/Projects/ccDesktopAFFL`. Same worktree. Branch `AFFL_Hermy_Baton`. **No clone, no new worktree.**
- Read `START-HERE.md` first every session; follow its read order.
- Confirm Linear issue status + acceptance criteria before editing. If Linear API unavailable, report that and leave statuses unchanged.
- Preserve unrelated modified and untracked files. Never `git clean`, reset, or bulk stage.
- `affl.db` is canonical. Inspect read-only unless the ticket explicitly requires mutation; then backup + `--check` first.
- **No AFFL 2026 season before draft.** Do not add 2026 to `dim_season` / `dim_team`. Membership = planning/navigation only.
- Follow `CONTRACTS.md`. Do not invent 2014–2017 weekly benches or transactions.
- **Do not run `export_site.py`** unless the task explicitly requires it and sidecar JSON loss is disproved.
- Serve existing site on **8765**, verify the exact page URL yourself, give Ryan that checked URL.
- Run `python3 evals/test_<relevant>.py` plus adjacent regressions; report exact output.
- Status rules: **In Dev** while building → **In QA** only when local + evals ready for Ryan → **In Deploy** only after his review → **Done** only after review **and** production Pages.
- **Do not commit, push, open a PR, or mark Done** unless Ryan explicitly asks and status rules are satisfied.
- Backlog stays backlog: CHI-80, CHI-81 redesign, CHI-76 library install, CHI-88 presentation charts until foundations clear. **Team-season activity grid/scatter (ROADMAP Phase 9) is in-plan Wave T**, not backlog redesign.
- No SumerSports / Supabase / HermesAFFL migration / third-party ESPN MCP in this loop.
- Never ask Ryan to “sign in on my box” or run homework commands when you can show localhost.

### SDD workspace

```bash
# From skill dir when executing:
# scripts/sdd-workspace docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md
# Ledger: .superpowers/sdd/<plan-basename>/progress.md
```

If scripts unavailable, create:

```text
.superpowers/sdd/2026-08-17-affl-hermy-baton-gauntlet/progress.md
.superpowers/sdd/2026-08-17-affl-hermy-baton-gauntlet/ledger.json
```

Ledger first line: `# SDD ledger — plan: docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md`

---

## Slash command goal

**Name:** `/affl-gauntlet`  
**Aliases:** `/hermy-baton`, skill load `affl-hermy-baton`  
**Standing goal text (paste into `/goal`):**

```text
AFFL Hermy Baton gauntlet. Work in /Users/chilly/Projects/ccDesktopAFFL on branch AFFL_Hermy_Baton only. Read START-HERE.md every turn batch. One Linear ticket at a time from the active wave. State problem + verification before edits. Preserve unrelated WIP. affl.db read-only unless ticket requires mutation. No 2026 dim_season/dim_team. No export_site.py unless proved safe. No commit/push/PR/Done unless Ryan asked. After each ticket: run named evals, curl the exact localhost:8765 URL, append ledger, move to In QA only when ready for Ryan. Skip CHI-80/81 redesign and CHI-76 library install. Loop until wave complete or BLOCKED.
```

**Per-tick controller checklist:**

1. `git branch --show-current` must be `AFFL_Hermy_Baton`
2. Read ledger; skip completed tasks
3. Re-query Linear for next ticket (or use frozen wave order if API down — mark status-as-assumed)
4. Dispatch implementer with task brief path only (not whole plan)
5. On DONE → review package → task reviewer
6. Fix loop ≤5 rounds; breaker → BLOCKED to Ryan
7. Append ledger; next ticket
8. Heartbeat if > few minutes

---

## File map (controller artifacts)

| Path | Role |
| --- | --- |
| `research/2026-08-17_hermy-baton-deep-research.md` | Domain + autopsy |
| `docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md` | This plan |
| `.superpowers/sdd/2026-08-17-affl-hermy-baton-gauntlet/progress.md` | Execution ledger |
| `evals/test_*.py` | Gates (standalone scripts, not pytest) |
| `START-HERE.md` / `CONTRACTS.md` | Law |
| `site/*` | Static product |
| `affl.db` | Canonical warehouse |

---

### Task 0: Controller bootstrap (no product change)

**Files:**
- Create: `.superpowers/sdd/2026-08-17-affl-hermy-baton-gauntlet/progress.md`
- Verify: branch, server, handoff eval

**Interfaces:**
- Produces: ledger baseline, confirmed review base URL `http://127.0.0.1:8765/`

- [ ] **Step 1: Confirm branch and worktree**

```bash
cd /Users/chilly/Projects/ccDesktopAFFL
git branch --show-current   # AFFL_Hermy_Baton
git worktree list           # only existing trees; no new ones
git status -sb | head -20   # dirty tree OK; do not clean
```

- [ ] **Step 2: Confirm site server**

```bash
lsof -a -p "$(lsof -tiTCP:8765 -sTCP:LISTEN)" -d cwd
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/
# Expect 200 and cwd .../ccDesktopAFFL/site
```

- [ ] **Step 3: Baseline evals**

```bash
python3 evals/test_handoff.py
# Expected: PASS
python3 evals/test_warehouse_2026.py
# Expected as of 2026-08-17: FAIL (CHI-75 vs Phase A stub) — record verbatim
```

- [ ] **Step 4: Write ledger identity**

```markdown
# SDD ledger — plan: docs/superpowers/plans/2026-08-17-affl-hermy-baton-gauntlet.md
Branch: AFFL_Hermy_Baton @ <sha>
Server: http://127.0.0.1:8765/ cwd=site PASS
test_handoff: PASS
test_warehouse_2026: FAIL (document lines)
Linear API: unavailable|available
```

- [ ] **Step 5: Do not commit**

Bootstrap creates ledger only. No git commit unless Ryan asks.

---

### Task 1: CHI-75 — lock “no 2026 AFFL season” in code + evals

**Ticketed problem:** DB correctly has 0×2026 season/team rows, but `build_db.py` may still call `load_2026_stub` and `evals/test_warehouse_2026.py` still requires a stub season — agents will reintroduce fake 2026.

**Intended verification:**
- `python3 evals/test_handoff.py` PASS
- New/updated eval: `dim_season`/`dim_team` for 2026 == 0
- Planning membership (if any) is **not** warehouse season rows
- `rg load_2026_stub build_db.py` → no active call path
- No `export_site.py`
- Review URL: N/A (data contract) + optional `http://127.0.0.1:8765/` still 200

**Files:**
- Modify: `build_db.py` (remove/disable `load_2026_stub` call path)
- Modify: `evals/test_warehouse_2026.py` → rename or rewrite as `test_no_affl_2026_season.py` behavior
- Modify: `preview/WAREHOUSE.md` only if regenerating via inspect (prefer leave stale with comment in ledger)
- Test: `evals/test_handoff.py`, updated warehouse eval

**Interfaces:**
- Consumes: CHI-75 rule from START-HERE / CONTRACTS
- Produces: eval that **fails** if 2026 season/team rows appear

- [ ] **Step 1: State problem in ledger before edits**

- [ ] **Step 2: Read-only confirm DB**

```bash
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:affl.db?mode=ro',uri=True)
print(c.execute('select count(*) from dim_season where season=2026').fetchone())
print(c.execute('select count(*) from dim_team where season=2026').fetchone())
PY
# Expect (0,) (0,)
```

- [ ] **Step 3: Write failing eval for the correct contract**

Eval must assert:
- 0 rows `dim_season` where season=2026
- 0 rows `dim_team` where season=2026
- Kafka canonical owner still `m07` for historical Chupacabras mapping (from contracts.py / dim tables — do not invent)
- Does **not** require 12×2026 teams

- [ ] **Step 4: Remove stub loader from build path**

Minimal change: ensure plain `build_db.py` does not insert 2026 season/teams. Do **not** run full rebuild in this task unless ticket forces it; prefer code path fix + eval. If rebuild required: backup DB first.

- [ ] **Step 5: Run evals**

```bash
python3 evals/test_handoff.py
python3 evals/test_warehouse_2026.py   # or new name
# adjacent:
python3 evals/test_historical_gates.py
```

- [ ] **Step 6: Report for Ryan**

Files changed, commands, data mutations (none expected), risks, Linear → In QA only if he needs to review contract text; pure eval/code may wait for batch QA.

- [ ] **Step 7: No commit unless asked**

---

### Task 2: CHI-72 — warehouse foundation honesty + sidecar gate

**Ticketed problem:** `schema.sql` defines six sidecar tables; live DB has none; site JSON holds local sidecar state; CHI-72 must not be claimed complete.

**Intended verification:**
- Inventory script or eval lists missing tables explicitly
- Load path documented; **no** `export_site.py` until load exists **or** export skips missing sidecars safely
- `python3 build_db.py --check` (read-only checks) still green if available
- Do not invent NGS/injury rows

**Files:**
- Read: `schema.sql` (sidecar DDL ~fact_ngs … fact_player_overview)
- Modify: `build_db.py` / adapters only if loading is in scope
- Create or modify: `evals/test_sidecars_status.py` (honest presence/absence)
- Optional scripts under `scripts/` for load — only if ticket scope includes load

**Interfaces:**
- Produces: `sidecars_status` report: MISSING|LOADED counts
- Consumes: existing `site/ngs.json`, `player_bio.json`, etc. as **cache inputs**, not truth until loaded

- [ ] **Step 1: Enumerate schema vs DB**

```bash
python3 - <<'PY'
import sqlite3,re
from pathlib import Path
schema=Path('schema.sql').read_text()
want=re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)',schema)
have={r[0] for r in sqlite3.connect('file:affl.db?mode=ro',uri=True)
      .execute("select name from sqlite_master where type='table'")}
for t in sorted(set(want)-have):
    print('MISSING',t)
PY
```

- [ ] **Step 2: Decide slice (controller)**

If Linear CHI-72 acceptance is “tables loaded,” implement **narrowest** load for one sidecar with provenance. If acceptance is “foundation + honesty,” ship status eval + docs only and leave load for child ticket.

- [ ] **Step 3: Never export_site in this task** unless acceptance requires it and diff proves JSON preserved.

- [ ] **Step 4: Evals + ledger**

- [ ] **Step 5: In QA only when Ryan must review behavior**

---

### Task 3: CHI-54 — FPpG correctness (player page)

**Ticketed problem:** Player cards showed season totals as FPpG (e.g. Tre Tucker ~104). Must be fantasy points **per game** with an honest denominator.

**Intended verification:**
- Denominator documented in code comment + dictionary if present: prefer NFL games played for season FPpG label, or rename metric if AFFL starts-only
- Spot-check Tucker / Kincaid / Kupp style rows via eval
- `python3 evals/test_player_fg.py` and/or new assertions
- Checked URL: `http://127.0.0.1:8765/players.html` (plus any deep link the page uses)
- curl 200 + manual metric sample in report

**Files:**
- Modify: `site/players.js` (and any JSON builders if server-side)
- Test: `evals/test_player_fg.py`, `evals/test_player_charts.py`

- [ ] **Step 1: Reproduce bug with a fixture player id from site JSON**

- [ ] **Step 2: Write/extend eval asserting FPpG ≤ reasonable bound OR equals pts/games**

- [ ] **Step 3: Minimal fix**

- [ ] **Step 4: Run evals + curl players.html**

```bash
python3 evals/test_player_fg.py
python3 evals/test_player_charts.py
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/players.html
```

- [ ] **Step 5: Move CHI-54 to In QA with checked URL for Ryan**

---

### Task 4: CHI-45 — trade builder join (site + warehouse honesty)

**Ticketed problem:** One-sided ESPN TRADE_ACCEPT legs dropped the other half; site year files may show more deals than `fact_trade`.

**Intended verification:**
- `python3 evals/test_trade_builder_join.py`
- `python3 evals/test_trade_grid.py`
- `python3 evals/test_trades_2025.py`
- Spot 2018 Fitz/Bernard two-sided if still the fixture
- URL: `http://127.0.0.1:8765/trades.html`
- Report warehouse count vs site count; do not silent-rebuild DB

**Files:**
- Modify: `site/trades.js`, possibly `process_seasons.py` / trade extract — only if needed
- Test: listed evals

- [ ] Implement only join correctness; no trade-winner grades expansion unless already in CHI-66 scope

---

### Task 5: Verify-only wave — Grok “In QA” pile (no redesign)

**Ticketed problem:** Multiple tickets claimed ready without a single honest gate pass under Hermy Baton.

**Tickets (verify, fix only if eval red):**  
CHI-48 Max Potential · CHI-50/55 titles+record · CHI-51 charts · CHI-53 dictionary · CHI-57/83 awards mechanical · CHI-60/61 draft · CHI-66 wrapped/grades · CHI-67/69 logos · CHI-84 NGS tree (no invented film)

**Intended verification per ticket:**
- Named `evals/test_*.py` PASS
- Exact page URL 200
- One-line residual risk
- Linear stays In QA or returns In Dev on fail — **never Done**

**Files:** touch only on FAIL

- [ ] **Step 1: Run batch**

```bash
python3 evals/test_max_potential.py
python3 evals/test_record_book.py
python3 evals/test_titles_combined.py
python3 evals/test_player_charts.py
python3 evals/test_dictionary.py
python3 evals/test_awards_pos.py
python3 evals/test_w1_awards.py
python3 evals/test_draft_guide.py
python3 evals/test_trade_grades.py
python3 evals/test_logo_home.py
python3 evals/test_logo_strip.py
python3 evals/test_ngs_tree.py
python3 evals/test_ngs_scheme.py
```

- [ ] **Step 2: curl pages**

```bash
for p in index.html scoreboard.html players.html draft.html trades.html \
  roto.html teams.html history.html awards.html dictionary.html wrapped.html; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8765/$p")
  echo "$code $p"
done
```

- [ ] **Step 3: Ledger matrix PASS/FAIL; spawn fix tasks only for FAIL**

- [ ] **Step 4: Give Ryan a single QA checklist of checked URLs**

---

### Task 5b: CHI-89 — Dashboard Elo + manager milestones (done locally 2026-08-17)

**Status in ledger:** complete (local). All-time pane on `index.html`.  
**URL:** `http://127.0.0.1:8765/index.html` (Cumulative).  
**Rebuild:** `python3 scripts/compute_milestones_elo.py` · eval `evals/test_milestones_elo.py`.

Do not re-implement unless evals go red.

---

### Task 6: Team-season activity lab — Activity grid + value-added scatter

**Roadmap:** Phase 9 (`ROADMAP.md`). **Surface:** `teams.html` with franchise **and** single season selected.

**Ticketed problem:** Managers cannot see *when* they churned (day×week) or whether in-season moves helped (tx count vs start-slot value added). Leagology-style refs; AFFL names/logos only.

**Depends on (already green or verify first):**
- CHI-45 trade join honesty
- CHI-32 / `fact_roster_week` started weeks 2018+
- `fact_transaction.ts` for day-of-week
- Pre-2018: empty state only — never invent tx

**Intended verification:**
- Season-scoped only (career view does not fake one year)
- 2025 sample franchise: grid cells match `fact_transaction` day buckets
- Scatter Y = started pts from in-season acquired − counterfactual replaced starters; solid Y=0; dashed = league median
- `python3 evals/test_team_activity.py` PASS
- Checked URL e.g. `http://127.0.0.1:8765/teams.html` (document franchise+year query/hash if any)
- No CHI-76 library install — CSS heatmap + Chart.js scatter

**Files (expected):**
- Create: `scripts/compute_team_activity.py` (or extend export carefully — prefer side JSON, not casual full `export_site.py`)
- Create: `site/team_activity.json` (or per-year slices under `site/years/` only if proven safe)
- Modify: `site/teams.html`, `site/teams.js`, `site/styles.css`
- Test: `evals/test_team_activity.py`
- Docs: keep `ROADMAP.md` Phase 9 as product law

**Interfaces:**
- Consumes: `fact_transaction`, `fact_roster_week` (started), weekly points, owner/team maps
- Produces: per team-season grid matrix + league scatter points for that season
- Y definition must be documented in eval docstring and on-page caption (not Custody PAR)

- [ ] **Step 1: State problem + Y formula in ledger before code**

- [ ] **Step 2: Read-only probe 2025 one franchise**

```bash
python3 - <<'PY'
import sqlite3
con=sqlite3.connect('file:affl.db?mode=ro',uri=True)
print(con.execute("""
  SELECT week, date(ts/1000,'unixepoch'), direction, COUNT(*)
  FROM fact_transaction WHERE season=2025 AND team_id=1
  GROUP BY 1,2,3 ORDER BY 1,2 LIMIT 20
""").fetchall())
PY
```

- [ ] **Step 3: Write failing eval** (grid non-empty 2018+; pre-2014–17 page shows unavailable; Y formula fixture)

- [ ] **Step 4: Compute JSON + wire teams season UI** (highlight selected franchise on scatter)

- [ ] **Step 5: Run evals + curl teams.html; give Ryan checked deep link**

- [ ] **Step 6: No commit unless asked; In QA when ready for Chrome**

---

### Task 7: CHI-76 — visualization tooling plan only

**Ticketed problem:** Need an approved plan before any chart library change.

**Intended verification:**
- Written plan in `research/` or ticket comment: keep Chart.js vs TanStack vs flint vs (not) OpenChart-in-static
- **Zero** package installs
- Note: Team activity heatmap is CSS-first and does **not** wait on CHI-76
- Eval: none (docs) — optional link from ROADMAP

**Files:**
- Create: `research/CHI-76_viz_tooling_plan.md`
- Modify: none of `site/` chart code

- [ ] Compare against current Chart.js usage inventory
- [ ] Recommend default: stay Chart.js until a Stats page shared-state pain is real
- [ ] In QA as planning artifact for Ryan

---

### Task 8: STATUS / preview hygiene (non-blocking)

**Ticketed problem:** Stale counts (trades 181, players 4854, 2026 stub language) mislead agents.

**Intended verification:**
- `STATUS.md` either regenerated from live DB or banner “stale — see START-HERE”
- Do not treat as product feature

**Files:**
- Modify: `STATUS.md` carefully; preserve WIP
- Avoid mass `inspect_data.py` unless intentional (rewrites preview)

---

### Task 9: Deploy wave (only after Ryan)

**Do not execute until Ryan explicitly approves a set of In Deploy tickets.**

- [ ] List approved tickets
- [ ] Commit **only** asked paths (or ask Ryan for commit permission)
- [ ] Merge strategy: `AFFL_Hermy_Baton` → `verify/full-audit` → `main` only as Ryan directs
- [ ] Confirm production Pages
- [ ] Then Linear Done

---

## Subagent roles

| Role | Model tier | Tools | Forbidden |
| --- | --- | --- | --- |
| Implementer | mid | file, terminal, read db ro | commit, Linear Done, export_site, new worktree, other repos |
| Task reviewer | mid/high | read diff package only | edit product code |
| Fix implementer (r4–5) | high | same as implementer | same |
| Final reviewer | high | branch diff | drive-by refactors |

### Implementer brief must include

1. Absolute repo path + branch name  
2. CHI-id + acceptance criteria paste  
3. Global Constraints block (verbatim short form)  
4. Eval commands + expected URL  
5. Report path `.superpowers/sdd/.../task-N-report.md`  
6. “Preserve unrelated dirty files”

### Report contract (implementer returns only)

```text
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
CHI: CHI-##
EVALS: <commands + exit>
URL: <checked or N/A>
FILES: <paths>
MUTATIONS: none | <db backup + command>
CONCERNS: ...
```

---

## Wave order (binding)

```text
Wave A (contracts):     Task 0 → Task 1 (CHI-75) → Task 2 (CHI-72 honesty/load)
Wave B (trust bugs):    Task 3 (CHI-54) → Task 4 (CHI-45)
Wave C (verify pile):   Task 5 (QA matrix)
Wave C2 (league story): Task 5b (CHI-89 Elo + milestones) — done local
Wave T (teams lab):     Task 6 (Phase 9 activity grid + value-added scatter)
Wave D (plan):          Task 7 (CHI-76) — does not block Wave T
Wave E (hygiene):       Task 8
Wave F (human):         Ryan Chrome on In QA URLs
Wave G (deploy):        Task 9 only after Ryan
```

**Why Wave T sits here:** needs honest trades + 2018+ tx/lineups (Waves B/C), ships manager-facing team season insight without waiting on chart-library politics (CHI-76) or Awards/Notables redesigns.

Parallelism: **verify-only** tickets inside Task 5 may use parallel subagents. **Mutating** tickets stay serial. Wave T is serial (one teams surface).

---

## Definition of progress for `/affl-gauntlet`

A gauntlet session is successful if **at least one** of:

1. A contract contradiction closed (CHI-75/72 eval green under no-2026 law), or  
2. A correctness bug fixed with eval + URL, or  
3. A full Wave C matrix produced with honest PASS/FAIL and Ryan-ready URLs, or  
4. Wave T team-season activity grid + scatter live with eval + checked `teams.html` URL  

A session **fails** if it: opens a new app, installs a chart library, invents 2026, runs casual export, marks Done, or drifts to SumerSports/RAID/HermesAFFL.

---

## Self-review (plan author)

| Spec item | Task |
| --- | --- |
| Branch AFFL_Hermy_Baton | Task 0 |
| START-HERE / no new worktree | Global + Task 0 |
| Linear pick + AC | Global + each task |
| No 2026 season | Task 1 |
| Sidecars / no casual export | Task 2 + Global |
| FPpG / trades trust | Task 3–4 |
| Elo + milestones (dashboard) | Task 5b |
| Team activity grid + scatter | Task 6 / ROADMAP Phase 9 |
| CHI-76 plan only | Task 7 |
| Deploy after Ryan | Task 9 |
| Evals + URL | every implement task |
| Status rules | Global + Task 5/8 |
| Grok failure avoidance | Global anti-patterns |
| Slash goal | §Slash command goal |
| Subagent SDD | roles + wave order |
| CHI-80/81 not redesigned | Global skip |
| Deep research subjects | companion research doc |
